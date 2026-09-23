"""grape_pipeline software driver model (stage 10, hw-integrate).

Register offsets/fields are generated one-for-one from the MAS register map
(`hw/grape_pipeline/docs/mas.md` §4) — `check_regmap.py` verifies this driver
against that table (0 differences required). The driver API matches the
contract in MAS §6.

Backends
--------
`MMIO` is the abstract bus: `read32(addr)` / `write32(addr, v)`.
`ModelBus` is a standalone functional+cycle model of the register block
(no RTL, no physics): it honours the invocation protocol (doorbell, BUSY,
DONE, W1C, ERR_PARAM) and reports CYCLES = K1 * NSTEPS with K1 = 124
(the measured, signed-off cycles/step — docs/ppa.md trade-off point 2), so
the driver and the speedup model can be exercised without a simulator. The
bit-exact physics lives in the frozen golden model + RTL.
`SimBackend` is the RTL-cosim path: it wires the identical register constants
below to the pyuvm `axi_lite_agent` through a running sequence's async
`rd`/`wr`, and `AsyncGrapeDriver` is the same API awaited per bus access.
Exercised by `tb/test_driver_model.py` (`make sim MODULE=test_driver_model`).
"""
from __future__ import annotations

import struct

# --- Register map (byte offsets), generated from MAS §4 -------------------
ID          = 0x000   # RO  ASCII 'GRP1'
VERSION     = 0x004   # RO  git short SHA
CTRL        = 0x008   # WP  bit0 DOORBELL, bit1 ABORT
STATUS      = 0x00C   # RO/W1C
IRQ_EN      = 0x010   # RW  mask over STATUS 16:1
IRQ_STATUS  = 0x014   # RO  STATUS & IRQ_EN
CYCLES_LO   = 0x040   # RO  busy cycles low word
CYCLES_HI   = 0x044   # RO  busy cycles high word
STEPS_DONE  = 0x048   # RO  steps committed (live)
DT_LO       = 0x100   # RW  dt IEEE binary64 low word
DT_HI       = 0x104   # RW  dt high word
NSTEPS      = 0x108   # RW  steps per invocation
NPAIRS      = 0x10C   # RW  pairs walked per step
BODY_BASE   = 0x200   # RW  BODY[i] window, stride 0x40
BODY_STRIDE = 0x040
PAIR_BASE   = 0x400   # RW  PAIR[k], stride 0x04
PAIR_STRIDE = 0x004

ID_VALUE = 0x47525031  # 'GRP1'

# CTRL bit positions (WP)
CTRL_DOORBELL = 1 << 0
CTRL_ABORT    = 1 << 1

# STATUS bit positions
ST_BUSY      = 1 << 0
ST_DONE      = 1 << 1
ST_ABORTED   = 1 << 2
ST_ERR_BUSY  = 1 << 8
ST_ERR_PARAM = 1 << 9
ST_FP_INVALID   = 1 << 12
ST_FP_DIVZERO   = 1 << 13
ST_FP_OVERFLOW  = 1 << 14
ST_FP_UNDERFLOW = 1 << 15
ST_STICKY_MASK  = 0x1FFFE          # bits 16:1 (W1C set)

# BODY[i] field byte offsets within the 0x40 stride (7 x FP64 pairs)
BODY_FIELDS = {"x": 0x00, "y": 0x08, "z": 0x10,
               "vx": 0x18, "vy": 0x20, "vz": 0x28, "m": 0x30}

K1_CYCLES_PER_STEP = 124           # measured, signed off (docs/ppa.md)


def f2words(x: float) -> tuple[int, int]:
    """IEEE binary64 -> (low32, high32), little-endian words (MAS §4)."""
    return struct.unpack("<II", struct.pack("<d", float(x)))


def words2f(lo: int, hi: int) -> float:
    return struct.unpack("<d", struct.pack("<II", lo & 0xFFFFFFFF, hi & 0xFFFFFFFF))[0]


class MMIO:
    """Abstract 32-bit MMIO bus."""
    def read32(self, addr: int) -> int:                # pragma: no cover
        raise NotImplementedError
    def write32(self, addr: int, value: int) -> None:  # pragma: no cover
        raise NotImplementedError


class AccelDriver:
    """Shared base (ADR-0005). `bus` provides read32/write32."""
    def __init__(self, bus: MMIO, base: int = 0):
        self.bus = bus
        self.base = base

    def _rd(self, off: int) -> int:
        return self.bus.read32(self.base + off)

    def _wr(self, off: int, val: int) -> None:
        self.bus.write32(self.base + off, val & 0xFFFFFFFF)

    def status(self) -> int:
        return self._rd(STATUS)

    def start(self) -> bool:
        """Doorbell. Returns False if the doorbell was rejected (ERR_PARAM)."""
        self._wr(CTRL, CTRL_DOORBELL)
        s = self.status()
        if s & ST_ERR_PARAM:
            return False
        return True

    def abort(self) -> None:
        self._wr(CTRL, CTRL_ABORT)

    def wait_done(self, max_polls: int) -> int:
        """Poll STATUS until DONE|ABORTED. Raises on timeout or on
        ERR_PARAM/ERR_BUSY. FP_* flags are returned, never raised."""
        for _ in range(max_polls):
            s = self.status()
            if s & (ST_ERR_PARAM | ST_ERR_BUSY):
                raise RuntimeError(f"invocation error: STATUS=0x{s:05x}")
            if s & (ST_DONE | ST_ABORTED):
                return s
        raise TimeoutError(f"wait_done: no DONE after {max_polls} polls")

    def clear(self, bits: int = ST_STICKY_MASK) -> None:
        self._wr(STATUS, bits)

    def counters(self) -> dict:
        lo, hi = self._rd(CYCLES_LO), self._rd(CYCLES_HI)
        return {"cycles": (hi << 32) | lo, "steps_done": self._rd(STEPS_DONE)}


class GrapeDriver(AccelDriver):
    N_BODIES, N_PAIRS_MAX = 5, 10

    def load_bodies(self, bodies) -> None:
        """bodies: [[r[3], v[3], m], ...] in benchmark layout."""
        for i, (r, v, m) in enumerate(bodies):
            base = BODY_BASE + i * BODY_STRIDE
            for name, val in zip(("x", "y", "z"), r):
                lo, hi = f2words(val)
                self._wr(base + BODY_FIELDS[name],     lo)
                self._wr(base + BODY_FIELDS[name] + 4, hi)
            for name, val in zip(("vx", "vy", "vz"), v):
                lo, hi = f2words(val)
                self._wr(base + BODY_FIELDS[name],     lo)
                self._wr(base + BODY_FIELDS[name] + 4, hi)
            lo, hi = f2words(m)
            self._wr(base + BODY_FIELDS["m"],     lo)
            self._wr(base + BODY_FIELDS["m"] + 4, hi)

    def load_pairs(self, index_pairs) -> None:
        """index_pairs: list of (i, j); validated < N_BODIES before writing."""
        for i, j in index_pairs:
            if not (0 <= i < self.N_BODIES and 0 <= j < self.N_BODIES):
                raise ValueError(f"pair index out of range: ({i}, {j})")
        self._wr(NPAIRS, len(index_pairs))
        for k, (i, j) in enumerate(index_pairs):
            self._wr(PAIR_BASE + k * PAIR_STRIDE, ((j & 0xFF) << 8) | (i & 0xFF))

    def configure(self, dt: float, nsteps: int) -> None:
        lo, hi = f2words(dt)
        self._wr(DT_LO, lo)
        self._wr(DT_HI, hi)
        self._wr(NSTEPS, nsteps)

    def read_bodies(self, bodies) -> None:
        """Writes committed r and v back into the same lists; mass untouched."""
        for i, (r, v, _m) in enumerate(bodies):
            base = BODY_BASE + i * BODY_STRIDE
            for idx, name in enumerate(("x", "y", "z")):
                r[idx] = words2f(self._rd(base + BODY_FIELDS[name]),
                                 self._rd(base + BODY_FIELDS[name] + 4))
            for idx, name in enumerate(("vx", "vy", "vz")):
                v[idx] = words2f(self._rd(base + BODY_FIELDS[name]),
                                 self._rd(base + BODY_FIELDS[name] + 4))

    def advance(self, dt, n, bodies, pairs) -> None:
        """Benchmark signature. `pairs` are (body, body) tuples of the same list
        objects -> resolved to indices by identity (i = first, j = second)."""
        ids = {id(b): k for k, b in enumerate(bodies)}
        index_pairs = [(ids[id(a)], ids[id(b)]) for (a, b) in pairs]
        self.load_bodies(bodies)
        self.load_pairs(index_pairs)
        self.configure(dt, n)
        if not self.start():
            raise RuntimeError("doorbell rejected (ERR_PARAM)")
        self.wait_done(max_polls=n * K1_CYCLES_PER_STEP + 64)
        self.read_bodies(bodies)
        self.clear()


class ModelBus(MMIO):
    """Standalone functional + cycle model of the register block (no RTL).

    Honours the MAS §5 invocation protocol so the driver and the speedup model
    run without a simulator. It does NOT integrate the physics: BODY read-back
    echoes the committed (written) state. CYCLES = K1 * NSTEPS with the
    measured K1 = 124.
    """
    def __init__(self):
        self.mem = {}
        self.busy = False
        self.sticky = 0
        self.cycles = 0
        self.steps_done = 0
        self.dt_pend = self.nsteps_pend = self.npairs_pend = 0
        self.committed = {}          # committed BODY window snapshot

    # -- helpers
    def _word(self, addr):
        return self.mem.get(addr, 0)

    def read32(self, addr: int) -> int:
        if addr == ID:
            return ID_VALUE
        if addr == STATUS:
            return (self.sticky & 0x1FFFE) | (1 if self.busy else 0)
        if addr == IRQ_STATUS:
            return self.sticky & self._word(IRQ_EN)
        if addr == CYCLES_LO:
            return self.cycles & 0xFFFFFFFF
        if addr == CYCLES_HI:
            return (self.cycles >> 32) & 0xFFFFFFFF
        if addr == STEPS_DONE:
            return self.steps_done
        if BODY_BASE <= addr < PAIR_BASE:      # committed read-back window
            return self.committed.get(addr, self._word(addr))
        return self._word(addr)

    def write32(self, addr: int, value: int) -> None:
        value &= 0xFFFFFFFF
        if addr == CTRL:
            if self.busy:
                self.sticky |= ST_ERR_BUSY       # F9
                return
            if value & CTRL_DOORBELL:
                self._doorbell()
            return
        if addr == STATUS:                        # W1C
            self.sticky &= ~(value & 0x1FFFE)
            return
        if self.busy:                             # config write while BUSY
            self.sticky |= ST_ERR_BUSY
            return
        self.mem[addr] = value

    def _doorbell(self):
        npairs = self._word(NPAIRS) & 0xFF
        # F17: pair index >= N_BODIES or NPAIRS > N_PAIRS_MAX -> ERR_PARAM
        if npairs > GrapeDriver.N_PAIRS_MAX:
            self.sticky |= ST_ERR_PARAM
            return
        for k in range(npairs):
            w = self._word(PAIR_BASE + k * PAIR_STRIDE)
            i, j = w & 0xFF, (w >> 8) & 0xFF
            if i >= GrapeDriver.N_BODIES or j >= GrapeDriver.N_BODIES:
                self.sticky |= ST_ERR_PARAM
                return
        nsteps = self._word(NSTEPS)
        # commit the body window snapshot (echo model: no integration)
        self.committed = {a: v for a, v in self.mem.items()
                          if BODY_BASE <= a < PAIR_BASE}
        self.cycles = K1_CYCLES_PER_STEP * nsteps if nsteps else 4  # F8: nsteps=0 -> <=4
        self.steps_done = nsteps
        self.sticky |= ST_DONE                    # model completes instantly
        self.busy = False


# =============================================================================
# SimBackend + AsyncGrapeDriver — RTL-cosim over the pyuvm axi_lite_agent
# (cocotb only; tb/test_driver_model.py).
# =============================================================================
class SimBackend(MMIO):
    """Drives the identical register constants through the DUT in cocotb.

    Construct with a running `uvm_sequence` (a `GrapeBaseSeq`, or anything with
    async `wr(addr, data)` / `rd(addr)` that go through the AXI-Lite agent's
    sequencer). Every access is monitored, so the env scoreboard checks each
    read-back against the golden `emulation.advance` while the driver runs.
    """

    def __init__(self, seq):
        self.seq = seq                     # provides async wr(addr, data) / rd(addr)

    async def read32(self, addr: int) -> int:
        return await self.seq.rd(addr)

    async def write32(self, addr: int, value: int) -> None:
        await self.seq.wr(addr, value & 0xFFFFFFFF)


class AsyncGrapeDriver(GrapeDriver):
    """`GrapeDriver` with every bus access awaited (for `SimBackend`).

    Each method is the sync body of its `GrapeDriver`/`AccelDriver` namesake
    with `await` on the bus calls; register constants and semantics are
    identical, so `check_regmap.py` covers this class too.
    """

    async def _rd(self, off: int) -> int:
        return await self.bus.read32(self.base + off)

    async def _wr(self, off: int, val: int) -> None:
        await self.bus.write32(self.base + off, val & 0xFFFFFFFF)

    # -- AccelDriver
    async def status(self) -> int:
        return await self._rd(STATUS)

    async def start(self) -> bool:
        """Doorbell. Returns False if the doorbell was rejected (ERR_PARAM)."""
        await self._wr(CTRL, CTRL_DOORBELL)
        s = await self.status()
        if s & ST_ERR_PARAM:
            return False
        return True

    async def abort(self) -> None:
        await self._wr(CTRL, CTRL_ABORT)

    async def wait_done(self, max_polls: int) -> int:
        """Poll STATUS until DONE|ABORTED. Raises on timeout or on
        ERR_PARAM/ERR_BUSY. FP_* flags are returned, never raised."""
        for _ in range(max_polls):
            s = await self.status()
            if s & (ST_ERR_PARAM | ST_ERR_BUSY):
                raise RuntimeError(f"invocation error: STATUS=0x{s:05x}")
            if s & (ST_DONE | ST_ABORTED):
                return s
        raise TimeoutError(f"wait_done: no DONE after {max_polls} polls")

    async def clear(self, bits: int = ST_STICKY_MASK) -> None:
        await self._wr(STATUS, bits)

    async def counters(self) -> dict:
        lo, hi = await self._rd(CYCLES_LO), await self._rd(CYCLES_HI)
        return {"cycles": (hi << 32) | lo, "steps_done": await self._rd(STEPS_DONE)}

    # -- GrapeDriver
    async def load_bodies(self, bodies) -> None:
        """bodies: [[r[3], v[3], m], ...] in benchmark layout."""
        for i, (r, v, m) in enumerate(bodies):
            base = BODY_BASE + i * BODY_STRIDE
            for name, val in zip(("x", "y", "z"), r):
                lo, hi = f2words(val)
                await self._wr(base + BODY_FIELDS[name],     lo)
                await self._wr(base + BODY_FIELDS[name] + 4, hi)
            for name, val in zip(("vx", "vy", "vz"), v):
                lo, hi = f2words(val)
                await self._wr(base + BODY_FIELDS[name],     lo)
                await self._wr(base + BODY_FIELDS[name] + 4, hi)
            lo, hi = f2words(m)
            await self._wr(base + BODY_FIELDS["m"],     lo)
            await self._wr(base + BODY_FIELDS["m"] + 4, hi)

    async def load_pairs(self, index_pairs) -> None:
        """index_pairs: list of (i, j); validated < N_BODIES before writing."""
        for i, j in index_pairs:
            if not (0 <= i < self.N_BODIES and 0 <= j < self.N_BODIES):
                raise ValueError(f"pair index out of range: ({i}, {j})")
        await self._wr(NPAIRS, len(index_pairs))
        for k, (i, j) in enumerate(index_pairs):
            await self._wr(PAIR_BASE + k * PAIR_STRIDE, ((j & 0xFF) << 8) | (i & 0xFF))

    async def configure(self, dt: float, nsteps: int) -> None:
        lo, hi = f2words(dt)
        await self._wr(DT_LO, lo)
        await self._wr(DT_HI, hi)
        await self._wr(NSTEPS, nsteps)

    async def read_bodies(self, bodies) -> None:
        """Writes committed r and v back into the same lists; mass untouched."""
        for i, (r, v, _m) in enumerate(bodies):
            base = BODY_BASE + i * BODY_STRIDE
            for idx, name in enumerate(("x", "y", "z")):
                r[idx] = words2f(await self._rd(base + BODY_FIELDS[name]),
                                 await self._rd(base + BODY_FIELDS[name] + 4))
            for idx, name in enumerate(("vx", "vy", "vz")):
                v[idx] = words2f(await self._rd(base + BODY_FIELDS[name]),
                                 await self._rd(base + BODY_FIELDS[name] + 4))

    async def advance(self, dt, n, bodies, pairs) -> None:
        """Benchmark signature. `pairs` are (body, body) tuples of the same list
        objects -> resolved to indices by identity (i = first, j = second)."""
        ids = {id(b): k for k, b in enumerate(bodies)}
        index_pairs = [(ids[id(a)], ids[id(b)]) for (a, b) in pairs]
        await self.load_bodies(bodies)
        await self.load_pairs(index_pairs)
        await self.configure(dt, n)
        if not await self.start():
            raise RuntimeError("doorbell rejected (ERR_PARAM)")
        await self.wait_done(max_polls=n * K1_CYCLES_PER_STEP + 64)
        await self.read_bodies(bodies)
        await self.clear()
