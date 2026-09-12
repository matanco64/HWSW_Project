"""Smoke sequence (testplan F-01 bring-up): program one tiny bzip2 table, doorbell, poll
to DONE (BUSY-fall), W1C, read the counters back. All register traffic goes through the
AXI agent; the scoreboard checks everything from the monitor streams."""
from axi_lite_agent import AxiLiteSeqItem
from pyuvm import uvm_sequence

from env import (ALPHABET, BITS, BUILD_CYCLES, CTRL, CYCLES_LO, ID_REG, LEN_BASE, MODE,
                 N_TABLES, START_BIT, ST_BUSY, ST_DONE, STATUS, SYMBOL_LIMIT, SYMBOLS)


def pack_lengths(all_lengths, alphabet):
    """Pack per-table length lists into LEN window words: table t occupies the fixed
    48-word stride LEN_BASE + 48·t (MAS §4 amendment 2026-09-08); 6 x 5-bit fields per
    word. Every word covering the alphabet is emitted (zeros included) so a re-programmed
    stride never inherits stale fields (review B10)."""
    words = {}
    for t, lens in enumerate(all_lengths):
        assert len(lens) == alphabet, f"table {t}: {len(lens)} lengths != ALPHABET {alphabet}"
        for w in range(48 * t, 48 * t + (alphabet + 5) // 6):
            words[w] = 0
        for s, l in enumerate(lens):
            w = 48 * t + s // 6
            words[w] |= (l & 0x1F) << (5 * (s % 6))
    return words


class HuffBaseSeq(uvm_sequence):
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

    async def program(self, *, mode=0, start_bit=0, alphabet=0, n_tables=1,
                      symbol_limit=1 << 20, lengths=None):
        await self.wr(MODE, mode)
        await self.wr(START_BIT, start_bit)
        await self.wr(ALPHABET, alphabet)
        await self.wr(N_TABLES, n_tables)
        await self.wr(SYMBOL_LIMIT, symbol_limit)
        for w, val in sorted(pack_lengths(lengths, alphabet).items()):
            await self.wr(LEN_BASE + 4 * w, val)

    async def run_to_done(self, max_polls=2000, outcome_mask=ST_DONE):
        """Doorbell, then poll STATUS until !BUSY with an outcome bit set (DONE by
        default; error tests pass their expected sticky mask). Requires BUSY observed
        or an outcome NOT present before the doorbell — grape S1/review B6."""
        before = await self.rd(STATUS)
        await self.wr(CTRL, 1)                       # doorbell
        busy_seen = False
        for _ in range(max_polls):
            status = await self.rd(STATUS)
            if status & ST_BUSY:
                busy_seen = True
                continue
            if busy_seen and (status & outcome_mask):
                return status
            if not busy_seen and (status & outcome_mask) and not (before & outcome_mask):
                return status                        # completed between polls
        raise AssertionError(
            f"outcome 0x{outcome_mask:x} not seen within {max_polls} polls "
            f"(busy_seen={busy_seen}, last STATUS 0x{status:x})")


class SmokeSeq(HuffBaseSeq):
    """One table, alphabet 4, lengths [1,2,3,3]: decode s0 s1 s2 s0 EOB (10 code bits)."""

    async def body(self):
        ident = await self.rd(ID_REG)
        assert ident == 0x48554631, f"ID reg 0x{ident:08x} != 'HUF1'"
        await self.program(alphabet=4, n_tables=1, lengths=[[1, 2, 3, 3]])
        status = await self.run_to_done()
        await self.wr(STATUS, ST_DONE)               # W1C
        await self.rd(STATUS)
        await self.rd(SYMBOLS)
        await self.rd(BITS)
        await self.rd(CYCLES_LO)
        await self.rd(BUILD_CYCLES)
