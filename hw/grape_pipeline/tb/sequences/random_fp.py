"""IEEE special values (testplan F-13/F-24): coincident bodies (divzero+invalid), overflow,
underflow; W1C-then-idle quiet check happens in the test."""
from smoke import BODY_BASE, BODY_STRIDE, STATUS, ST_DONE, GrapeBaseSeq

FP_W1C = (1 << 12) | (1 << 13) | (1 << 14) | (1 << 15)


class FpSeq(GrapeBaseSeq):
    async def run_case(self, dt, bodies, pairs, nsteps=1):
        await self.program(dt, nsteps, bodies, pairs)
        await self.run_to_done(nsteps)
        await self.rd(STATUS)                      # sticky compare vs golden flag mirror
        for i in range(5):                         # NaN/Inf state bit-exact (F-13)
            base = BODY_BASE + i * BODY_STRIDE
            for f in range(7):
                await self.rd(base + 8 * f)
                await self.rd(base + 8 * f + 4)
        await self.wr(STATUS, ST_DONE | FP_W1C)    # clear for the next case
        await self.rd(STATUS)

    async def body(self):
        b = ([1.0, 2.0, 3.0], [0.1, -0.2, 0.3], 5.0)
        # coincident bodies: dsq = 0 -> divzero (rcp), then 0*inf -> invalid, NaN velocities
        bodies = [b, (list(b[0]), [0.0, 0.0, 0.0], 2.0)] + [([float(i + 4), 0.0, 0.0],
                  [0.0, 0.0, 0.0], 1.0) for i in range(3)]
        bodies[1] = ([1.0, 2.0, 3.0], [0.0, 0.0, 0.0], 2.0)
        await self.run_case(0.01, bodies, [(0, 1)])
        # overflow: huge masses and dt
        big = 1e308
        bodies = [([0.0, 0.0, 0.0], [0.0, 0.0, 0.0], big),
                  ([1e-150, 0.0, 0.0], [0.0, 0.0, 0.0], big)] + \
                 [([float(i + 2), 1.0, 1.0], [0.0, 0.0, 0.0], 1.0) for i in range(3)]
        await self.run_case(1e300, bodies, [(0, 1)])
        # underflow: tiny masses, tiny dt, huge separation
        tiny = 5e-324
        bodies = [([0.0, 0.0, 0.0], [0.0, 0.0, 0.0], tiny),
                  ([1e150, 0.0, 0.0], [0.0, 0.0, 0.0], tiny)] + \
                 [([float(i + 2), 2.0, 2.0], [0.0, 0.0, 0.0], 1.0) for i in range(3)]
        await self.run_case(1e-300, bodies, [(0, 1)])
        # NaN-poisoned multi-step: step 1 makes NaN velocities/positions, steps 2-3 feed NaN
        # through sub/square/sqrt/rcp/mul/add special paths (coincident pair, all pairs chained)
        bodies = [([1.0, 1.0, 1.0], [0.0, 0.0, 0.0], 2.0),
                  ([1.0, 1.0, 1.0], [0.0, 0.0, 0.0], 3.0),
                  ([2.0, 0.0, 0.0], [0.1, 0.1, 0.1], 1.0),
                  ([0.0, 2.0, 0.0], [-0.1, 0.0, 0.0], 1.0),
                  ([0.0, 0.0, 2.0], [0.0, -0.1, 0.0], 1.0)]
        await self.run_case(0.5, bodies, [(0, 1), (0, 2), (1, 3), (2, 4), (3, 4)], nsteps=3)
        # subnormal dsq into sqrt (radicand formatter's denormal path)
        bodies = [([0.0, 0.0, 0.0], [0.0, 0.0, 0.0], 1e-30),
                  ([1e-160, 2e-160, 3e-160], [0.0, 0.0, 0.0], 1e-30),
                  ([1.0, 1.0, 1.0], [0.0, 0.0, 0.0], 1.0),
                  ([2.0, 2.0, 2.0], [0.0, 0.0, 0.0], 1.0),
                  ([3.0, 3.0, 3.0], [0.0, 0.0, 0.0], 1.0)]
        await self.run_case(1e-3, bodies, [(0, 1)])
        # subnormals and -0.0 through the normal path
        sub = 2.5e-310
        bodies = [([-0.0, sub, -sub], [sub, -0.0, 0.0], 4e-310),
                  ([sub, -0.0, sub], [0.0, sub, -0.0], 3.0),
                  ([1.0, 1.0, 1.0], [0.0, 0.0, 0.0], 1.0),
                  ([2.0, 2.0, 2.0], [0.0, 0.0, 0.0], 1.0),
                  ([3.0, 3.0, 3.0], [0.0, 0.0, 0.0], 1.0)]
        await self.run_case(1e-5, bodies, [(0, 1), (2, 3)], nsteps=2)
