"""GrapeEnv + GrapeScoreboard (testplan.md §3/§4).

The scoreboard replays the monitored AXI stream in bus order in check_phase: it mirrors the
pending config registers, runs golden `emulation.advance` at each accepted doorbell (never a
re-implementation), and compares every idle BODY-window / STEPS_DONE / STATUS read against the
mirror bit-exactly. CYCLES_LO reads after DONE are checked against K1 = 128 cycles/step.
"""
import struct

from pyuvm import ConfigDB, uvm_scoreboard, uvm_tlm_analysis_fifo

from axi_lite_agent import AxiLiteAgent
from base_env import BaseEnv

# Register map (docs/mas.md §4)
CTRL, STATUS, IRQ_EN = 0x008, 0x00C, 0x010
CYCLES_LO, CYCLES_HI, STEPS_DONE = 0x040, 0x044, 0x048
DT_LO, DT_HI, NSTEPS, NPAIRS = 0x100, 0x104, 0x108, 0x10C
BODY_BASE, BODY_STRIDE, PAIR_BASE = 0x200, 0x40, 0x400
N_BODIES, N_PAIRS_MAX = 5, 10
ST_BUSY, ST_DONE, ST_ABORTED = 1 << 0, 1 << 1, 1 << 2
FP_BITS = {12: "invalid", 13: "divzero", 14: "overflow", 15: "underflow"}
K1 = 128


def w2f(lo, hi):
    return struct.unpack("<d", struct.pack("<II", lo, hi))[0]


def f2w(x):
    lo, hi = struct.unpack("<II", struct.pack("<d", float(x)))
    return lo, hi


class GrapeScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.fifo = uvm_tlm_analysis_fifo("fifo", self)
        self.export = self.fifo.analysis_export
        self.golden = ConfigDB().get(self, "", "golden")  # module with .advance
        self.compared = 0
        self.mismatches = 0
        self.runs = 0

    # ---- mirror state ------------------------------------------------------------------------
    def _reset_mirror(self):
        self.regs = {}            # word offset -> pending 32-bit value (config registers)
        self.busy = False
        self.expected_flags = set()
        self.latched_nsteps = 0

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

    def _run_golden(self):
        """Accepted doorbell: run emulation.advance on the mirrored config."""
        dt = w2f(self._cfg(DT_LO), self._cfg(DT_HI))
        nsteps = self._cfg(NSTEPS)
        npairs = self._cfg(NPAIRS) & 0xFF
        bodies = self._bodies_from_mirror()
        pairs = []
        for k in range(npairs):
            pw = self._cfg(PAIR_BASE + 4 * k)
            i, j = pw & 0xFF, (pw >> 8) & 0xFF
            if i >= N_BODIES or j >= N_BODIES:
                return False                     # ERR_PARAM reject: nothing latched
        if npairs > N_PAIRS_MAX:
            return False
        for k in range(npairs):
            pw = self._cfg(PAIR_BASE + 4 * k)
            pairs.append((bodies[pw & 0xFF], bodies[(pw >> 8) & 0xFF]))
        flags = self.golden.advance(dt, nsteps, bodies, pairs)
        self.expected_flags |= flags             # sticky mirror (testplan §4)
        self.latched_nsteps = nsteps
        # committed result is copied into the pending BODY regs at DONE (MAS §4)
        for i, (r, v, m) in enumerate(bodies):
            base = BODY_BASE + i * BODY_STRIDE
            for f, val in enumerate((r[0], r[1], r[2], v[0], v[1], v[2], m)):
                lo, hi = f2w(val)
                self.regs[base + 8 * f] = lo
                self.regs[base + 8 * f + 4] = hi
        self.runs += 1
        return True

    # ---- checks ------------------------------------------------------------------------------
    def _check(self, ok, msg):
        self.compared += 1
        if not ok:
            self.mismatches += 1
            if self.mismatches <= 10:
                self.logger.error(f"mismatch: {msg}")

    def _replay(self, items):
        self._reset_mirror()
        cfg_ranges = ([DT_LO, DT_HI, NSTEPS, NPAIRS]
                      + [BODY_BASE + i * BODY_STRIDE + 8 * f + w
                         for i in range(N_BODIES) for f in range(7) for w in (0, 4)]
                      + [PAIR_BASE + 4 * k for k in range(N_PAIRS_MAX)])
        cfg_set = set(cfg_ranges)
        for it in items:
            if it.kind == "write":
                if it.addr == CTRL:
                    if not self.busy and (it.data & 1) and not (it.data & 2):
                        self.busy = self._run_golden()
                elif it.addr in cfg_set and not self.busy and it.strb == 0xF:
                    self.regs[it.addr] = it.data
                elif it.addr == STATUS:
                    for b, n in FP_BITS.items():  # W1C clears the sticky mirror (testplan §4)
                        if it.data & (1 << b):
                            self.expected_flags.discard(n)
            else:  # read
                if it.addr == STATUS:
                    if it.data & (ST_DONE | ST_ABORTED):
                        self.busy = False
                    if not self.busy and (it.data & (ST_DONE | ST_ABORTED)):
                        got = {n for b, n in FP_BITS.items() if it.data & (1 << b)}
                        self._check(got == self.expected_flags,
                                    f"STATUS FP flags {got} != golden {self.expected_flags}")
                elif it.addr in cfg_set and not self.busy:
                    exp = self._cfg(it.addr)
                    self._check(it.data == exp,
                                f"@0x{it.addr:03x}: read 0x{it.data:08x} expected 0x{exp:08x}")
                elif it.addr == STEPS_DONE and not self.busy:
                    self._check(it.data == self.latched_nsteps,
                                f"STEPS_DONE {it.data} != {self.latched_nsteps}")
                elif it.addr == CYCLES_LO and not self.busy and self.latched_nsteps == 0 \
                        and self.runs:
                    self._check(it.data <= 4, f"PRD-F8: NSTEPS=0 CYCLES {it.data} > 4")
                elif it.addr == CYCLES_LO and not self.busy and self.latched_nsteps:
                    per_step = it.data / self.latched_nsteps
                    self._check(per_step <= K1,
                                f"K1: {it.data} cycles / {self.latched_nsteps} steps = "
                                f"{per_step:.1f} > {K1}")
                    self.logger.info(f"K1 measured: {per_step:.1f} cycles/step "
                                     f"(model 123 nominal / 127 worst)")

    def check_phase(self):
        items = []
        while self.fifo.can_get():
            ok, it = self.fifo.try_get()
            if ok:
                items.append(it)
        self._replay(items)
        assert self.runs > 0, "scoreboard: no accepted doorbell observed"
        assert self.compared > 0, "scoreboard: nothing compared"
        if self.mismatches == 0:
            self.logger.info(f"scoreboard: compared {self.compared} items, 0 mismatches "
                             f"(golden=emulation.advance, {self.runs} run(s))")

    def report_phase(self):
        assert self.mismatches == 0, f"scoreboard: {self.mismatches} mismatches"


class GrapeEnv(BaseEnv):
    def build_phase(self):
        super().build_phase()
        self.agent = AxiLiteAgent.create("agent", self)
        self.scoreboard = GrapeScoreboard.create("scoreboard", self)

    def connect_phase(self):
        self.agent.monitor.ap.connect(self.scoreboard.export)
