"""Error-injection sequences (testplan F-09/F-10/F-26; MAS §4/§8 error rows).

`ErrInvSeq` drives ONE invocation: writes the five config registers (LEN window only
when `lengths` is given), applies optional raw register writes (e.g. a corrupt LEN
word for F-26 badlen), rings the doorbell, and lands on the expected sticky outcome:

- `reject=True` (doorbell-time ERR_PARAM / ERR_TABLE badlen): MAS §5 ADR-0005 — the
  rejection flag is visible in STATUS by the time BRESP returns, and BUSY must never
  rise. A short bounded poll tolerates a couple of cycles of skew but fails on BUSY.
- otherwise: `run_to_done(outcome_mask=...)` from HuffBaseSeq (grape S1 poll pattern).

After the outcome: optional config read-backs (`readback`, proves a rejected doorbell
left the config registers untouched), optional SYMBOLS/BITS reads (the scoreboard
cross-checks SYMBOLS against its golden prefix; BITS on error invocations is not
auto-checked — the test records the observed value), then a FULL W1C of every sticky
bit (STATUS <= 0xFF06 = STICKY_MASK) so the next invocation starts from a clean
sticky mirror. The scoreboard (env.py v2) predicts every outcome independently from
golden primitives; these sequences only engineer the stimulus."""
from env import (ALPHABET, BITS, CTRL, LEN_BASE, MODE, N_TABLES, START_BIT, ST_BUSY,
                 ST_DONE, STATUS, STICKY_MASK, SYMBOL_LIMIT, SYMBOLS)
from smoke import HuffBaseSeq, pack_lengths

# the smoke-test known table (MAS example): codes 0, 10, 110, 111; EOB = sym3 = 111
GOOD_LENGTHS = [[1, 2, 3, 3]]
GOOD_STREAM = bytes([0x59, 0xC0])       # '0 10 110 0 111' -> s0 s1 s2 s0 EOB (10 bits)
GOOD_SELS = bytes([0])
GOOD_SYMBOLS = 5
GOOD_BITS = 10


class ErrInvSeq(HuffBaseSeq):
    """One configurable invocation ending in `outcome` (a sticky STATUS bit)."""

    def __init__(self, name="err_inv", *, mode=0, start_bit=0, alphabet=4, n_tables=1,
                 symbol_limit=1 << 20, lengths=None, raw_writes=(), outcome=ST_DONE,
                 reject=False, read_counters=True, readback=(), max_polls=2000):
        super().__init__(name)
        self.mode, self.start_bit = mode, start_bit
        self.alphabet, self.n_tables, self.symbol_limit = alphabet, n_tables, symbol_limit
        self.lengths = lengths                  # None: leave the LEN window as-is
        self.raw_writes = tuple(raw_writes)
        self.outcome, self.reject = outcome, reject
        self.read_counters = read_counters
        self.readback = tuple(readback)
        self.max_polls = max_polls
        self.status = self.symbols = self.bits = None

    async def body(self):
        await self.wr(MODE, self.mode)
        await self.wr(START_BIT, self.start_bit)
        await self.wr(ALPHABET, self.alphabet)
        await self.wr(N_TABLES, self.n_tables)
        await self.wr(SYMBOL_LIMIT, self.symbol_limit)
        if self.lengths is not None:
            for w, val in sorted(pack_lengths(self.lengths, self.alphabet).items()):
                await self.wr(LEN_BASE + 4 * w, val)
        for addr, val in self.raw_writes:
            await self.wr(addr, val)

        if self.reject:
            # doorbell-time rejection: flag sticky, BUSY never rises (MAS §8 F9 row)
            await self.wr(CTRL, 1)
            st = await self.rd(STATUS)
            for _ in range(8):
                assert not (st & ST_BUSY), (
                    f"{self.get_name()}: BUSY rose after a doorbell that must be "
                    f"rejected (STATUS=0x{st:x})")
                if st & self.outcome:
                    break
                st = await self.rd(STATUS)
            assert (st & self.outcome) and not (st & ST_BUSY), (
                f"{self.get_name()}: expected sticky 0x{self.outcome:x} with no BUSY, "
                f"got STATUS=0x{st:x}")
            self.status = st
        else:
            self.status = await self.run_to_done(
                max_polls=self.max_polls, outcome_mask=self.outcome)

        for addr, exp in self.readback:            # config unchanged by the rejection
            got = await self.rd(addr)
            assert got == exp, (
                f"{self.get_name()}: config @0x{addr:03x} changed by rejected "
                f"doorbell: read 0x{got:x}, wrote 0x{exp:x}")

        if self.read_counters:
            self.symbols = await self.rd(SYMBOLS)
            self.bits = await self.rd(BITS)

        await self.wr(STATUS, STICKY_MASK)         # full W1C (0xFF06) between invocations
