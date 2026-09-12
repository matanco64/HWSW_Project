"""test_bench_block sequence (F-01/F-02/F-12/F-30): the real benchmark bzip2 block from
tb/vectors/, programmed and polled to DONE; K1 = CYCLES/SYMBOLS enforced by the test."""
from env import BITS, BUILD_CYCLES, CYCLES_LO, OVERFETCH, ST_DONE, STATUS, SYMBOLS
from smoke import HuffBaseSeq


class BenchSeq(HuffBaseSeq):
    """Program the vector block, doorbell, poll to DONE, read every counter."""

    def __init__(self, name="bench", vec=None):
        super().__init__(name)
        self.vec = vec
        self.counters = {}

    async def body(self):
        v = self.vec
        await self.program(start_bit=v["start_bit"], alphabet=v["alphabet"],
                           n_tables=v["n_tables"], lengths=v["lengths"])
        await self.run_to_done(max_polls=60000)
        await self.wr(STATUS, ST_DONE)               # W1C
        for name, addr in (("cycles", CYCLES_LO), ("symbols", SYMBOLS), ("bits", BITS),
                           ("build_cycles", BUILD_CYCLES), ("overfetch", OVERFETCH)):
            self.counters[name] = await self.rd(addr)
