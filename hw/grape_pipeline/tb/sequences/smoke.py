"""Smoke sequence (testplan F-01 bring-up): program a short synthetic run, doorbell, poll to
DONE, W1C, read everything back. All traffic goes through the AXI agent; the scoreboard checks
from the monitor stream."""
import struct

from axi_lite_agent import AxiLiteSeqItem
from pyuvm import uvm_sequence

CTRL, STATUS = 0x008, 0x00C
CYCLES_LO, CYCLES_HI, STEPS_DONE = 0x040, 0x044, 0x048
DT_LO, DT_HI, NSTEPS, NPAIRS = 0x100, 0x104, 0x108, 0x10C
BODY_BASE, BODY_STRIDE, PAIR_BASE = 0x200, 0x40, 0x400
ST_BUSY, ST_DONE = 1 << 0, 1 << 1


def f2w(x):
    return struct.unpack("<II", struct.pack("<d", float(x)))


class GrapeBaseSeq(uvm_sequence):
    async def wr(self, addr, data):
        item = AxiLiteSeqItem("wr", kind="write", addr=addr, data=data)
        await self.start_item(item)
        await self.finish_item(item)
        return item

    async def rd(self, addr):
        item = AxiLiteSeqItem("rd", kind="read", addr=addr)
        await self.start_item(item)
        await self.finish_item(item)
        return item.data

    async def wr64(self, addr, value):
        lo, hi = f2w(value)
        await self.wr(addr, lo)
        await self.wr(addr + 4, hi)

    async def program(self, dt, nsteps, bodies, pairs):
        """bodies: list of ([x,y,z],[vx,vy,vz],m); pairs: list of (i, j) index tuples."""
        await self.wr64(DT_LO, dt)
        await self.wr(NSTEPS, nsteps)
        await self.wr(NPAIRS, len(pairs))
        for i, (r, v, m) in enumerate(bodies):
            base = BODY_BASE + i * BODY_STRIDE
            for f, val in enumerate((r[0], r[1], r[2], v[0], v[1], v[2], m)):
                await self.wr64(base + 8 * f, val)
        for k, (bi, bj) in enumerate(pairs):
            await self.wr(PAIR_BASE + 4 * k, (bj << 8) | bi)

    async def run_to_done(self, nsteps, max_polls=None):
        await self.wr(CTRL, 1)                     # doorbell
        polls = max_polls or (50 + 40 * max(nsteps, 1))
        for n in range(polls):
            status = await self.rd(STATUS)
            if status & ST_DONE:
                return status
            if n % 16 == 0:
                cyc = await self.rd(CYCLES_LO)
                steps = await self.rd(STEPS_DONE)
                print(f"[smoke] poll {n}: STATUS=0x{status:05x} CYCLES={cyc} STEPS_DONE={steps}")
        raise AssertionError(f"DONE not seen within {polls} STATUS polls")


class SmokeSeq(GrapeBaseSeq):
    """NPAIRS=2, NSTEPS=2 on benchmark-valued bodies (memory: bring-up-first synthetic step)."""

    def __init__(self, name="smoke", dt=0.01, nsteps=2, bodies=None, pairs=None):
        super().__init__(name)
        self.dt = dt
        self.nsteps = nsteps
        self.bodies = bodies
        self.pairs = pairs if pairs is not None else [(0, 1), (0, 2)]

    async def body(self):
        await self.program(self.dt, self.nsteps, self.bodies, self.pairs)
        await self.run_to_done(self.nsteps)
        await self.wr(STATUS, ST_DONE)             # W1C
        await self.rd(STATUS)
        await self.rd(CYCLES_LO)
        await self.rd(CYCLES_HI)
        await self.rd(STEPS_DONE)
        for i in range(len(self.bodies)):          # full state read-back (scoreboard compares)
            base = BODY_BASE + i * BODY_STRIDE
            for f in range(7):
                await self.rd(base + 8 * f)
                await self.rd(base + 8 * f + 4)


class CornerSeq(GrapeBaseSeq):
    """PRD-F8 (NSTEPS=0 no-op, CYCLES <= 4) then NPAIRS=0 (integrate-only) back-to-back."""

    def __init__(self, name="corner", bodies=None):
        super().__init__(name)
        self.bodies = bodies

    async def body(self):
        # NSTEPS = 0: immediate DONE, state unchanged (testplan F-08)
        await self.program(0.01, 0, self.bodies, [(0, 1), (0, 2)])
        await self.run_to_done(0, max_polls=10)
        await self.wr(STATUS, ST_DONE)
        await self.rd(CYCLES_LO)
        await self.rd(STEPS_DONE)
        for i in range(len(self.bodies)):
            base = BODY_BASE + i * BODY_STRIDE
            for f in range(7):
                await self.rd(base + 8 * f)
                await self.rd(base + 8 * f + 4)
        # NPAIRS = 0, NSTEPS = 3: integrate-only steps (testplan F-32 npairs0)
        await self.wr(NSTEPS, 3)
        await self.wr(NPAIRS, 0)
        await self.run_to_done(3)
        await self.wr(STATUS, ST_DONE)
        await self.rd(CYCLES_LO)
        await self.rd(STEPS_DONE)
        for i in range(len(self.bodies)):
            base = BODY_BASE + i * BODY_STRIDE
            for f in range(7):
                await self.rd(base + 8 * f)
                await self.rd(base + 8 * f + 4)
