"""HuffEnv (testplan.md §3): AXI-Lite agent (grape pattern) + cocotbext-axi stream
sources/sink + passive AXIS monitors + HuffScoreboard.

The scoreboard is replay-style (grape lesson): it mirrors config writes from the AXI
monitor stream, and at each accepted doorbell runs the golden
`canonical_model.decode_bzip2_symbols` on the byte buffer / selector list reconstructed
from the s_bits / s_sel monitors — never a re-implementation. Every m_sym beat is compared
in order, trace-exact (F-01/F-02/F-05); SYMBOLS/BITS reads after completion are compared
against the golden (F-12). Completion is BUSY-fall on a STATUS read (grape S1 lesson:
sticky DONE survives doorbells, so DONE alone is not completion)."""
from pyuvm import (ConfigDB, uvm_analysis_port, uvm_monitor, uvm_scoreboard,
                   uvm_sequence_item, uvm_tlm_analysis_fifo)

from cocotb.triggers import ReadOnly, RisingEdge

from axi_lite_agent import AxiLiteAgent
from base_env import BaseEnv

# register map (MAS §4; offsets proven by tb/unit/test_top_smoke.py)
ID_REG, CTRL, STATUS, IRQ_EN = 0x000, 0x008, 0x00C, 0x010
CYCLES_LO, CYCLES_HI, SYMBOLS, BITS, BUILD_CYCLES, OVERFETCH = 0x040, 0x044, 0x048, 0x04C, 0x050, 0x054
MODE, START_BIT, ALPHABET, N_TABLES, SYMBOL_LIMIT = 0x100, 0x104, 0x108, 0x10C, 0x110
DBG_SEL, DBG_DATA = 0x114, 0x118
LEN_BASE, LEN_TOP = 0x400, 0x880
ST_BUSY, ST_DONE = 1 << 0, 1 << 1
STICKY_MASK = 0xFFFE          # DONE + ABORTED + ERR bits (write-1-to-clear)
TYPE_EOB = 3


class AxisBeat(uvm_sequence_item):
    """One AXI-Stream handshake: data word, byte-keep, last."""

    def __init__(self, name="beat", data=0, keep=0xF, last=0):
        super().__init__(name)
        self.data = data
        self.keep = keep
        self.last = last

    def __str__(self):
        return f"beat(data=0x{self.data:x} keep=0x{self.keep:x} last={self.last})"


class AxisMonitor(uvm_monitor):
    """Passive AXIS monitor: publishes every tvalid&&tready beat; X after reset asserts
    (F-15 protocol independence, grape monitor pattern)."""

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "dut")
        self.clk = ConfigDB().get(self, "", "clk")
        self.rst_n = ConfigDB().get(self, "", "rst_n")
        self.prefix = ConfigDB().get(self, "", f"{self.get_name()}_prefix")
        self.ap = uvm_analysis_port("ap", self)

    async def run_phase(self):
        sig = lambda n: getattr(self.dut, f"{self.prefix}_{n}", None)
        tvalid, tready, tdata = sig("tvalid"), sig("tready"), sig("tdata")
        tkeep, tlast = sig("tkeep"), sig("tlast")
        n = 0
        while True:
            await RisingEdge(self.clk)
            await ReadOnly()
            if not self.rst_n.value.is_resolvable or int(self.rst_n.value) == 0:
                continue
            assert tvalid.value.is_resolvable, f"{self.prefix}_tvalid X after reset"
            assert tready.value.is_resolvable, f"{self.prefix}_tready X after reset"
            if int(tvalid.value) == 1 and int(tready.value) == 1:
                n += 1
                self.ap.write(AxisBeat(
                    f"{self.prefix}{n}", data=int(tdata.value),
                    keep=int(tkeep.value) if tkeep is not None else 0xF,
                    last=int(tlast.value) if tlast is not None else 0))


class HuffScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.axi_fifo = uvm_tlm_analysis_fifo("axi_fifo", self)
        self.bits_fifo = uvm_tlm_analysis_fifo("bits_fifo", self)
        self.sel_fifo = uvm_tlm_analysis_fifo("sel_fifo", self)
        self.sym_fifo = uvm_tlm_analysis_fifo("sym_fifo", self)
        self.export = self.axi_fifo.analysis_export
        self.bits_export = self.bits_fifo.analysis_export
        self.sel_export = self.sel_fifo.analysis_export
        self.sym_export = self.sym_fifo.analysis_export
        self.golden = ConfigDB().get(self, "", "golden")     # canonical_model module
        self.k1_enforce = (ConfigDB().get(self, "", "k1_enforce")
                           if ConfigDB().exists(self, "", "k1_enforce") else False)
        self.errors = 0
        self.compared = 0
        self.passed = False

    # ---- replay helpers -------------------------------------------------------------
    @staticmethod
    def _drain(fifo):
        out = []
        while fifo.can_get():
            ok, item = fifo.try_get()
            if ok:
                out.append(item)
        return out

    def _check(self, ok, msg):
        if not ok:
            self.errors += 1
            if self.errors <= 20:
                self.logger.error(msg)

    @staticmethod
    def _frame_bytes(beats):
        """Concatenate beats up to and including TLAST into (bytes, beats_consumed)."""
        out = bytearray()
        for i, b in enumerate(beats):
            keep = b.keep & 0xF
            nbytes = 0
            while keep & 1:
                nbytes += 1
                keep >>= 1
            out += int(b.data).to_bytes(4, "little")[:nbytes]
            if b.last:
                return bytes(out), i + 1
        return bytes(out), len(beats)

    def _lengths_from_mirror(self, mirror, n_tables, alphabet):
        """Unpack the LEN window (6 x 5-bit fields per word, table-major) per MAS 0x400."""
        tables = []
        for t in range(n_tables):
            lens = []
            for s in range(alphabet):
                e = t * alphabet + s
                word = mirror.get(LEN_BASE + 4 * (e // 6), 0)
                lens.append((word >> (5 * (e % 6))) & 0x1F)
            tables.append(lens)
        return tables

    # ---- the replay -----------------------------------------------------------------
    def check_phase(self):
        axi = self._drain(self.axi_fifo)
        bits_beats = self._drain(self.bits_fifo)
        sel_beats = self._drain(self.sel_fifo)
        sym_beats = self._drain(self.sym_fifo)

        mirror = {}
        sym_i = 0                 # global index into sym_beats
        exp = None                # expectations of the open invocation, or None
        completed = False
        golden_name = "canonical_model.decode_bzip2_symbols"

        for item in axi:
            if item.kind == "reset":
                mirror.clear()
                exp = None
                continue
            if item.kind == "write":
                if item.addr == CTRL and (item.data & 1):
                    # doorbell: snapshot config, reconstruct this invocation's streams
                    alphabet = mirror.get(ALPHABET, 0)
                    n_tables = mirror.get(N_TABLES, 0)
                    mode = mirror.get(MODE, 0) & 1
                    self._check(mode == 0, "replay: DEFLATE doorbell not supported yet (F-25 gated)")
                    data, used_b = self._frame_bytes(bits_beats)
                    bits_beats = bits_beats[used_b:]
                    sel_bytes, used_s = self._frame_bytes(sel_beats)
                    selectors = [b & 7 for b in sel_bytes]
                    sel_beats = sel_beats[used_s:]
                    lengths = self._lengths_from_mirror(mirror, n_tables, alphabet)
                    syms, end_bit, _cyc = self.golden.decode_bzip2_symbols(
                        data, mirror.get(START_BIT, 0), lengths, selectors, alphabet)
                    exp_beats = [(s, 0) for s in syms[:-1]]
                    exp_beats.append(((TYPE_EOB << 9) | syms[-1], 1))
                    exp = {"beats": exp_beats,
                           "symbols": len(syms),
                           "bits": end_bit - mirror.get(START_BIT, 0)}
                    completed = False
                elif item.addr == STATUS:
                    pass                                  # W1C: sticky mirror at coverage stage
                elif item.addr < LEN_TOP:
                    mirror[item.addr] = item.data
                continue
            # reads
            if item.addr == STATUS and exp is not None and not completed:
                if not (item.data & ST_BUSY) and (item.data & ST_DONE):
                    # invocation complete: compare its m_sym beats now
                    got = sym_beats[sym_i:sym_i + len(exp["beats"])]
                    self._check(len(got) == len(exp["beats"]),
                                f"beat count: expected {len(exp['beats'])} got {len(got)}")
                    for k, (g, (ed, el)) in enumerate(zip(got, exp["beats"])):
                        self._check(g.data == ed and g.last == el,
                                    f"beat {k}: expected (0x{ed:x},{el}) got "
                                    f"(0x{g.data:x},{g.last})")
                    self.compared += len(got)
                    sym_i += len(got)
                    completed = True
            elif completed and exp is not None:
                if item.addr == SYMBOLS:
                    self._check(item.data == exp["symbols"],
                                f"SYMBOLS {item.data} != golden {exp['symbols']}")
                elif item.addr == BITS:
                    self._check(item.data == exp["bits"],
                                f"BITS {item.data} != golden {exp['bits']}")

        self._check(sym_i == len(sym_beats),
                    f"{len(sym_beats) - sym_i} unexplained m_sym beats after replay")
        self.passed = self.errors == 0
        if self.passed:
            self.logger.info(
                f"scoreboard PASS: compared {self.compared} items, 0 mismatches "
                f"(golden={golden_name})")
        else:
            self.logger.error(f"scoreboard FAIL: {self.errors} errors")

    def report_phase(self):
        assert self.passed, f"scoreboard: {self.errors} mismatches"


class HuffEnv(BaseEnv):
    """AXI agent + three AXIS monitors + cocotbext stream sources/sink + scoreboard."""

    def build_phase(self):
        super().build_phase()
        self.agent = AxiLiteAgent.create("agent", self)
        ConfigDB().set(self, "bits_mon", "bits_mon_prefix", "s_axis_bits")
        ConfigDB().set(self, "sel_mon", "sel_mon_prefix", "s_axis_sel")
        ConfigDB().set(self, "sym_mon", "sym_mon_prefix", "m_axis_sym")
        self.bits_mon = AxisMonitor.create("bits_mon", self)
        self.sel_mon = AxisMonitor.create("sel_mon", self)
        self.sym_mon = AxisMonitor.create("sym_mon", self)
        self.scoreboard = HuffScoreboard.create("scoreboard", self)
        # cocotbext-axi masters/sink (drivers only; monitors above are independent)
        from cocotbext.axi import AxiStreamBus, AxiStreamSink, AxiStreamSource
        dut = ConfigDB().get(self, "", "dut")
        clk = ConfigDB().get(self, "", "clk")
        rst_n = ConfigDB().get(self, "", "rst_n")
        self.bits_source = AxiStreamSource(
            AxiStreamBus.from_prefix(dut, "s_axis_bits"), clk, rst_n, reset_active_level=False)
        self.sel_source = AxiStreamSource(
            AxiStreamBus.from_prefix(dut, "s_axis_sel"), clk, rst_n, reset_active_level=False)
        self.sym_sink = AxiStreamSink(
            AxiStreamBus.from_prefix(dut, "m_axis_sym"), clk, rst_n, reset_active_level=False)

    def connect_phase(self):
        self.agent.monitor.ap.connect(self.scoreboard.export)
        self.bits_mon.ap.connect(self.scoreboard.bits_export)
        self.sel_mon.ap.connect(self.scoreboard.sel_export)
        self.sym_mon.ap.connect(self.scoreboard.sym_export)
