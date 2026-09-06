"""GrapeEnv + GrapeScoreboard (testplan.md §3/§4).

The scoreboard replays the monitored AXI stream in bus order in check_phase: it mirrors the
pending config registers and the full STATUS sticky set (DONE/ABORTED/ERR_BUSY/ERR_PARAM/FP_*),
runs golden `emulation.advance` at each accepted doorbell (never a re-implementation), replays
aborts from the DUT-reported STEPS_DONE (testplan §4), and compares every idle read bit-exactly.
Functional coverage (testplan §2 cg_*) accumulates process-wide across tests into
tb/cov/func_cov.txt.
"""
import os
import struct

from pyuvm import ConfigDB, uvm_scoreboard, uvm_tlm_analysis_fifo

from axi_lite_agent import AxiLiteAgent
from base_env import BaseEnv

# Register map (docs/mas.md §4)
CTRL, STATUS, IRQ_EN, IRQ_STATUS = 0x008, 0x00C, 0x010, 0x014
CYCLES_LO, CYCLES_HI, STEPS_DONE = 0x040, 0x044, 0x048
DT_LO, DT_HI, NSTEPS, NPAIRS = 0x100, 0x104, 0x108, 0x10C
BODY_BASE, BODY_STRIDE, PAIR_BASE = 0x200, 0x40, 0x400
N_BODIES, N_PAIRS_MAX = 5, 10
ST_BUSY, ST_DONE, ST_ABORTED = 1 << 0, 1 << 1, 1 << 2
ST_ERR_BUSY, ST_ERR_PARAM = 1 << 8, 1 << 9
FP_BITS = {12: "invalid", 13: "divzero", 14: "overflow", 15: "underflow"}
STICKY_MASK = ST_DONE | ST_ABORTED | ST_ERR_BUSY | ST_ERR_PARAM | sum(1 << b for b in FP_BITS)
K1 = 128

# process-wide functional coverage (all tests run in one simulation process)
FUNC_COV = {}


def cov(group, bin_name):
    FUNC_COV.setdefault(group, {})
    FUNC_COV[group][str(bin_name)] = FUNC_COV[group].get(str(bin_name), 0) + 1


def w2f(lo, hi):
    return struct.unpack("<d", struct.pack("<II", lo, hi))[0]


def f2w(x):
    x = float(x)
    if x != x:                                    # NaN: DUT canonicalizes to +qNaN (contract);
        return 0x00000000, 0x7FF80000             # golden numpy NaNs carry arbitrary sign/payload
    lo, hi = struct.unpack("<II", struct.pack("<d", x))
    return lo, hi


def nsteps_bin(n):
    if n in (0, 1, 2):
        return str(n)
    if n <= 10:
        return "3..10"
    if n == 20000:
        return "20000"
    if n == 0xFFFFFFFF:
        return "2^32-1"
    return "other"


class GrapeScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.fifo = uvm_tlm_analysis_fifo("fifo", self)
        self.export = self.fifo.analysis_export
        self.golden = ConfigDB().get(self, "", "golden")  # module with .advance
        self.k1_enforce = (ConfigDB().get(self, "", "k1_enforce")
                           if ConfigDB().exists(self, "", "k1_enforce") else False)
        self.compared = 0
        self.mismatches = 0
        self.runs = 0
        self.k1_worst = 0.0

    # ---- mirror state ------------------------------------------------------------------------
    def _reset_mirror(self):
        self.regs = {}            # word offset -> pending 32-bit value (config registers)
        self.busy = False
        self.sticky = 0           # expected STATUS sticky bits (incl. FP mirror)
        self.latched = None       # (dt, nsteps, npairs, pair_words) at accept
        self.steps_final = None   # expected STEPS_DONE once the run ended
        self.abort_sent = False
        self.aborted_wait_steps = False   # ABORTED seen; golden replay deferred to STEPS_DONE read

    def _cfg(self, off, default=0):
        return self.regs.get(off, default)

    def _bodies_from_mirror(self):
        bodies = []
        for i in range(N_BODIES):
            base = BODY_BASE + i * BODY_STRIDE
            vals = [w2f(self._cfg(base + 8 * f), self._cfg(base + 8 * f + 4))
                    for f in range(7)]
            bodies.append(([vals[0], vals[1], vals[2]], [vals[3], vals[4], vals[5]], vals[6]))
        return bodies

    def _params_ok(self):
        npairs = self._cfg(NPAIRS) & 0xFF
        if npairs > N_PAIRS_MAX:
            return False
        for k in range(npairs):
            pw = self._cfg(PAIR_BASE + 4 * k)
            if (pw & 0xFF) >= N_BODIES or ((pw >> 8) & 0xFF) >= N_BODIES:
                return False
        return True

    def _latch(self):
        self.latched = (w2f(self._cfg(DT_LO), self._cfg(DT_HI)), self._cfg(NSTEPS),
                        self._cfg(NPAIRS) & 0xFF,
                        [self._cfg(PAIR_BASE + 4 * k) for k in range(self._cfg(NPAIRS) & 0xFF)])

    def _advance_golden(self, steps):
        """Run golden for `steps` steps from the latched config; update expected BODY regs."""
        dt, _, _, pair_words = self.latched
        bodies = self._bodies_from_mirror()
        pairs = [(bodies[pw & 0xFF], bodies[(pw >> 8) & 0xFF]) for pw in pair_words]
        flags = self.golden.advance(dt, steps, bodies, pairs)
        for b, n in FP_BITS.items():
            if n in flags:
                self.sticky |= 1 << b
                cov("cg_fp_flags", n)
        for i, (r, v, m) in enumerate(bodies):
            base = BODY_BASE + i * BODY_STRIDE
            for f, val in enumerate((r[0], r[1], r[2], v[0], v[1], v[2], m)):
                lo, hi = f2w(val)
                self.regs[base + 8 * f] = lo
                self.regs[base + 8 * f + 4] = hi
        self.runs += 1

    # ---- checks ------------------------------------------------------------------------------
    def _check(self, ok, msg):
        self.compared += 1
        if not ok:
            self.mismatches += 1
            if self.mismatches <= 10:
                self.logger.error(f"mismatch: {msg}")

    def _on_ctrl_write(self, data):
        cov("cg_ctrl", f"{'DB' if data & 1 else ''}{'+AB' if data & 2 else ''}"
                       f"|{'busy' if self.busy else 'idle'}")
        if self.busy:
            if data & 2:
                self.abort_sent = True
            if data & 1:
                self.sticky |= ST_ERR_BUSY        # doorbell while BUSY (MAS §8)
                cov("cg_err", "ERR_BUSY.doorbell")
            return
        if data & 2:                              # ABORT wins over DB in the same write (idle)
            return
        if data & 1:
            if not self._params_ok():
                self.sticky |= ST_ERR_PARAM
                cov("cg_err", "ERR_PARAM")
                return
            self._latch()
            nsteps = self.latched[1]
            cov("cg_cfg", f"nsteps.{nsteps_bin(nsteps)}")
            cov("cg_cfg", f"npairs.{self.latched[2]}")
            for pw in self.latched[3]:
                cov("cg_pairs", f"{pw & 0xFF}-{(pw >> 8) & 0xFF}")
            if nsteps == 0:
                self.sticky |= ST_DONE            # immediate DONE (PRD-F8)
                self.steps_final = 0
                self._advance_golden(0)
            else:
                self.busy = True
                self.steps_final = None

    def _on_status_read(self, data):
        # Completion = live BUSY falls (sticky DONE/ABORTED can be stale from an un-W1C'd
        # earlier run — PRD-F12: sticky bits survive the doorbell).
        if self.busy and (data & ST_BUSY) == 0:
            self.busy = False
            if self.abort_sent and (data & ST_ABORTED):
                cov("cg_abort", "aborted")
                self.sticky |= ST_ABORTED
                self.aborted_wait_steps = True    # golden replay deferred to STEPS_DONE read
            else:
                if self.abort_sent:
                    cov("cg_abort", "done_wins")  # abort landed on boundary NSTEPS (MAS §8)
                self._check(bool(data & ST_DONE),
                            f"run ended without DONE 0x{data:05x}")
                self.sticky |= ST_DONE
                self.steps_final = self.latched[1]
                self._advance_golden(self.steps_final)
            self.abort_sent = False
        if not self.busy and not self.aborted_wait_steps:
            got = data & STICKY_MASK
            self._check(got == self.sticky,
                        f"STATUS sticky 0x{got:05x} != expected 0x{self.sticky:05x}")

    def _replay(self, items):
        self._reset_mirror()
        cfg_set = set([DT_LO, DT_HI, NSTEPS, NPAIRS]
                      + [BODY_BASE + i * BODY_STRIDE + 8 * f + w
                         for i in range(N_BODIES) for f in range(7) for w in (0, 4)]
                      + [PAIR_BASE + 4 * k for k in range(N_PAIRS_MAX)])
        for it in items:
            if it.kind == "reset":
                self._reset_mirror()
                cov("cg_reset", "mid_stream")
                continue
            if it.kind == "write":
                cov("cg_axi", f"wr.resp{it.resp}")
                if it.addr == CTRL:
                    self._on_ctrl_write(it.data)
                elif it.addr in cfg_set:
                    if self.busy:
                        self.sticky |= ST_ERR_BUSY
                        cov("cg_err", "ERR_BUSY.cfg_write")
                    elif it.strb == 0xF:
                        self.regs[it.addr] = it.data
                elif it.addr == STATUS:
                    self.sticky &= ~(it.data & STICKY_MASK)   # W1C
                    cov("cg_irq", "w1c")
            else:  # read
                cov("cg_axi", f"rd.resp{it.resp}")
                if it.addr == STATUS:
                    self._on_status_read(it.data)
                elif it.addr in cfg_set and not self.busy and not self.aborted_wait_steps:
                    exp = self._cfg(it.addr)
                    self._check(it.data == exp,
                                f"@0x{it.addr:03x}: read 0x{it.data:08x} expected 0x{exp:08x}")
                elif it.addr == STEPS_DONE and not self.busy:
                    if self.aborted_wait_steps:
                        self.aborted_wait_steps = False
                        nsteps = self.latched[1]
                        self._check(it.data <= nsteps,
                                    f"STEPS_DONE {it.data} > NSTEPS {nsteps} after abort")
                        cov("cg_abort", "steps.0" if it.data == 0 else
                            ("steps.final" if it.data == nsteps else "steps.mid"))
                        self.steps_final = min(it.data, nsteps)
                        self._advance_golden(self.steps_final)
                    elif self.steps_final is not None:
                        self._check(it.data == self.steps_final,
                                    f"STEPS_DONE {it.data} != {self.steps_final}")
                elif it.addr == CYCLES_LO and not self.busy and self.steps_final is not None:
                    if self.latched is not None and self.latched[1] == 0:
                        self._check(it.data <= 4, f"PRD-F8: NSTEPS=0 CYCLES {it.data} > 4")
                    elif self.steps_final:
                        per_step = it.data / self.steps_final
                        self.k1_worst = max(self.k1_worst, per_step)
                        if self.k1_enforce:
                            # K1 binds on the benchmark pair list (PRD KPI). Random lists with
                            # duplicate pairs build accumulate chains deeper than the static
                            # window and legitimately exceed it — recorded, not failed.
                            self._check(per_step <= K1,
                                        f"K1: {it.data}/{self.steps_final} = {per_step:.1f} > {K1}")

    def check_phase(self):
        items = []
        while self.fifo.can_get():
            ok, it = self.fifo.try_get()
            if ok:
                items.append(it)
        self._replay(items)
        assert self.compared > 0, "scoreboard: nothing compared"
        if self.mismatches == 0:
            self.logger.info(f"scoreboard: compared {self.compared} items, 0 mismatches "
                             f"(golden=emulation.advance, {self.runs} run(s), "
                             f"K1 worst {self.k1_worst:.1f})")

    def report_phase(self):
        cov_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cov")
        os.makedirs(cov_dir, exist_ok=True)
        with open(os.path.join(cov_dir, "func_cov.txt"), "w") as f:
            for g in sorted(FUNC_COV):
                for b in sorted(FUNC_COV[g]):
                    f.write(f"{g}.{b}: {FUNC_COV[g][b]}\n")
        assert self.mismatches == 0, f"scoreboard: {self.mismatches} mismatches"


class GrapeEnv(BaseEnv):
    def build_phase(self):
        super().build_phase()
        self.agent = AxiLiteAgent.create("agent", self)
        self.scoreboard = GrapeScoreboard.create("scoreboard", self)

    def connect_phase(self):
        self.agent.monitor.ap.connect(self.scoreboard.export)
