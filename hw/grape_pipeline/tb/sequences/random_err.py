"""Error paths (testplan F-09/F-17/F-21): ERR_PARAM rejects, writes while BUSY, reject-fix-run."""
import random

from smoke import (BODY_BASE, CTRL, DT_LO, NPAIRS, NSTEPS, PAIR_BASE, STATUS,
                   ST_DONE, GrapeBaseSeq)
from random_cfg import rand_body, rand_pairs

ST_ERR_BUSY, ST_ERR_PARAM = 1 << 8, 1 << 9


class ErrSeq(GrapeBaseSeq):
    def __init__(self, name="err", seed=2):
        super().__init__(name)
        self.rng = random.Random(seed)

    async def body(self):
        rng = self.rng
        bodies = [rand_body(rng) for _ in range(5)]
        # 1. ERR_PARAM: pair index out of range
        await self.program(0.01, 1, bodies, [(0, 1)])
        await self.wr(PAIR_BASE, (7 << 8) | 0)     # j = 7 >= N_BODIES
        await self.wr(CTRL, 1)
        st = await self.rd(STATUS)
        assert st & ST_ERR_PARAM and not (st & 1), f"expected ERR_PARAM idle, got 0x{st:05x}"
        # 2. ERR_PARAM: NPAIRS too large
        await self.wr(NPAIRS, 11)
        await self.wr(CTRL, 1)
        await self.rd(STATUS)
        # 3. fix and run (reject-then-fix-then-accept)
        await self.wr(STATUS, ST_ERR_PARAM)        # W1C
        await self.wr(NPAIRS, 1)
        await self.wr(PAIR_BASE, (1 << 8) | 0)
        await self.run_to_done(1)
        # 4. writes while BUSY: every config class + doorbell -> ERR_BUSY, run unaffected
        await self.wr(NSTEPS, 3)
        await self.wr(CTRL, 1)                     # doorbell (3 steps, time to interfere)
        await self.wr(DT_LO, 0xDEADBEEF)           # ignored
        await self.wr(NSTEPS, 0)                   # ignored
        await self.wr(NPAIRS, 9)                   # ignored
        await self.wr(BODY_BASE, 0x12345678)       # ignored
        await self.wr(PAIR_BASE, (2 << 8) | 3)     # ignored
        await self.wr(CTRL, 1)                     # doorbell while BUSY
        await self.run_to_done(3, max_polls=200)
        await self.wr(STATUS, ST_DONE | ST_ERR_BUSY)
        # 5. pending-register bit exercise (PRD-F7 round-trip at full width): all-ones pair
        # words / NPAIRS / IRQ_EN, read back while idle, then restored (nothing latched).
        for k in range(10):
            await self.wr(PAIR_BASE + 4 * k, 0xFFFF)
        await self.wr(NPAIRS, 0xFF)
        await self.wr(0x010, 0x1FFFE)              # IRQ_EN full mask
        for k in range(10):
            await self.rd(PAIR_BASE + 4 * k)
        await self.rd(NPAIRS)
        await self.rd(0x010)
        for k in range(10):
            await self.wr(PAIR_BASE + 4 * k, 0)
        await self.wr(NPAIRS, 0)
        await self.wr(0x010, 0)
        # 6. unmapped offsets -> SLVERR (MAS §4 0x428-0xFFC; cg_axi resp2)
        it = await self.rd(0x800)
        it = await self.wr(0x800, 0x1234)
        # 7. readback proves ignored writes really were ignored (scoreboard compares mirror)
        await self.rd(DT_LO)
        await self.rd(NSTEPS)
        await self.rd(NPAIRS)
        await self.rd(PAIR_BASE)
        await self.rd(BODY_BASE)
