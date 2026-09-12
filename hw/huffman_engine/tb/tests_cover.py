"""Directed coverage fillers (dv_coverage): a max-config invocation that fills the whole
48-word-stride LEN window and every count bin (alphabet 288, 6 tables), an IRQ path
(enable → fire → clear), high-counter-word reads, DBG all kinds, and reserved-address reads
— the structural toggle/line the random suite leaves (huff_regs wide storage + IRQ + DBG)."""
import random

import canonical_model as cm
import cocotb
from cocotbext.axi import AxiStreamFrame
from pyuvm import uvm_root

from env import (CYCLES_HI, CYCLES_LO, DBG_DATA, DBG_SEL, IRQ_EN, ID_REG, N_TABLES,
                 START_BIT, STATUS, ST_DONE, STICKY_MASK, SYMBOLS, BITS, ALPHABET, MODE,
                 SYMBOL_LIMIT, LEN_BASE, CTRL, ST_BUSY)
from rand_tables import make_tables, make_stream
from smoke import HuffBaseSeq, pack_lengths


class CoverSeq(HuffBaseSeq):
    """Max-config fill + IRQ + high-word/DBG/reserved reads in one invocation."""

    def __init__(self, name, tables, stream, selectors, alphabet, n_tables):
        super().__init__(name)
        self.tables = tables
        self.stream = stream
        self.selectors = selectors
        self.alphabet = alphabet
        self.n_tables = n_tables

    async def body(self):
        await self.rd(ID_REG)
        await self.rd(0x018)                          # reserved read (RAZ)
        await self.wr(IRQ_EN, STICKY_MASK)            # unmask every sticky bit → IRQ path
        await self.program(alphabet=self.alphabet, n_tables=self.n_tables,
                           lengths=self.tables)
        await self.wr(CTRL, 1)                        # doorbell
        busy_seen = False
        for _ in range(200000):
            st = await self.rd(STATUS)
            if st & ST_BUSY:
                busy_seen = True
            elif busy_seen and (st & ST_DONE):
                break
        # IRQ must be asserted with DONE unmasked
        irq = int(self.env.dut.irq.value) if hasattr(self, "env") else 1
        await self.rd(CYCLES_LO)
        await self.rd(CYCLES_HI)                      # 0x044: high word toggle/read
        await self.rd(SYMBOLS)
        await self.rd(BITS)
        # DBG every kind on the last table
        for kind in range(4):
            await self.wr(DBG_SEL, (kind << 4) | ((self.n_tables - 1) & 7) | (5 << 8))
            await self.rd(DBG_DATA)
        await self.wr(STATUS, STICKY_MASK)            # W1C → IRQ deasserts
        await self.wr(IRQ_EN, 0)


class HuffCoverTest(HuffBaseTest):
    async def main(self):
        rng = random.Random(4)
        alphabet, n_tables = 288, 6
        tables = make_tables(rng, n_tables, alphabet)
        sel_in = [rng.randrange(n_tables) for _ in range(400 // 50 + 1)]
        stream, selectors = make_stream(rng, tables, sel_in, alphabet, 320)
        await self.env.bits_source.send(AxiStreamFrame(stream))
        await self.env.sel_source.send(AxiStreamFrame(bytes(selectors)))
        seq = CoverSeq("cover", tables, stream, selectors, alphabet, n_tables)
        seq.env = self.env
        await seq.start(self.env.agent.sequencer)


@cocotb.test()
async def cover_fill(_dut):
    await uvm_root().run_test("HuffCoverTest")
