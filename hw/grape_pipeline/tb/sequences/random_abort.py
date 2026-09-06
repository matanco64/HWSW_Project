"""Abort paths (testplan F-11/F-21): random-offset aborts, DONE-wins, idle no-op, DB+AB,
NSTEPS=2^32-1 counter-width run."""
import random

from cocotb.triggers import ClockCycles

from smoke import (BODY_BASE, BODY_STRIDE, CTRL, CYCLES_LO, NSTEPS, STATUS, STEPS_DONE,
                   ST_DONE, GrapeBaseSeq)
from random_cfg import rand_body, rand_pairs

ST_ABORTED = 1 << 2


class AbortSeq(GrapeBaseSeq):
    def __init__(self, name="abort", seed=3, clk=None):
        super().__init__(name)
        self.rng = random.Random(seed)
        self.clk = clk

    async def poll_end(self, max_polls=400):
        for _ in range(max_polls):
            st = await self.rd(STATUS)
            if st & (ST_DONE | ST_ABORTED):
                return st
        raise AssertionError("neither DONE nor ABORTED seen")

    async def finish_abort(self):
        st = await self.poll_end()
        await self.rd(STEPS_DONE)                  # scoreboard replays golden from this
        await self.rd(CYCLES_LO)
        for i in range(5):
            base = BODY_BASE + i * BODY_STRIDE
            for f in range(7):
                await self.rd(base + 8 * f)
                await self.rd(base + 8 * f + 4)
        await self.wr(STATUS, st & (ST_DONE | ST_ABORTED))
        return st

    async def body(self):
        rng = self.rng
        bodies = [rand_body(rng) for _ in range(5)]
        # abort while idle: no-op (no flags)
        await self.wr(CTRL, 2)
        await self.rd(STATUS)
        # DB+AB in one write while idle: nothing starts
        await self.wr(CTRL, 3)
        await self.rd(STATUS)
        # random-offset aborts over multi-step runs
        for trial in range(4):
            nsteps = rng.randrange(3, 8)
            await self.program(rng.uniform(1e-3, 0.05), nsteps,
                               [rand_body(rng) for _ in range(5)], rand_pairs(rng, 4))
            await self.wr(CTRL, 1)
            if self.clk is not None:
                await ClockCycles(self.clk, rng.randrange(1, nsteps * 130))
            await self.wr(CTRL, 2)
            await self.finish_abort()
        # abort right after doorbell: STEPS_DONE <= 1
        await self.program(0.01, 5, bodies, [(0, 1), (2, 3)])
        await self.wr(CTRL, 1)
        await self.wr(CTRL, 2)
        await self.finish_abort()
        # DB+AB while busy: abort acts AND ERR_BUSY
        await self.program(0.01, 6, bodies, [(0, 1)])
        await self.wr(CTRL, 1)
        await self.wr(CTRL, 3)
        await self.finish_abort()
        await self.wr(STATUS, 0xFFFF_FFFF)         # clear everything incl. ERR_BUSY
        # NSTEPS = 2^32-1: run a few steps, abort (counter width, testplan F-11)
        await self.program(0.01, 0xFFFFFFFF, bodies, [(0, 1), (1, 2)])
        await self.wr(CTRL, 1)
        if self.clk is not None:
            await ClockCycles(self.clk, 700)       # ~5 steps
        await self.wr(CTRL, 2)
        await self.finish_abort()
