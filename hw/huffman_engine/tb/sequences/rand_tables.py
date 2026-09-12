"""Constrained-random table/stream generation + the randomized config sequences
(dv_coverage stage). Tables are KRAFT-COMPLETE by construction (random splitting of a
canonical tree, depths 1..MAXLEN_BZ2); canonical codes are derived from the golden
`canonical_model.Table` internals (first_code/base/symtab) — never re-implemented — and
every generated stream is round-tripped through `canonical_model.decode_bzip2_symbols`
before it is allowed near the DUT."""
import canonical_model
from canonical_model import MAXLEN_BZ2

from env import (ALPHABET, BITS, CTRL, CYCLES_LO, LEN_BASE, N_TABLES, START_BIT, ST_BUSY,
                 ST_DONE, ST_EBUSY, STATUS, STICKY_MASK, SYMBOLS)
from smoke import HuffBaseSeq


# ---- random Kraft-complete tables -------------------------------------------------------
def make_tables(rng, n_tables, alphabet):
    """n_tables random length lists, each exactly Kraft-complete (sum 2^-l == 1), every
    symbol used, lengths 1..MAXLEN_BZ2. Built by random leaf splitting of a canonical
    tree: start with the two depth-1 leaves and split a random leaf (depth < MAXLEN)
    until `alphabet` leaves exist; splitting preserves completeness by construction."""
    assert alphabet >= 2
    tables = []
    for _ in range(n_tables):
        depths = [1, 1]
        while len(depths) < alphabet:
            splittable = [k for k, d in enumerate(depths) if d < MAXLEN_BZ2]
            k = splittable[rng.randrange(len(splittable))]
            d = depths.pop(k)
            depths += [d + 1, d + 1]
        rng.shuffle(depths)                       # random symbol <-> depth assignment
        assert sum(1 << (MAXLEN_BZ2 - d) for d in depths) == 1 << MAXLEN_BZ2, \
            "internal: tree not Kraft-complete"
        tables.append(depths)
    return tables


# ---- canonical bit-packing (codes from the golden Table, MSB-first per byte) ------------
def codebook(lengths):
    """Per-symbol (code, len) from the golden canonical_model.Table: symbol s sits at
    index idx in symtab, so its code is first_code[l] + idx - base[l] (the exact inverse
    of Table.decode's symtab[base[l] + code - first_code[l]])."""
    t = canonical_model.Table(lengths, MAXLEN_BZ2)
    book = {}
    for idx, s in enumerate(t.symtab):
        l = lengths[s]
        book[s] = (t.first_code[l] + idx - t.base[l], l)
    return book


class _BitWriter:
    """Append bits MSB-first into bytes (bzip2 bit order)."""

    def __init__(self):
        self.buf = bytearray()
        self.nbits = 0

    def put(self, value, nbits):
        for i in range(nbits - 1, -1, -1):
            if self.nbits % 8 == 0:
                self.buf.append(0)
            if (value >> i) & 1:
                self.buf[-1] |= 0x80 >> (self.nbits % 8)
            self.nbits += 1

    def bytes(self):
        return bytes(self.buf)


def encode(symbols, lengths):
    """Pack `symbols` with the single canonical table `lengths` into an MSB-first-per-byte
    stream starting at bit 0."""
    book = codebook(lengths)
    w = _BitWriter()
    for s in symbols:
        code, l = book[s]
        w.put(code, l)
    return w.bytes()


def make_stream(rng, tables, selectors, alphabet, n_symbols, start_bit=0):
    """Random symbol stream: n_symbols symbols in 50-symbol selector groups, EOB
    (= alphabet-1) exactly once, as the very last symbol. `selectors` supplies the table
    index per group (extra entries are trimmed). start_bit random filler bits are packed
    ahead of the first code so the caller programs START_BIT = start_bit verbatim.
    Round-tripped through the golden decode_bzip2_symbols before returning.
    Returns (stream_bytes, selectors)."""
    eob = alphabet - 1
    n_groups = (n_symbols + 49) // 50
    assert len(selectors) >= n_groups, f"need {n_groups} selectors, got {len(selectors)}"
    selectors = list(selectors[:n_groups])
    assert all(0 <= s < len(tables) for s in selectors)
    # EOB terminates decode, so it must not appear before the end
    symbols = [rng.randrange(alphabet - 1) for _ in range(n_symbols - 1)] + [eob]
    books = [codebook(l) for l in tables]
    w = _BitWriter()
    for _ in range(start_bit):
        w.put(rng.randrange(2), 1)
    for i, s in enumerate(symbols):
        code, l = books[selectors[i // 50]][s]
        w.put(code, l)
    data = w.bytes()
    got, end_pos, _ = canonical_model.decode_bzip2_symbols(
        data, start_bit, tables, selectors, alphabet)
    assert got == symbols, "round-trip mismatch: encoder vs golden decoder"
    assert end_pos == w.nbits
    return data, selectors


# ---- sequences ---------------------------------------------------------------------------
class _RandSeqBase(HuffBaseSeq):
    async def clear_stride_tails(self, alphabet, n_tables):
        """DUT driver-contract gap (found by this suite, see tests_random.py docstring):
        huff_regs.sv folds ALL six 5-bit fields of every LEN word into the per-table
        Kraft count bins, alphabet-blind. pack_lengths (review B10) rewrites only the
        words covering the alphabet, so a stride reused with a SMALLER alphabet inherits
        stale beyond-alphabet fields in the bins and huff_builder flags ERR_TABLE
        (over-subscribed) on a perfectly Kraft-complete table — the golden model sees
        only in-alphabet lengths and predicts DONE. Workaround: zero the stride tail of
        every used table before the doorbell."""
        for t in range(n_tables):
            for w in range((alphabet + 5) // 6, 48):
                await self.wr(LEN_BASE + 4 * (48 * t + w), 0)


class RandCfgSeq(_RandSeqBase):
    """Program one prepared random config, doorbell, poll to DONE, W1C the observed
    sticky bits, read the counters back. Correctness (beats, sticky mirror, SYMBOLS/BITS)
    is asserted by the scoreboard from the monitor streams alone."""

    def __init__(self, name="randcfg", cfg=None):
        super().__init__(name)
        self.cfg = cfg
        self.counters = {}

    async def body(self):
        c = self.cfg
        await self.program(start_bit=c.get("start_bit", 0), alphabet=c["alphabet"],
                           n_tables=c["n_tables"],
                           symbol_limit=c.get("symbol_limit", 1 << 20),
                           lengths=c["lengths"])
        await self.clear_stride_tails(c["alphabet"], c["n_tables"])
        status = await self.run_to_done(max_polls=c.get("max_polls", 20000))
        await self.wr(STATUS, status & STICKY_MASK)          # W1C everything observed
        for name, addr in (("symbols", SYMBOLS), ("bits", BITS), ("cycles", CYCLES_LO)):
            self.counters[name] = await self.rd(addr)


class RandBusySeq(_RandSeqBase):
    """One long invocation with mid-run abuse: config-register writes while BUSY (must be
    ignored — the scoreboard mirror models the discard, so a DUT that latched them would
    fail the beat/counter comparison at DONE) and a second doorbell while BUSY (rejected,
    sticky ERR_BUSY, run unaffected; W1C'd while still BUSY). Needs `env` to wait for the
    stream sources to drain first: the rejected doorbell is a db_time in the scoreboard's
    B4 replay and would truncate the open invocation's stream window if bits/sel beats
    were still being accepted after it."""

    def __init__(self, name="busy", cfg=None, env=None):
        super().__init__(name)
        self.cfg = cfg
        self.env = env
        self.counters = {}

    async def body(self):
        c = self.cfg
        await self.program(start_bit=c.get("start_bit", 0), alphabet=c["alphabet"],
                           n_tables=c["n_tables"], symbol_limit=1 << 20,
                           lengths=c["lengths"])
        await self.clear_stride_tails(c["alphabet"], c["n_tables"])
        await self.wr(CTRL, 1)                               # doorbell
        status = await self.rd(STATUS)
        assert status & ST_BUSY, f"expected BUSY after doorbell, STATUS=0x{status:x}"
        for _ in range(60000):
            if self.env.bits_source.idle() and self.env.sel_source.idle():
                break
            status = await self.rd(STATUS)
            assert status & ST_BUSY, "run finished before the sources drained " \
                                     "(backpressure too light for this stream)"
        else:
            raise AssertionError("stream sources never drained")
        # BUSY-ignored config writes (MAS: only STATUS W1C / IRQ_EN / DBG_SEL live)
        await self.wr(ALPHABET, 4)
        await self.wr(N_TABLES, 1)
        await self.wr(START_BIT, 777)
        await self.wr(LEN_BASE, (2 << 5) | 1)
        # second doorbell while BUSY: rejected, ERR_BUSY sticky immediately
        await self.wr(CTRL, 1)
        status = await self.rd(STATUS)
        assert status & ST_EBUSY, f"ERR_BUSY not sticky after busy doorbell, " \
                                  f"STATUS=0x{status:x}"
        assert status & ST_BUSY, "run finished inside the busy-abuse window"
        await self.wr(STATUS, ST_EBUSY)                      # W1C while BUSY (allowed)
        for _ in range(120000):
            status = await self.rd(STATUS)
            if not (status & ST_BUSY):
                break
        assert status & ST_DONE, f"no DONE after busy abuse, STATUS=0x{status:x}"
        await self.wr(STATUS, ST_DONE)
        for name, addr in (("symbols", SYMBOLS), ("bits", BITS), ("cycles", CYCLES_LO)):
            self.counters[name] = await self.rd(addr)
