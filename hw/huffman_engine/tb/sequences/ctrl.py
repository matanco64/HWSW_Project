"""Control-semantics sequences (testplan F-11 abort, F-13 multiblock, F-14 reset,
F-21 selector boundary, F-24 DBG window, F-32 first-symbol latency).

All register traffic goes through the AXI agent (HuffBaseSeq); the scoreboard v2 in
env.py auto-checks beats/sticky/counters from the monitor streams, including abort
prefix semantics and the DONE-wins race. This file adds the TB-side canonical
bit-packer (testplan §3 `seq_stream`: encode side only, built on the golden Table's
canonical codes — decode checking stays the scoreboard's job) and the small
parameterized sequences the control tests compose."""
import canonical_model
from cocotb.utils import get_sim_time

from env import (CTRL, DBG_DATA, DBG_SEL, LEN_BASE, ST_BUSY, ST_DONE, STATUS,
                 STICKY_MASK, SYMBOLS, BITS)
from smoke import HuffBaseSeq

CLK_NS = 20.0                       # MAS §3: 50 MHz target (HuffBaseTest.clk_period_ns)

# hand-crafted tables (testplan: "small is faster")
T_A = [1, 2, 3, 3]                  # smoke table: alphabet 4, EOB = 3
T_B = [2, 2, 2, 2]                  # flat 2-bit table, alphabet 4
T_8 = [3] * 8                       # complete 3-bit table, alphabet 8 (DBG stale-slot prep)


# ---- TB encoder (golden Table canonical codes) -------------------------------------------
def canonical_codes(lengths):
    """symbol -> (code, len) canonical map derived from the golden Table."""
    t = canonical_model.Table(lengths, canonical_model.MAXLEN_BZ2)
    codes = {}
    for s, l in enumerate(lengths):
        if l:
            rank = sum(1 for s2 in range(s) if lengths[s2] == l)
            codes[s] = (t.first_code[l] + rank, l)
    return codes


def encode_block(tables, selectors, symbols):
    """Bit list (bzip2 MSB-first order) for `symbols` under the selector cadence:
    selectors[i // 50] picks the table of symbol i; `symbols` INCLUDES the final EOB."""
    maps = [canonical_codes(l) for l in tables]
    bits = []
    for i, s in enumerate(symbols):
        code, l = maps[selectors[i // 50]][s]
        bits += [(code >> (l - 1 - k)) & 1 for k in range(l)]
    return bits


def pack_bits(bits):
    """Pack a bit list into bytes, bit 0 = byte 0 MSB (bzip2 bit order, MAS §4)."""
    out = bytearray((len(bits) + 7) // 8)
    for i, b in enumerate(bits):
        if b:
            out[i >> 3] |= 0x80 >> (i & 7)
    return bytes(out)


# encoder sanity: must reproduce the proven smoke vector (s0 s1 s2 s0 EOB under T_A)
assert pack_bits(encode_block([T_A], [0], [0, 1, 2, 0, 3])) == bytes([0x59, 0xC0])


# ---- sequences ----------------------------------------------------------------------------
class ProgramDoorbellSeq(HuffBaseSeq):
    """Program a config and ring the doorbell; records the B-handshake time. The caller
    owns everything after (polls, aborts, resets)."""

    def __init__(self, name="pgm_db", cfg=None):
        super().__init__(name)
        self.cfg = cfg or {}
        self.t_doorbell = None

    async def body(self):
        await self.program(**self.cfg)
        await self.wr(CTRL, 1)
        self.t_doorbell = get_sim_time("ns")


class AbortSeq(HuffBaseSeq):
    """F-11: optionally wait for the live SYMBOLS counter to reach `sym_target`, then
    CTRL.ABORT and poll STATUS to !BUSY. Records symbols_at_abort, n_polls, cycles
    (abort B-handshake to the !BUSY read completing) and the final status."""

    def __init__(self, name="abort", sym_target=None, max_wait_polls=20000, max_polls=8):
        super().__init__(name)
        self.sym_target = sym_target
        self.max_wait_polls = max_wait_polls
        self.max_polls = max_polls
        self.symbols_at_abort = None
        self.status = None
        self.n_polls = None
        self.cycles = None
        self.t_abort = None

    async def body(self):
        if self.sym_target is not None:
            for _ in range(self.max_wait_polls):
                self.symbols_at_abort = await self.rd(SYMBOLS)
                if self.symbols_at_abort >= self.sym_target:
                    break
            else:
                raise AssertionError(
                    f"SYMBOLS never reached {self.sym_target} "
                    f"(last {self.symbols_at_abort})")
        await self.wr(CTRL, 2)                        # ABORT
        self.t_abort = get_sim_time("ns")
        status = 0
        for i in range(self.max_polls):
            status = await self.rd(STATUS)
            if not (status & ST_BUSY):
                self.status = status
                self.n_polls = i + 1
                self.cycles = (get_sim_time("ns") - self.t_abort) / CLK_NS
                return
        raise AssertionError(
            f"abort-to-!BUSY bound blown: still BUSY after {self.max_polls} "
            f"STATUS polls (last 0x{status:x})")


class W1CSeq(HuffBaseSeq):
    """Write-1-to-clear a sticky mask, read STATUS back (the scoreboard checks the
    sticky mirror; .status is for the test's own asserts)."""

    def __init__(self, name="w1c", mask=STICKY_MASK):
        super().__init__(name)
        self.mask = mask
        self.status = None

    async def body(self):
        await self.wr(STATUS, self.mask)
        self.status = await self.rd(STATUS)


class RunSeq(HuffBaseSeq):
    """Full invocation: program (plus optional extra raw LEN-word writes — driver
    contract: fields beyond the new ALPHABET must be zeroed when the alphabet shrinks),
    doorbell + poll to an outcome, optional W1C, read SYMBOLS/BITS (scoreboard-checked)."""

    def __init__(self, name="run", cfg=None, w1c_mask=ST_DONE, outcome_mask=ST_DONE,
                 max_polls=4000, read_counters=True, extra_len_words=None):
        super().__init__(name)
        self.cfg = cfg or {}
        self.w1c_mask = w1c_mask
        self.outcome_mask = outcome_mask
        self.max_polls = max_polls
        self.read_counters = read_counters
        self.extra_len_words = extra_len_words or {}
        self.status = None
        self.status_after_w1c = None
        self.symbols = None
        self.bits = None

    async def body(self):
        await self.program(**self.cfg)
        for w, val in sorted(self.extra_len_words.items()):
            await self.wr(LEN_BASE + 4 * w, val)
        self.status = await self.run_to_done(max_polls=self.max_polls,
                                             outcome_mask=self.outcome_mask)
        if self.w1c_mask:
            await self.wr(STATUS, self.w1c_mask)
            self.status_after_w1c = await self.rd(STATUS)
        if self.read_counters:
            self.symbols = await self.rd(SYMBOLS)
            self.bits = await self.rd(BITS)


class ReadRegsSeq(HuffBaseSeq):
    """Read a list of addresses into .values (the test asserts the expectations)."""

    def __init__(self, name="rdregs", addrs=()):
        super().__init__(name)
        self.addrs = list(addrs)
        self.values = {}

    async def body(self):
        for a in self.addrs:
            self.values[a] = await self.rd(a)


class PollSymbolsSeq(HuffBaseSeq):
    """Poll the live SYMBOLS counter until it reaches `target` (reads while BUSY are
    legal and scoreboard-neutral, MAS §4)."""

    def __init__(self, name="poll_sym", target=0, max_polls=20000):
        super().__init__(name)
        self.target = target
        self.max_polls = max_polls
        self.symbols = None

    async def body(self):
        for _ in range(self.max_polls):
            self.symbols = await self.rd(SYMBOLS)
            if self.symbols >= self.target:
                return
        raise AssertionError(f"SYMBOLS stuck at {self.symbols} < {self.target}")


class PollDoneSeq(HuffBaseSeq):
    """Poll STATUS until !BUSY with an outcome bit set (the doorbell was already rung
    by the caller — unlike run_to_done this never writes CTRL)."""

    def __init__(self, name="poll_done", outcome_mask=ST_DONE, max_polls=8000):
        super().__init__(name)
        self.outcome_mask = outcome_mask
        self.max_polls = max_polls
        self.status = None
        self.n_polls = None

    async def body(self):
        status = 0
        for i in range(self.max_polls):
            status = await self.rd(STATUS)
            if not (status & ST_BUSY) and (status & self.outcome_mask):
                self.status = status
                self.n_polls = i + 1
                return
        raise AssertionError(
            f"outcome 0x{self.outcome_mask:x} not seen in {self.max_polls} polls "
            f"(last STATUS 0x{status:x})")


class DbgSeq(HuffBaseSeq):
    """F-24 DBG window probes: for each (table, kind, index) write DBG_SEL and read
    DBG_DATA (MAS 0x114: [2:0] table, [5:4] kind, [16:8] index)."""

    def __init__(self, name="dbg", probes=()):
        super().__init__(name)
        self.probes = list(probes)
        self.values = {}

    async def body(self):
        for t, kind, idx in self.probes:
            await self.wr(DBG_SEL, ((idx & 0x1FF) << 8) | ((kind & 3) << 4) | (t & 7))
            self.values[(t, kind, idx)] = await self.rd(DBG_DATA)
