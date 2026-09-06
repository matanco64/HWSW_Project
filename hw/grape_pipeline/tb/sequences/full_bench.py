"""Sign-off sequence (testplan F-04/F-05): the benchmark's own 20,000-step advance through the
DUT — benchmark_system() state, all 10 pairs, dt = 0.01."""
from smoke import (BODY_BASE, BODY_STRIDE, CYCLES_LO, CYCLES_HI, STATUS, STEPS_DONE,
                   ST_DONE, GrapeBaseSeq)


class FullBenchSeq(GrapeBaseSeq):
    def __init__(self, name="full_bench", bodies=None, pairs=None, nsteps=20000):
        super().__init__(name)
        self.bodies = bodies
        self.pairs = pairs
        self.nsteps = nsteps

    async def body(self):
        await self.program(0.01, self.nsteps, self.bodies, self.pairs)
        await self.run_to_done(self.nsteps, max_polls=900000)
        await self.wr(STATUS, ST_DONE)
        await self.rd(CYCLES_LO)
        await self.rd(CYCLES_HI)
        await self.rd(STEPS_DONE)
        for i in range(len(self.bodies)):
            base = BODY_BASE + i * BODY_STRIDE
            for f in range(7):
                await self.rd(base + 8 * f)
                await self.rd(base + 8 * f + 4)
