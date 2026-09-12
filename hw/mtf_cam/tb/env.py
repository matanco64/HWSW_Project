"""MtfEnv (testplan §5): AXI-Lite agent (grape/huffman pattern) + a cocotbext-axi symbol-stream
SOURCE on s_sym + an m_l stream SINK (with a pause generator for backpressure) + passive AXIS
monitors on both + MtfScoreboard.

Scoreboard (huffman replay pattern): it mirrors the AXI config writes (USED[0..7], SYMBOL_LIMIT,
BYTES_LIMIT, W/D from CAPS); at each accepted doorbell it reconstructs the symbol list from the
s_sym monitor stream (by timestamp window) and calls the FROZEN predictor `list_model.expand`
(golden/, never a re-implementation) for the expected L-byte vector; it reassembles the m_l beats
(tkeep-masked, lane 0 first) into a byte stream and compares EXACT to the predictor; it checks the
counters (SYMBOLS_IN, BYTES_OUT, MAX_RUN, INIT_CYCLES) and a sticky-STATUS mirror with BUSY-fall
completion (sticky DONE survives the completion read; W1C clears — the huffman S1 lesson). The
predictor is cross-checked against the golden `mtf_ref` once per benchmark block by the test.
"""
import os

from pyuvm import (ConfigDB, uvm_analysis_port, uvm_monitor, uvm_scoreboard,
                   uvm_sequence_item, uvm_tlm_analysis_fifo)

from cocotb.triggers import ReadOnly, RisingEdge
from cocotb.utils import get_sim_time

from axi_lite_agent import AxiLiteAgent
from base_env import BaseEnv

# ---- register map (MAS §4 EXACT byte offsets; proven against mtf_regs.sv word decode) ----
ID_REG, VERSION, CTRL, STATUS, IRQ_EN, IRQ_STATUS = 0x000, 0x004, 0x008, 0x00C, 0x010, 0x014
CYCLES_LO, CYCLES_HI, SYMBOLS_IN, BYTES_OUT, INIT_CYCLES, MAX_RUN = \
    0x040, 0x044, 0x048, 0x04C, 0x050, 0x054
SYMBOL_LIMIT, BYTES_LIMIT, CAPS, DBG_SEL, DBG_DATA = 0x100, 0x104, 0x108, 0x10C, 0x110
USED_BASE = 0x200                       # USED[w] = 0x200 + 4*w, w = 0..7

ST_BUSY, ST_DONE, ST_ABORTED = 1 << 0, 1 << 1, 1 << 2
ST_EBUSY, ST_EPARAM, ST_ERANK = 1 << 8, 1 << 9, 1 << 10
ST_ERUN, ST_ELIMIT, ST_EUNDER = 1 << 11, 1 << 12, 1 << 13
STICKY_MASK = 0x3F06                    # DONE|ABORTED + err bits 8..13 (W1C); bit 0 = live BUSY

# ADR-0006 symbol beat: value = tdata[8:0], TYPE = tdata[11:9]
TYPE_MTF, TYPE_EOB = 0, 3


def make_beat(value, is_eob):
    """Build the 32-bit ADR-0006 s_sym beat for a raw symbol value."""
    typ = TYPE_EOB if is_eob else TYPE_MTF
    return (typ << 9) | (value & 0x1FF)


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
    """Passive AXIS monitor (huffman pattern): publishes every tvalid&&tready beat; X on any
    sampled field of an accepted beat asserts (vacuous on 2-state Verilator, armed on Icarus)."""

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
        lanes = max(1, len(tdata) // 8)
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


class MtfScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.axi_fifo = uvm_tlm_analysis_fifo("axi_fifo", self)
        self.sym_fifo = uvm_tlm_analysis_fifo("sym_fifo", self)
        self.l_fifo = uvm_tlm_analysis_fifo("l_fifo", self)
        self.export = self.axi_fifo.analysis_export
        self.sym_export = self.sym_fifo.analysis_export
        self.l_export = self.l_fifo.analysis_export
        self.predictor = ConfigDB().get(self, "", "predictor")   # list_model module
        self.W = ConfigDB().get(self, "", "W") if ConfigDB().exists(self, "", "W") else 8
        self.errors = 0
        self.compared = 0
        self.blocks = 0
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
            if self.errors <= 30:
                self.logger.error(msg)

    def _used_from_mirror(self, mirror):
        used = [False] * 256
        for w in range(8):
            word = mirror.get(USED_BASE + 4 * w, 0)
            for b in range(32):
                if word & (1 << b):
                    used[32 * w + b] = True
        return used

    @staticmethod
    def _bytes_of(beats, W):
        """Bytes carried by an m_l beat list (tkeep-masked, contiguous lane 0 first)."""
        out = bytearray()
        for beat in beats:
            for lane in range(W):
                if beat.keep & (1 << lane):
                    out.append((beat.data >> (8 * lane)) & 0xFF)
        return bytes(out)

    def _check_beat_shape(self, beats, n_bytes, W):
        """Every beat but the last carries W bytes (TKEEP all ones, no TLAST); the last beat
        carries the remainder contiguous from lane 0 with TLAST (uArch S3)."""
        rem = n_bytes % W
        exp_beats = n_bytes // W + (1 if rem else 0)
        full = (1 << W) - 1
        self._check(len(beats) == exp_beats,
                    f"m_l beat count: expected {exp_beats} got {len(beats)}")
        for i, beat in enumerate(beats):
            last = (i == len(beats) - 1)
            if last:
                exp_keep = full if rem == 0 else (1 << rem) - 1
                self._check(beat.keep == exp_keep,
                            f"m_l last beat TKEEP 0x{beat.keep:x} != 0x{exp_keep:x}")
                self._check(beat.last == 1, f"m_l last beat TLAST={beat.last} != 1")
            else:
                self._check(beat.keep == full,
                            f"m_l beat {i} TKEEP 0x{beat.keep:x} != full 0x{full:x}")
                self._check(beat.last == 0, f"m_l non-last beat {i} TLAST={beat.last} != 0")

    # ---- the replay -----------------------------------------------------------------
    def check_phase(self):
        axi = self._drain(self.axi_fifo)
        sym_beats = self._drain(self.sym_fifo)
        l_beats = self._drain(self.l_fifo)
        W = self.W
        golden_name = "list_model.expand"

        db_times = [x.t for x in axi
                    if x.kind == "write" and x.addr == CTRL and (x.data & 1) and not (x.data & 2)]

        def in_window(stream, t0, t1):
            return [b for b in stream if t0 <= b.t < t1]

        mirror = {}
        sticky = 0
        busy = False
        inv = None
        completed = None

        for item in axi:
            if item.kind == "reset":
                mirror.clear()
                sticky, busy, inv, completed = 0, False, None, None
                continue

            if item.kind == "write":
                if item.addr == CTRL:
                    if item.data & 2:                       # ABORT — out of bring-up scope
                        continue
                    if not (item.data & 1):
                        continue
                    if busy:
                        sticky |= ST_EBUSY
                        cov("cg_err", "busy")
                        continue
                    # accepted doorbell: open the invocation, window its streams by time
                    t0 = item.t
                    later = [t for t in db_times if t > item.t]
                    t1 = later[0] if later else float("inf")
                    symbols = [b.data & 0x1FF for b in in_window(sym_beats, t0, t1)]
                    used = self._used_from_mirror(mirror)
                    n_used = sum(used)
                    alphabet = n_used + 2
                    l_bytes, events = self.predictor.expand(symbols, used, alphabet)
                    max_run = max((e[1] for e in events if e[0] == "run"), default=0)
                    inv = dict(t0=t0, t1=t1, symbols=symbols, l_bytes=l_bytes,
                               n_used=n_used, alphabet=alphabet, max_run=max_run)
                    busy = True
                    cov("cg_block", f"n_used.{n_used}")
                    cov("cg_block", "eob")
                    if max_run:
                        cov("cg_run", "present")
                    continue
                if item.addr == STATUS:
                    sticky &= ~(item.data & STICKY_MASK)    # W1C
                elif not busy:
                    mirror[item.addr] = item.data           # config latched at doorbell
                continue

            # reads
            if item.addr == STATUS:
                if busy and not (item.data & ST_BUSY):
                    # BUSY-fall completion: compare the invocation's m_l beats to the predictor
                    beats = in_window(l_beats, inv["t0"], inv["t1"])
                    got = self._bytes_of(beats, W)
                    self._check(got == inv["l_bytes"],
                                f"m_l byte stream mismatch: got {len(got)} B, "
                                f"expected {len(inv['l_bytes'])} B "
                                f"(first diff at "
                                f"{next((i for i in range(min(len(got), len(inv['l_bytes']))) if got[i] != inv['l_bytes'][i]), 'len')})")
                    self._check_beat_shape(beats, len(inv["l_bytes"]), W)
                    self.compared += len(got)
                    self.blocks += 1
                    sticky |= ST_DONE
                    inv["symbols_in"] = len(inv["symbols"])
                    inv["bytes_out"] = len(inv["l_bytes"])
                    inv["init_cycles"] = inv["n_used"]
                    completed = inv
                    busy = False
                    inv = None
                    cov("cg_ctrl", "done")
                got = item.data & STICKY_MASK
                self._check(got == (sticky & STICKY_MASK),
                            f"STATUS sticky mismatch at t={item.t}: read 0x{got:x} "
                            f"!= model 0x{sticky & STICKY_MASK:x}")
            elif not busy and completed is not None:
                c = completed
                if item.addr == SYMBOLS_IN:
                    self._check(item.data == c["symbols_in"],
                                f"SYMBOLS_IN {item.data} != golden {c['symbols_in']}")
                elif item.addr == BYTES_OUT:
                    self._check(item.data == c["bytes_out"],
                                f"BYTES_OUT {item.data} != golden {c['bytes_out']}")
                elif item.addr == MAX_RUN:
                    self._check(item.data == c["max_run"],
                                f"MAX_RUN {item.data} != golden {c['max_run']}")
                elif item.addr == INIT_CYCLES:
                    self._check(item.data == c["init_cycles"],
                                f"INIT_CYCLES {item.data} != golden {c['init_cycles']} (N_USED)")

        self.passed = self.errors == 0
        if self.passed:
            self.logger.info(
                f"scoreboard PASS: compared {self.compared} items over {self.blocks} block(s), "
                f"0 mismatches (golden={golden_name})")
        else:
            self.logger.error(f"scoreboard FAIL: {self.errors} errors")

    def report_phase(self):
        write_func_cov()
        assert self.passed, f"scoreboard: {self.errors} mismatches"


class MtfEnv(BaseEnv):
    """AXI agent + s_sym/m_l passive monitors + cocotbext stream source/sink + scoreboard."""

    def build_phase(self):
        super().build_phase()
        self.agent = AxiLiteAgent.create("agent", self)
        ConfigDB().set(self, "sym_mon", "sym_mon_prefix", "s_axis_sym")
        ConfigDB().set(self, "l_mon", "l_mon_prefix", "m_axis_l")
        self.sym_mon = AxisMonitor.create("sym_mon", self)
        self.l_mon = AxisMonitor.create("l_mon", self)
        self.scoreboard = MtfScoreboard.create("scoreboard", self)
        from cocotbext.axi import AxiStreamBus, AxiStreamSink, AxiStreamSource
        dut = ConfigDB().get(self, "", "dut")
        clk = ConfigDB().get(self, "", "clk")
        rst_n = ConfigDB().get(self, "", "rst_n")
        self.sym_source = AxiStreamSource(
            AxiStreamBus.from_prefix(dut, "s_axis_sym"), clk, rst_n, reset_active_level=False)
        self.l_sink = AxiStreamSink(
            AxiStreamBus.from_prefix(dut, "m_axis_l"), clk, rst_n, reset_active_level=False)

    def connect_phase(self):
        self.agent.monitor.ap.connect(self.scoreboard.export)
        self.sym_mon.ap.connect(self.scoreboard.sym_export)
        self.l_mon.ap.connect(self.scoreboard.l_export)
