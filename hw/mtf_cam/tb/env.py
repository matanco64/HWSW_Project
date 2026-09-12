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


def write_func_cov(path=None):
    # Absolute path anchored on this file so the report lands in the real tb/cov/ no matter
    # which build dir cocotb runs the test from (sim runs cwd = sim_build*/).
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cov", "func_cov.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for k in sorted(FUNC_COV):
            f.write(f"{k} {FUNC_COV[k]}\n")


# ---- doorbell-time ERR_PARAM model (mirrors mtf_regs.sv err_param, MAS §4 / F-09) ----------
SYM_MAX = 1 << 27                       # SYMBOL_LIMIT ceiling (mtf_regs SYM_MAX = 0x0800_0000)
BYT_MAX = 1 << 30                       # BYTES_LIMIT  ceiling (mtf_regs BYT_MAX = 0x4000_0000)
RUN_MAX = 1 << 20                       # run overflow threshold (mtf_run RUN_MAX)


def err_param(n_used, sym_lim, byt_lim):
    """True iff a doorbell would be rejected with ERR_PARAM (F-09 clauses)."""
    return (n_used == 0
            or sym_lim == 0 or sym_lim > SYM_MAX
            or byt_lim == 0 or byt_lim > BYT_MAX)


def compute_outcome(predictor, sym_typed, used, n_used, alphabet, sym_lim, byt_lim):
    """Replay one accepted invocation to the DUT's terminal outcome, WITHOUT re-implementing the
    MTF/run algorithm: the byte VALUES always come from the frozen predictor `list_model.expand`;
    this walk only locates the stop point (which runtime error, at which beat) and the beat shape,
    exactly as the RTL detects them (mtf_ctrl per-symbol errors + mtf_cam ERR_LIMIT gate), which
    the testplan §2.1 sanctions the scoreboard to derive for the limit/underrun/bad-EOB cases the
    frozen model has no argument for. Returns a dict outcome.

    sym_typed: list of (value, type, tlast) for the invocation's s_sym beats, in order.
    """
    eob_val = n_used + 1
    run = 0
    k = 0
    committed = 0
    err_bit = None
    e = None
    done = False
    # per-group run composition for cg_run.kind
    grp_syms = 0
    grp_runa = False
    grp_runb = False
    cov_events = []                     # (tag, payload) drained into functional coverage after

    for i, (v, typ, last) in enumerate(sym_typed):
        is_type0 = (typ == 0)
        is_type3 = (typ == 3)
        is_run = is_type0 and v <= 1
        valid_type0 = is_type0 and v <= n_used
        valid_eob = is_type3 and v == eob_val
        is_mtf = valid_type0 and v >= 2

        # --- error detection, in the RTL's priority order (mtf_ctrl §per-symbol) ---
        if last and not is_type3:
            err_bit, e = ST_EUNDER, i
            cov_events.append(("err", "underrun"))
            break
        if not valid_type0 and not valid_eob:
            err_bit, e = ST_ERANK, i
            if run > 0:                     # F-23: a run pending when ERR_RANK fires (discarded)
                cov_events.append(("enq", "rank_run_pending"))
            # classify the bad symbol for cg_block / cg_errrt
            if is_type3:
                cov_events.append(("badeob", "type3_badval"))
            elif is_type0 and v == eob_val:
                cov_events.append(("badeob", "type0_eobval"))
            elif typ in (1, 2):
                cov_events.append(("badeob", "type12"))
            else:
                cov_events.append(("rank", "gt_nused"))
            cov_events.append(("err", "rank"))
            break
        if is_run:
            incr = (1 << k) * (1 + v)
            s = run + incr
            if s > RUN_MAX:
                err_bit, e = ST_ERUN, i
                cov_events.append(("err", "run"))
                break
        if not valid_eob and sym_lim != 0 and (i + 1) == sym_lim:
            err_bit, e = ST_ELIMIT, i
            cov_events.append(("err", "limit_sym"))
            break
        if is_mtf:
            i0 = run if run > 0 else 1
            c1 = committed + i0
            i1 = 1 if run > 0 else 0
            if c1 > byt_lim or (i1 and c1 + i1 > byt_lim):
                err_bit, e = ST_ELIMIT, i
                cov_events.append(("err", "limit_byte"))
                break
        elif valid_eob and run > 0:
            if committed + run > byt_lim:
                err_bit, e = ST_ELIMIT, i
                cov_events.append(("err", "limit_byte"))
                break

        # --- clean beat: apply effects, collect coverage ---
        if is_run:
            run = s
            k += 1
            grp_syms += 1
            if v == 0:
                grp_runa = True
            else:
                grp_runb = True
        elif is_mtf:
            if run > 0:
                cov_events.append(("run_group", (run, grp_syms, grp_runa, grp_runb, "mtf")))
                committed += run
                run = 0
                k = 0
                grp_syms = 0
                grp_runa = grp_runb = False
            committed += 1
            cov_events.append(("mtf", v - 1))
        elif valid_eob:
            if run > 0:
                cov_events.append(("run_group", (run, grp_syms, grp_runa, grp_runb, "eob")))
                committed += run
            cov_events.append(("eob_ok", i))
            done, e = True, i
            break

    if e is None:
        e = len(sym_typed)              # stream exhausted with no EOB / error (open invocation)

    values = [v for (v, _t, _l) in sym_typed]
    cut = e + 1 if done else e
    out_bytes, events = predictor.expand(values[:cut], used, alphabet)
    max_run = max((ev[1] for ev in events if ev[0] == "run"), default=0)

    return dict(out_bytes=out_bytes, err_bit=err_bit, done=done,
                symbols_in=min(e + 1, len(sym_typed)), bytes_out=len(out_bytes),
                max_run=max_run, n_used=n_used, cov_events=cov_events,
                e=e, total=len(sym_typed))


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


class MtfProbe(uvm_monitor):
    """Read-only internal-signal probe (rtl/ untouched): samples the ctrl FSM state, the item
    FIFO occupancy and the 2-wide enqueue / beat-withdrawal control each cycle to close the
    covergroups (cg_fsm, cg_fifo, cg_enq, cg_xinv) that the passive port monitors cannot see.
    Every access is guarded so a build that optimises a signal away degrades gracefully."""

    _ST = {0: "idle", 1: "init", 2: "decode", 3: "drain"}

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "dut")
        self.clk = ConfigDB().get(self, "", "clk")
        self.rst_n = ConfigDB().get(self, "", "rst_n")

    def _get(self, path):
        obj = self.dut
        try:
            for part in path.split("."):
                obj = getattr(obj, part)
            return obj
        except AttributeError:
            return None

    async def run_phase(self):
        st = self._get("u_ctrl.state_q")
        cnt = self._get("u_fifo.cnt_q")
        wa = self._get("fifo_wr_a_en")
        wb = self._get("fifo_wr_b_en")
        disc = self._get("pack_discard")
        rc = self._get("run_commit")
        mvalid = self._get("m_axis_l_tvalid")
        mready = self._get("m_axis_l_tready")
        sym_tr = self._get("s_axis_sym_tready")
        abort = self._get("abort_req")
        cov("cg_probe", "attached" if st is not None else "detached")
        prev = None
        in_reset = False
        stall = 0
        while True:
            await RisingEdge(self.clk)
            await ReadOnly()
            if not self.rst_n.value.is_resolvable or int(self.rst_n.value) == 0:
                if not in_reset and prev is not None:       # reset-in-state (F-16 cg_reset)
                    cov("cg_reset", f"at_{self._ST.get(prev, prev)}")
                in_reset = True
                prev = None
                stall = 0
                continue
            in_reset = False

            def iv(sig):
                return int(sig.value) if (sig is not None and sig.value.is_resolvable) else None

            s = iv(st)
            if s is not None:
                cov("cg_fsm", f"state_{self._ST.get(s, s)}")
                if prev is not None and prev != s:
                    cov("cg_fsm", f"arc_{self._ST.get(prev, prev)}_{self._ST.get(s, s)}")
                prev = s
                if s == 1 and iv(sym_tr) == 0:              # F-04: s_sym.tready held 0 during INIT
                    cov("cg_init", "tready0_init")
                if iv(abort) and s != 0:                    # F-11 abort honoured in a non-idle state
                    cov("cg_ctrl", f"abort_{self._ST.get(s, s)}")

            # cg_pack stall length: consecutive cycles m_l valid but not ready
            if iv(mvalid) and not iv(mready):
                stall += 1
            else:
                if stall == 1:
                    cov("cg_pack", "stall_1")
                elif 2 <= stall <= 10:
                    cov("cg_pack", "stall_2_10")
                elif stall > 10:
                    cov("cg_pack", "stall_long")
                stall = 0

            c = iv(cnt)
            if c is not None:
                cov("cg_fifo", f"occ_{c}")
                d = self.D
                if c >= d - 1:
                    cov("cg_fifo", "full_stall")
                if c == 0:
                    cov("cg_fifo", "empty")

            a, b = iv(wa), iv(wb)
            if a:
                if b:
                    cov("cg_enq", "two_wide")
                else:
                    cov("cg_enq", "single")
                if iv(rc):
                    cov("cg_enq", "run_commit")
            if iv(disc):
                cov("cg_xinv", "discard")
                if iv(mvalid):
                    cov("cg_xinv", "discard_pending_beat")

    @property
    def D(self):
        return 8


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

    def _check_beat_shape(self, beats, n_bytes, W, done=True):
        """Normal drain (done): every beat but the last carries W bytes (TKEEP all ones, no
        TLAST); the last beat is the remainder contiguous from lane 0 WITH TLAST (uArch S3;
        exact multiple -> full last beat + TLAST). Error/abort flush (done=False): the residual
        partial beat carries NO TLAST and every beat has TLAST=0 (F-10)."""
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
                self._check(beat.last == (1 if done else 0),
                            f"m_l last beat TLAST={beat.last} != {1 if done else 0} (done={done})")
            else:
                self._check(beat.keep == full,
                            f"m_l beat {i} TKEEP 0x{beat.keep:x} != full 0x{full:x}")
                self._check(beat.last == 0, f"m_l non-last beat {i} TLAST={beat.last} != 0")

    # ---- functional coverage helpers ------------------------------------------------
    @staticmethod
    def _cover_errparam(n_used, sym_lim, byt_lim):
        if n_used == 0:
            cov("cg_errparam", "n_used0")
        if sym_lim == 0:
            cov("cg_errparam", "symlim0")
        if sym_lim > SYM_MAX:
            cov("cg_errparam", "symlim_hi")
        if byt_lim == 0:
            cov("cg_errparam", "bytlim0")
        if byt_lim > BYT_MAX:
            cov("cg_errparam", "bytlim_hi")

    @staticmethod
    def _cover_invocation(oc):
        n_used = oc["n_used"]
        for tag, payload in oc["cov_events"]:
            if tag == "mtf":
                r = payload
                if r in (1, 2, 3, 17, 62, 144):
                    cov("cg_rank", f"r{r}")
                if r == n_used - 1:
                    cov("cg_rank", "r_top")
            elif tag == "run_group":
                n, syms, runa, runb, term = payload
                if runa and runb:
                    cov("cg_run", "kind_mixed")
                elif runa:
                    cov("cg_run", "kind_runa")
                elif runb:
                    cov("cg_run", "kind_runb")
                if n in (1, 2, 8157, RUN_MAX):
                    cov("cg_run", {1: "n_1", 2: "n_2", 8157: "n_8157",
                                   RUN_MAX: "n_2p20"}[n])
                cov("cg_run", f"term_{term}")
                if syms == 1:
                    cov("cg_run", "grp_1")
                elif syms == 2:
                    cov("cg_run", "grp_2")
                elif syms <= 5:
                    cov("cg_run", "grp_3_5")
                elif syms <= 12:
                    cov("cg_run", "grp_6_12")
                else:
                    cov("cg_run", "grp_13_20")
                if n >= 2:
                    cov("cg_maxrun", "present")
            elif tag == "eob_ok":
                cov("cg_block", "eob_ok")
            elif tag == "badeob":
                cov("cg_block", f"eob_{payload}")
            elif tag == "enq":
                cov("cg_enq", payload)
            elif tag == "rank" and payload == "gt_nused":
                cov("cg_errrt", "rank_gt_nused")
            elif tag == "err":
                cov("cg_errrt", payload)
                pos = oc["e"]                       # clean beats accepted before the erroring one
                if pos == 0:
                    cov("cg_errrt", "pos_first")
                elif pos <= 8:
                    cov("cg_errrt", "pos_mid")
                else:
                    cov("cg_errrt", "pos_near_eob")

    @staticmethod
    def _cover_pack(beats, n_bytes, W, done):
        if not beats:
            return
        full = (1 << W) - 1
        if beats[-1].keep == full:
            cov("cg_pack", "last_full")
        else:
            cov("cg_pack", "last_partial")

    def _accepted_doorbell_times(self, axi):
        """Times of doorbells that actually open an invocation (not BUSY-rejected, not
        ERR_PARAM), mirroring the main replay's accept condition."""
        times = []
        busy = False
        mirror = {}
        for item in axi:
            if item.kind == "reset":
                busy = False
                mirror.clear()
                continue
            if item.kind == "write":
                if item.addr == CTRL:
                    if item.data & 2:           # ABORT: not a boundary (busy clears at BUSY-fall)
                        continue
                    if not (item.data & 1):
                        continue
                    if busy:
                        continue                # ERR_BUSY: not a boundary
                    n_used = sum(self._used_from_mirror(mirror))
                    if err_param(n_used, mirror.get(SYMBOL_LIMIT, 0),
                                 mirror.get(BYTES_LIMIT, 0)):
                        continue                # ERR_PARAM: idle, no symbols cross it
                    times.append(item.t)
                    busy = True
                elif item.addr != STATUS and not busy:
                    mirror[item.addr] = item.data
                continue
            if item.addr == STATUS and busy and not (item.data & ST_BUSY):
                busy = False                    # BUSY-fall completion (DONE or error)
        return times

    # ---- the replay -----------------------------------------------------------------
    def check_phase(self):
        axi = self._drain(self.axi_fifo)
        sym_beats = self._drain(self.sym_fifo)
        l_beats = self._drain(self.l_fifo)
        W = self.W
        golden_name = "list_model.expand"

        # Real invocation boundaries are the ACCEPTED doorbells only: a doorbell rejected because
        # BUSY (ERR_BUSY) or ERR_PARAM opens no invocation and must NOT truncate the open
        # invocation's symbol window (a late-accepted EOB would otherwise fall out — the huffman
        # RandBusySeq lesson). Pre-pass the stream tracking busy (busy-fall via a STATUS read) to
        # collect the accepted-doorbell times used as window ends.
        db_times = self._accepted_doorbell_times(axi)

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
                cov("cg_reset", "reset_seen")
                continue

            if item.kind == "write":
                if item.resp:                               # cg_axi write resp bin
                    cov("cg_axi", "wr_slverr")
                else:
                    cov("cg_axi", "wr_okay")
                if item.addr == CTRL:
                    if item.data & 2:                       # ABORT (F-11): wins over doorbell
                        if busy and inv is not None:
                            # abort has <= 8-cycle latency; ABORTED is set at the BUSY-fall read
                            inv["aborting"] = True
                            cov("cg_ctrl", "abort")
                        # abort while idle is a no-op (MAS §8)
                        continue
                    if not (item.data & 1):
                        continue
                    if busy:
                        sticky |= ST_EBUSY
                        cov("cg_errrt", "busy")
                        cov("cg_ctrl", "err_busy")
                        continue
                    used = self._used_from_mirror(mirror)
                    n_used = sum(used)
                    sym_lim = mirror.get(SYMBOL_LIMIT, 0)
                    byt_lim = mirror.get(BYTES_LIMIT, 0)
                    if err_param(n_used, sym_lim, byt_lim):
                        # doorbell rejected: sticky ERR_PARAM, no BUSY, no invocation (F-09)
                        sticky |= ST_EPARAM
                        self._cover_errparam(n_used, sym_lim, byt_lim)
                        continue
                    # accepted doorbell: open the invocation, window its streams by time
                    t0 = item.t
                    later = [t for t in db_times if t > item.t]
                    t1 = later[0] if later else float("inf")
                    sym_typed = [(b.data & 0x1FF, (b.data >> 9) & 0x7, b.last)
                                 for b in in_window(sym_beats, t0, t1)]
                    alphabet = n_used + 2
                    oc = compute_outcome(self.predictor, sym_typed, used, n_used, alphabet,
                                         sym_lim, byt_lim)
                    oc.update(t0=t0, t1=t1)
                    inv = oc
                    busy = True
                    cov("cg_init", f"n_used.{n_used}")
                    self._cover_invocation(oc)
                    continue
                if item.addr == STATUS:
                    if item.data & STICKY_MASK:
                        cov("cg_ctrl", "w1c")
                    sticky &= ~(item.data & STICKY_MASK)    # W1C
                elif busy:
                    # a config write to SYMBOL_LIMIT/BYTES_LIMIT/USED while BUSY is ignored and sets
                    # ERR_BUSY (mtf_regs); IRQ_EN/DBG_SEL are writable while BUSY (no ERR_BUSY)
                    if (item.addr in (SYMBOL_LIMIT, BYTES_LIMIT)
                            or USED_BASE <= item.addr <= USED_BASE + 28):
                        sticky |= ST_EBUSY
                        cov("cg_ctrl", "err_busy_cfg")
                else:
                    mirror[item.addr] = item.data           # config latched at doorbell
                continue

            # reads
            if item.resp:                                   # cg_axi read resp bin
                cov("cg_axi", "rd_slverr")
            else:
                cov("cg_axi", "rd_okay")
            if item.addr == CAPS:
                w = item.data & 0xFF
                cov("cg_caps", f"w.{w}")
                cov("cg_caps", f"d.{(item.data >> 8) & 0xFF}")
                cov("cg_caps", f"n_list.{(item.data >> 16) & 0x1FF}")
            if item.addr in (SYMBOLS_IN, BYTES_OUT, MAX_RUN, INIT_CYCLES,
                             CYCLES_LO, CYCLES_HI):
                cov("cg_counters", "read_busy" if busy else "read_idle")
            if item.addr == STATUS:
                if busy and inv is not None and inv.get("aborting") and not (item.data & ST_BUSY):
                    # aborted invocation: ABORTED sticky, emitted bytes timing-dependent (the pipe
                    # is flushed mid-flight) so not compared; no reliable counters
                    sticky |= ST_ABORTED
                    busy = False
                    inv = None
                    completed = None
                elif busy and not (item.data & ST_BUSY):
                    # BUSY-fall completion: compare the invocation's m_l beats to the model
                    beats = in_window(l_beats, inv["t0"], inv["t1"])
                    got = self._bytes_of(beats, W)
                    exp = inv["out_bytes"]
                    if inv["done"]:
                        # normal drain: the whole L-vector is emitted, byte-exact + TLAST (S3)
                        self._check(got == exp,
                                    f"m_l byte stream mismatch: got {len(got)} B, expected "
                                    f"{len(exp)} B (first diff at "
                                    f"{next((i for i in range(min(len(got), len(exp))) if got[i] != exp[i]), 'len')})")
                        self._check_beat_shape(beats, len(exp), W, done=True)
                        inv["bytes_out"] = len(exp)
                        sticky |= ST_DONE
                        cov("cg_ctrl", "done")
                        cov("cg_block", "donelat_1cyc")
                        if len(exp) == 0:
                            cov("cg_empty", "eob_first")
                    else:
                        # error flush (F-10 / M3): bytes already handshaken stay and must be a
                        # correct prefix of the golden L-vector; the FIFO+expander in-flight
                        # bytes and any pending run are DISCARDED (so the emitted length is a
                        # timing-dependent prefix, never longer than golden), and the residual
                        # partial beat carries NO TLAST. BYTES_OUT self-consistency is checked
                        # below against the observed handshaked count.
                        self._check(got == exp[:len(got)],
                                    f"error-flush bytes are not a prefix of the golden L-vector "
                                    f"(got {len(got)} B; first diff at "
                                    f"{next((i for i in range(len(got)) if i >= len(exp) or got[i] != exp[i]), 'len')})")
                        self._check(len(got) <= len(exp),
                                    f"error-flush emitted {len(got)} B > golden {len(exp)} B")
                        self._check_beat_shape(beats, len(got), W, done=False)
                        inv["bytes_out"] = len(got)
                        sticky |= inv["err_bit"]
                    self.compared += len(got)
                    self.blocks += 1
                    self._cover_pack(beats, inv["bytes_out"], W, inv["done"])
                    inv["init_cycles"] = inv["n_used"]
                    completed = inv
                    busy = False
                    inv = None
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
        self.probe = MtfProbe.create("probe", self)
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
