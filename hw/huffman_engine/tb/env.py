"""HuffEnv (testplan.md §3): AXI-Lite agent (grape pattern) + cocotbext-axi stream
sources/sink + passive AXIS monitors + HuffScoreboard.

Scoreboard v2 (dv_coverage; closes review B4-B7, B9): replay-style over the timestamped
monitor streams. It models doorbell ACCEPTANCE (BUSY-reject → ERR_BUSY, ABORT priority,
ERR_PARAM clauses, doorbell-time ERR_TABLE) and keeps a sticky-STATUS mirror with W1C, so
error/abort/back-to-back tests replay without desync. Stream beats are attributed to
invocations by timestamp (accepted after the accepting doorbell), not by TLAST faith (B4).
Completion is the first STATUS read showing !BUSY with an outcome predicted for the open
invocation (B6). Expected beats/counters/sticky come from a predictor built ONLY on golden
primitives (`canonical_model.Table` / `BitReader` / `decode_bzip2_symbols`) — never a
re-implementation of the math. Functional coverage: process-wide FUNC_COV bins written to
tb/cov/func_cov.txt at report_phase (grape pattern)."""
import os

from pyuvm import (ConfigDB, uvm_analysis_port, uvm_monitor, uvm_scoreboard,
                   uvm_sequence_item, uvm_tlm_analysis_fifo)

from cocotb.triggers import ReadOnly, RisingEdge
from cocotb.utils import get_sim_time

from axi_lite_agent import AxiLiteAgent
from base_env import BaseEnv

# register map (MAS §4; offsets proven by tb/unit/test_top_smoke.py)
ID_REG, CTRL, STATUS, IRQ_EN = 0x000, 0x008, 0x00C, 0x010
CYCLES_LO, CYCLES_HI, SYMBOLS, BITS, BUILD_CYCLES, OVERFETCH = 0x040, 0x044, 0x048, 0x4C, 0x050, 0x054
MODE, START_BIT, ALPHABET, N_TABLES, SYMBOL_LIMIT = 0x100, 0x104, 0x108, 0x10C, 0x110
DBG_SEL, DBG_DATA = 0x114, 0x118
LEN_BASE, LEN_TOP = 0x400, 0x880
ST_BUSY, ST_DONE, ST_ABORTED = 1 << 0, 1 << 1, 1 << 2
ST_EBUSY, ST_EPARAM, ST_ETABLE = 1 << 8, 1 << 9, 1 << 10
ST_ENOCODE, ST_ESEL, ST_ESYM, ST_ELIMIT, ST_EUNDER = 1 << 11, 1 << 12, 1 << 13, 1 << 14, 1 << 15
STICKY_MASK = 0xFF06          # DONE|ABORTED + bits 8..15 (W1C; bit 0 = live BUSY)
TYPE_EOB = 3

# ---- functional coverage (grape pattern: process-wide dict, written at report_phase) ----
FUNC_COV = {}


def cov(group, bin_name):
    FUNC_COV[f"{group}.{bin_name}"] = FUNC_COV.get(f"{group}.{bin_name}", 0) + 1


def write_func_cov(path="tb/cov/func_cov.txt"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for k in sorted(FUNC_COV):
            f.write(f"{k} {FUNC_COV[k]}\n")


class AxisBeat(uvm_sequence_item):
    """One AXI-Stream handshake: data word, byte-keep, last, sim time (ns)."""

    def __init__(self, name="beat", data=0, keep=0xF, last=0):
        super().__init__(name)
        self.data = data
        self.keep = keep
        self.last = last
        self.t = get_sim_time("ns")

    def __str__(self):
        return f"beat(data=0x{self.data:x} keep=0x{self.keep:x} last={self.last} t={self.t})"


class AxisMonitor(uvm_monitor):
    """Passive AXIS monitor: publishes every tvalid&&tready beat; X on any sampled field of
    an accepted beat asserts (B7; vacuous on 2-state Verilator, armed on Icarus)."""

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
        lanes = max(1, len(tdata) // 8)          # byte lanes from the bus width
        full_keep = (1 << lanes) - 1
        n = 0
        while True:
            await RisingEdge(self.clk)
            await ReadOnly()
            if not self.rst_n.value.is_resolvable or int(self.rst_n.value) == 0:
                continue
            assert tvalid.value.is_resolvable, f"{self.prefix}_tvalid X after reset"
            assert tready.value.is_resolvable, f"{self.prefix}_tready X after reset"
            if int(tvalid.value) == 1 and int(tready.value) == 1:
                assert tdata.value.is_resolvable, f"{self.prefix}_tdata X on handshake"
                if tkeep is not None:
                    assert tkeep.value.is_resolvable, f"{self.prefix}_tkeep X on handshake"
                if tlast is not None:
                    assert tlast.value.is_resolvable, f"{self.prefix}_tlast X on handshake"
                n += 1
                self.ap.write(AxisBeat(
                    f"{self.prefix}{n}", data=int(tdata.value),
                    keep=int(tkeep.value) if tkeep is not None else full_keep,
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
        self.errors = 0
        self.compared = 0
        self.passed = False

    # ---- helpers --------------------------------------------------------------------
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
    def _bytes_of(beats):
        """Bytes carried by a beat list (keep-masked, little-endian lanes)."""
        out = bytearray()
        for b in beats:
            keep = b.keep
            nbytes = 0
            while keep & 1:
                nbytes += 1
                keep >>= 1
            out += int(b.data).to_bytes(4, "little")[:nbytes]
        return bytes(out)

    def _lengths_from_mirror(self, mirror, n_tables, alphabet):
        """Unpack the LEN window: table t at the fixed 48-word stride (MAS §4 amendment
        2026-09-08), 6 x 5-bit fields per word."""
        tables = []
        for t in range(n_tables):
            lens = []
            for s in range(alphabet):
                word = mirror.get(LEN_BASE + 4 * (48 * t + s // 6), 0)
                lens.append((word >> (5 * (s % 6))) & 0x1F)
            tables.append(lens)
        return tables

    # ---- doorbell-time checks (MAS §4/§8) --------------------------------------------
    def _param_error(self, m):
        mode = m.get(MODE, 0) & 1
        alphabet = m.get(ALPHABET, 0) & 0x1FF
        n_tables = m.get(N_TABLES, 0) & 0x7
        limit = m.get(SYMBOL_LIMIT, 0)
        if not (1 <= limit <= (1 << 27)):
            return True
        if mode == 0 and not (3 <= alphabet <= 288 and 1 <= n_tables <= 6):
            return True
        if mode == 1 and not (257 <= alphabet <= 288 and n_tables == 2):
            return True
        return False

    def _table_error_doorbell(self, m):
        """Doorbell-rejection half of ERR_TABLE: a length field 21..31 anywhere in a used
        table's in-alphabet fields (DEFLATE also 16..20)."""
        mode = m.get(MODE, 0) & 1
        alphabet = m.get(ALPHABET, 0) & 0x1FF
        n_tables = m.get(N_TABLES, 0) & 0x7
        bad = 20 if mode == 0 else 15
        for lens in self._lengths_from_mirror(m, n_tables, alphabet):
            if any(l > bad for l in lens):
                return True
        return False

    # ---- the predictor (golden primitives only) --------------------------------------
    def _predict(self, data, start_bit, lengths, selectors, alphabet, limit):
        """Step the golden Table/BitReader to the invocation's outcome.
        Returns dict(beats, symbols, bits, sticky) — beats as (tdata, tlast)."""
        cm = self.golden
        try:
            tables = [cm.Table(l, cm.MAXLEN_BZ2) for l in lengths]
        except ValueError:
            return {"beats": [], "symbols": 0, "bits": None, "sticky": ST_ETABLE}
        rd = cm.BitReader(data, start_bit, msb_first=True)
        total_bits = len(data) * 8
        eob = alphabet - 1
        beats = []
        sel_i, group_left = 0, 0
        t = None
        while True:
            if group_left == 0:
                if sel_i >= len(selectors):
                    return {"beats": beats, "symbols": len(beats), "bits": None,
                            "sticky": ST_ESEL}
                if selectors[sel_i] >= len(tables):
                    return {"beats": beats, "symbols": len(beats), "bits": None,
                            "sticky": ST_ESEL}
                t = tables[selectors[sel_i]]
                sel_i += 1
                group_left = 50
            try:
                sym, l = t.decode(rd.peek(cm.MAXLEN_BZ2))
            except ValueError:
                return {"beats": beats, "symbols": len(beats), "bits": None,
                        "sticky": ST_ENOCODE}
            if rd.pos + l > total_bits:
                return {"beats": beats, "symbols": len(beats), "bits": None,
                        "sticky": ST_EUNDER}
            rd.consume(l)
            group_left -= 1
            if sym == eob:
                beats.append(((TYPE_EOB << 9) | sym, 1))
                if len(beats) > limit:
                    # EOB would be beat limit+1: limit hit first
                    return {"beats": beats[:limit], "symbols": limit, "bits": None,
                            "sticky": ST_ELIMIT}
                return {"beats": beats, "symbols": len(beats),
                        "bits": rd.pos - start_bit, "sticky": ST_DONE}
            beats.append((sym, 0))
            if len(beats) > limit:
                return {"beats": beats[:limit], "symbols": limit, "bits": None,
                        "sticky": ST_ELIMIT}

    # ---- the replay -----------------------------------------------------------------
    def check_phase(self):
        axi = self._drain(self.axi_fifo)
        bits_beats = self._drain(self.bits_fifo)
        sel_beats = self._drain(self.sel_fifo)
        sym_beats = self._drain(self.sym_fifo)

        mirror = {}
        sticky = 0                # model of STATUS[15:1]
        busy = False
        inv = None                # open invocation expectations
        aborted = False
        sym_i = 0
        golden_name = "canonical_model (Table/BitReader step predictor)"
        # doorbell times split the beat streams (B4)
        db_times = [x.t for x in axi if x.kind == "write" and x.addr == CTRL and (x.data & 1)]

        def beats_of_invocation(stream, t0, t1):
            return [b for b in stream if t0 <= b.t < t1]

        for item in axi:
            if item.kind == "reset":
                mirror.clear()
                sticky, busy, inv, aborted = 0, False, None, False
                continue
            if item.kind == "write":
                if item.addr == CTRL:
                    if item.data & 2:                      # ABORT (priority over doorbell)
                        if busy:
                            aborted = True
                        continue
                    if not (item.data & 1):
                        continue
                    if busy:
                        sticky |= ST_EBUSY                 # rejected doorbell
                        cov("cg_err", "busy")
                        continue
                    # acceptance checks
                    if self._param_error(mirror):
                        sticky |= ST_EPARAM
                        cov("cg_err", "param")
                        continue
                    if self._table_error_doorbell(mirror):
                        sticky |= ST_ETABLE
                        cov("cg_err", "table.badlen")
                        continue
                    # accepted: reconstruct this invocation's streams by time (B4). The
                    # window opens a little BEFORE the doorbell's B-handshake timestamp:
                    # tready rises at PREP, which can precede the B response by a few
                    # cycles; earlier beats are impossible (tready 0 from DONE/ERR to the
                    # next accepted doorbell, MAS §5).
                    t0 = item.t - 100.0
                    later = [t for t in db_times if t > item.t]
                    t1 = (later[0] - 100.0) if later else float("inf")
                    data = self._bytes_of(beats_of_invocation(bits_beats, t0, t1))
                    sels = [b.data & 7 for b in beats_of_invocation(sel_beats, t0, t1)]
                    alphabet = mirror.get(ALPHABET, 0) & 0x1FF
                    n_tables = mirror.get(N_TABLES, 0) & 0x7
                    lengths = self._lengths_from_mirror(mirror, n_tables, alphabet)
                    inv = self._predict(data, mirror.get(START_BIT, 0), lengths, sels,
                                        alphabet, mirror.get(SYMBOL_LIMIT, 0))
                    inv["t0"] = t0
                    busy = True
                    aborted = False
                    cov("cg_cfg", f"n_tables.{n_tables}")
                    cov("cg_cfg", f"alphabet.{'288' if alphabet == 288 else '147' if alphabet == 147 else 'small' if alphabet <= 8 else 'mid'}")
                    cov("cg_bits", f"start_bit.{'zero' if mirror.get(START_BIT,0)==0 else 'mod32' if mirror.get(START_BIT,0)%32==0 else 'odd'}")
                elif item.addr == STATUS:
                    sticky &= ~(item.data & STICKY_MASK)   # W1C (allowed while BUSY)
                elif item.addr in (IRQ_EN, DBG_SEL):
                    mirror[item.addr] = item.data          # writable while BUSY (MAS)
                elif not busy and item.addr < LEN_TOP:
                    mirror[item.addr] = item.data          # BUSY-discarded otherwise (B5)
                continue
            # reads
            if item.addr == STATUS:
                if busy and not (item.data & ST_BUSY):
                    # completion (B6): fold the invocation outcome into the mirror
                    if aborted and not (item.data & ST_DONE):
                        # aborted before natural completion (DONE-wins otherwise, uArch N5):
                        # emitted beats must be an exact prefix of the predicted stream
                        pre = [b for b in sym_beats[sym_i:] if inv["t0"] <= b.t < item.t]
                        self._check(len(pre) <= len(inv["beats"]),
                                    f"abort: {len(pre)} beats > predicted {len(inv['beats'])}")
                        for k, g in enumerate(pre):
                            self._check(g.data == inv["beats"][k][0],
                                        f"abort prefix beat {k}: 0x{g.data:x} != "
                                        f"0x{inv['beats'][k][0]:x}")
                        sym_i += len(pre)
                        self.compared += len(pre)
                        sticky |= ST_ABORTED
                        cov("cg_ctrl", "abort")
                        busy, inv = False, None
                        self._sticky_check(item, sticky)
                        continue
                    outcome = inv["sticky"]
                    exp_beats = inv["beats"]
                    got = sym_beats[sym_i:sym_i + len(exp_beats)]
                    self._check(len(got) == len(exp_beats),
                                f"beat count: expected {len(exp_beats)} got {len(got)}")
                    for k, (g, (ed, el)) in enumerate(zip(got, exp_beats)):
                        self._check(g.data == ed and g.last == el,
                                    f"beat {k}: expected (0x{ed:x},{el}) got "
                                    f"(0x{g.data:x},{g.last})")
                    self.compared += len(got)
                    sym_i += len(got)
                    sticky |= outcome
                    inv["done_seen"] = True
                    for name, bit in (("done", ST_DONE), ("nocode", ST_ENOCODE),
                                      ("selector", ST_ESEL), ("limit", ST_ELIMIT),
                                      ("underrun", ST_EUNDER), ("table.kraft", ST_ETABLE)):
                        if outcome & bit:
                            cov("cg_err" if bit != ST_DONE else "cg_ctrl", name)
                    busy = False
                    self._completed = inv
                    inv = None
                self._sticky_check(item, sticky if not busy else sticky)
            elif not busy and getattr(self, "_completed", None):
                c = self._completed
                if item.addr == SYMBOLS:
                    self._check(item.data == c["symbols"],
                                f"SYMBOLS {item.data} != golden {c['symbols']}")
                elif item.addr == BITS and c["bits"] is not None:
                    self._check(item.data == c["bits"],
                                f"BITS {item.data} != golden {c['bits']}")

        self._check(sym_i == len(sym_beats),
                    f"{len(sym_beats) - sym_i} unexplained m_sym beats after replay")
        self.passed = self.errors == 0
        if self.passed:
            self.logger.info(
                f"scoreboard PASS: compared {self.compared} items, 0 mismatches "
                f"(golden={golden_name})")
        else:
            self.logger.error(f"scoreboard FAIL: {self.errors} errors")

    def _sticky_check(self, item, sticky):
        got = item.data & STICKY_MASK
        self._check(got == (sticky & STICKY_MASK),
                    f"STATUS sticky mismatch at t={item.t}: read 0x{got:x} "
                    f"!= model 0x{sticky & STICKY_MASK:x}")

    def report_phase(self):
        write_func_cov()
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

    def flush_sources(self):
        """MAS DMA rule: channels stopped and flushed before every doorbell — drop any
        un-accepted beats parked in the cocotbext sources (B4)."""
        for src in (self.bits_source, self.sel_source):
            try:
                src.clear()
            except AttributeError:
                pass

    def connect_phase(self):
        self.agent.monitor.ap.connect(self.scoreboard.export)
        self.bits_mon.ap.connect(self.scoreboard.bits_export)
        self.sel_mon.ap.connect(self.scoreboard.sel_export)
        self.sym_mon.ap.connect(self.scoreboard.sym_export)
