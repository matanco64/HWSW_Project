"""Constrained-random symbol-stream generation + the randomized invocation sequence
(dv_coverage stage 7). Mirrors the huffman_engine `rand_tables.py` discipline: a seeded
`random.Random`, streams built ONLY from valid tokens (used-map / N_USED, MTF ranks
1..N_USED-1, RUNA/RUNB run groups with n <= a bounded cap, exactly one EOB last), and every
generated stream is round-tripped through the FROZEN golden `list_model.expand` before it is
allowed near the DUT (no re-implementation of the MTF/run algorithm here). The scoreboard
remains the oracle; these sequences only engineer the stimulus and log `SEED=`.

Bijective base-2 run encoding (RUNA=0, RUNB=1): n = sum_k (1<<k)*(1+s_k). `n_to_runs` is the
exact inverse; validated against list_model.expand in dv (single-used-byte run == n bytes).
"""
import itertools
import random

import list_model

from env import (BYTES_LIMIT, CTRL, INIT_CYCLES, MAX_RUN, STATUS, ST_DONE, STICKY_MASK,
                 SYMBOLS_IN, BYTES_OUT, SYMBOL_LIMIT, USED_BASE, cov)
from smoke import MtfBaseSeq


def n_to_runs(n):
    """Bijective base-2 RUNA/RUNB symbols encoding a run length n >= 1 (RUNA=0, RUNB=1)."""
    assert n >= 1
    syms = []
    while n > 0:
        if n & 1:
            syms.append(0)
            n = (n - 1) // 2
        else:
            syms.append(1)
            n = (n - 2) // 2
    return syms


# ---- pause generators for the m_l sink (tready duty) ---------------------------------------
def pause_gen(kind, rng):
    """Return (itertools pause generator | None, coverage bin) for the requested backpressure."""
    if kind == "none":                                  # ~0 % backpressure: always ready
        return None, "duty_0"
    if kind == "half":                                  # ~50 % ready
        return (rng.random() < 0.5 for _ in itertools.count()), "duty_50"
    # heavy: ~90 % backpressure (ready ~10 %)
    return (rng.random() < 0.9 for _ in itertools.count()), "duty_90"


def make_random_stream(rng, *, max_used=40, max_tokens=120, run_cap=1500):
    """Build one valid (used_bytes, symbols, alphabet). Round-tripped through list_model.expand
    (raises would mean an invalid stream leaked past the constraints)."""
    n_used = rng.randint(2, max_used)
    used_bytes = sorted(rng.sample(range(256), n_used))
    alphabet = n_used + 2
    eob = alphabet - 1
    used = [False] * 256
    for b in used_bytes:
        used[b] = True

    symbols = []
    prev_run = False                                    # a run must be terminated by an MTF so two
    for _ in range(rng.randint(4, max_tokens)):         # run tokens never MERGE into one group and
        if n_used >= 2 and not prev_run and rng.random() < 0.45:   # overflow (each group <= run_cap)
            n = rng.randint(1, run_cap)                 # a run group
            symbols.extend(n_to_runs(n))
            prev_run = True
        else:                                           # an MTF symbol (rank 1..n_used-1)
            r = rng.randint(1, n_used - 1)
            symbols.append(r + 1)                       # value = rank + 1 (bzip2 MTF coding)
            prev_run = False
    symbols.append(eob)

    l_bytes, _ = list_model.expand(symbols, used, alphabet)   # validate: must not raise
    assert len(l_bytes) <= (1 << 20), "random stream drain exceeds BYTES_LIMIT"
    return used_bytes, symbols, alphabet


class RandStreamSeq(MtfBaseSeq):
    """Program a prepared random used-map + limits, doorbell, poll to DONE, W1C, read counters.
    All correctness (byte-exact L-vector, sticky mirror, counters) is asserted by the scoreboard
    from the monitor streams alone."""

    def __init__(self, name="rand", used_bytes=None):
        super().__init__(name)
        self.used_bytes = used_bytes
        self.counters = {}

    async def body(self):
        await self.program_used(self.used_bytes, symbol_limit=1 << 27, bytes_limit=1 << 30)
        status, _ = await self.run_to_done(max_polls=40000)
        assert status & ST_DONE, f"random run did not reach DONE, STATUS=0x{status:x}"
        for name, addr in (("symbols_in", SYMBOLS_IN), ("bytes_out", BYTES_OUT),
                           ("max_run", MAX_RUN), ("init_cycles", INIT_CYCLES)):
            self.counters[name] = await self.rd(addr)
        await self.wr(STATUS, status & STICKY_MASK)     # W1C everything observed
