"""Constrained-random invocations (testplan F-02/F-03/F-07/F-32/F-33): random configs, pair
permutations (duplicates + both orders), back-to-back runs with partial reprogramming."""
import random

from smoke import (BODY_BASE, BODY_STRIDE, CYCLES_LO, STATUS, STEPS_DONE, ST_DONE,
                   GrapeBaseSeq)


def rand_body(rng):
    r = [rng.uniform(-50, 50) for _ in range(3)]
    v = [rng.uniform(-5, 5) for _ in range(3)]
    m = rng.uniform(1e-3, 40.0)
    return (r, v, m)


def rand_pairs(rng, npairs):
    pairs = []
    for _ in range(npairs):
        i = rng.randrange(5)
        j = rng.randrange(5)
        while j == i:
            j = rng.randrange(5)
        pairs.append((i, j))
    return pairs


class RandCfgSeq(GrapeBaseSeq):
    """`n_runs` random invocations; ~1 in 4 reuses the previous committed state (F-33)."""

    def __init__(self, name="rand_cfg", seed=1, n_runs=25):
        super().__init__(name)
        self.rng = random.Random(seed)
        self.n_runs = n_runs

    async def one_run(self, full_program, force_npairs=None):
        rng = self.rng
        nsteps = rng.choice([1, 1, 2, 3, rng.randrange(1, 8)])
        npairs = force_npairs if force_npairs is not None else \
            rng.choice([0, 1, 2, 5, 10, rng.randrange(0, 11)])
        pairs = rand_pairs(rng, npairs)
        if full_program:
            bodies = [rand_body(rng) for _ in range(5)]
            await self.program(rng.uniform(1e-3, 0.1), nsteps, bodies, pairs)
        else:                                     # partial reprogram: keep committed bodies
            await self.wr(0x108, nsteps)          # NSTEPS
            await self.wr(0x10C, len(pairs))      # NPAIRS
            for k, (bi, bj) in enumerate(pairs):
                await self.wr(0x400 + 4 * k, (bj << 8) | bi)
        await self.run_to_done(nsteps)
        await self.wr(STATUS, ST_DONE)
        await self.rd(CYCLES_LO)
        await self.rd(STEPS_DONE)
        n_readback = 5 if not full_program else 5
        for i in range(n_readback):
            base = BODY_BASE + i * BODY_STRIDE
            for f in range(7):
                await self.rd(base + 8 * f)
                await self.rd(base + 8 * f + 4)

    async def body(self):
        for n in range(self.n_runs):
            forced = [None, 6, 7, 8, 9][n] if n < 5 else None   # cg_cfg npairs 6..9 bins
            await self.one_run(full_program=(n == 0 or self.rng.random() > 0.25),
                               force_npairs=forced)
