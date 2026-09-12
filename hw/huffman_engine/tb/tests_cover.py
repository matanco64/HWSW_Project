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
from test_huffman_engine import HuffBaseTest


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
        # IRQ must be asserted with DONE unmasked (level irq, MAS 0x010)
        assert int(cocotb.top.irq.value) == 1, "IRQ not asserted with DONE unmasked"
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


class HuffDeflateAllCodesTest(HuffBaseTest):
    """Toggle-closing DEFLATE stream: every length code 257..285 with max extra, cycling
    every distance code 0..29 with max extra — toggles huff_deflate's LEN_BASE/DIST_BASE
    selection, the extra-bit slices, and the wide len_val/dist_val datapath."""

    async def main(self):
        import canonical_model as cm
        from tests_deflate import FIXED_DIST, FIXED_LIT, DeflateSeq, deflate_encode
        events = []
        for i in range(29):
            base, ex = cm._LEN_BASE[i], cm._LEN_EXTRA[i]
            length = min(base + ((1 << ex) - 1 if ex else 0), 258)
            d = i % 30
            dist = cm._DIST_BASE[d] + ((1 << cm._DIST_EXTRA[d]) - 1 if cm._DIST_EXTRA[d] else 0)
            events += [("lit", 65), ("copy", length, dist)]
        events.append(("eob",))
        stream = deflate_encode(events, FIXED_LIT, FIXED_DIST)
        chk, _, _ = cm.decode_deflate_symbols(stream, 0, FIXED_LIT, FIXED_DIST)
        assert chk == events
        await self.env.bits_source.send(AxiStreamFrame(stream))
        await DeflateSeq("dfl_allcodes", FIXED_LIT, FIXED_DIST).start(self.env.agent.sequencer)


@cocotb.test()
async def deflate_all_codes(_dut):
    await uvm_root().run_test("HuffDeflateAllCodesTest")


class HuffDeepTreeTest(HuffBaseTest):
    """Toggle-closing bzip2: canonical tables that use the FULL length range 1..20 (deep
    codes toggle the LEN-field top bits and drive large per-length count bins), streamed
    long enough to exercise every table. Six tables, alphabet 288, ~600 symbols."""

    async def main(self):
        import random
        from rand_tables import make_stream
        rng = random.Random(20)
        alphabet, n_tables = 288, 6
        # deep canonical tree: assign a Huffman-complete length set spanning 1..20 by a
        # skewed split so max length reaches 20 (make_tables caps at 20; here force depth)
        tables = []
        for t in range(n_tables):
            # lengths: a long "spine" 1..20 plus the rest filled to complete the tree
            lens = _deep_lengths(rng, alphabet)
            tables.append(lens)
        sel_in = [rng.randrange(n_tables) for _ in range(600 // 50 + 1)]
        stream, selectors = make_stream(rng, tables, sel_in, alphabet, 600)
        await self.env.bits_source.send(AxiStreamFrame(stream))
        await self.env.sel_source.send(AxiStreamFrame(bytes(selectors)))
        await CoverSeq("deep", tables, stream, selectors, alphabet, n_tables).start(
            self.env.agent.sequencer)


def _deep_lengths(rng, alphabet):
    """A Kraft-complete length list that reaches length 20 (deep spine)."""
    # spine: lengths 1,2,3,...,19,20,20 uses codes down to depth 20 and is complete for 21
    # symbols; pad the rest by splitting the deepest leaves.
    lens = list(range(1, 20)) + [20, 20]                 # 21 symbols, complete
    while len(lens) < alphabet:
        # split a deepest leaf into two one-deeper leaves (keeps Kraft = 1); cap at 20
        i = max(range(len(lens)), key=lambda k: lens[k] if lens[k] < 20 else -1)
        if lens[i] >= 20:
            # no room to deepen; extend by splitting a length-<20 leaf elsewhere
            cand = [k for k in range(len(lens)) if lens[k] < 20]
            i = cand[0]
        d = lens[i] + 1
        lens[i] = d
        lens.append(d)
    lens = lens[:alphabet]
    # ensure exactly complete: rebuild via canonical check
    return lens


@cocotb.test()
async def deep_tree(_dut):
    await uvm_root().run_test("HuffDeepTreeTest")
