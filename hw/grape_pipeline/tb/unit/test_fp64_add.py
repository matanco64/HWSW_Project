"""Unit test for fp64_add (docs/rtl_contracts.md) against the tb/unit/fp_helpers oracle.

Exact green command (from the repo root, after ``source hw/env.sh``)::

    make -C hw/grape_pipeline sim TOPLEVEL=fp64_add MODULE=unit.test_fp64_add \
        VERILOG_SOURCES="rtl/fp64_pkg.sv rtl/fp64_add.sv"

hw/common/Makefile.cocotb already puts <module>/tb on PYTHONPATH, so this file is
importable as ``unit.test_fp64_add`` (tb/unit/__init__.py makes tb/unit a package).
VERILOG_SOURCES is passed on the command line because the Makefile's rtl/*.sv wildcard
also matches unrelated units; rtl/fp64_add.sv ``include``s rtl/fp64_pkg.sv itself, but
listing the package first keeps the compile order robust.  RNG seed fixed at SEED = 1.

Checks (rtl_contracts.md unit test contract): directed corner cases (specials,
subnormals, halfway-rounding, benchmark dt), 10,000 uniform bit-pattern ops, 10,000
magnitude-window (1e-5..1e2) ops — result bits AND flags compared against
fp_helpers.ref_op — plus an out_valid latency (exactly LATENCY = 3) and II = 1 check.
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge

from unit.fp_helpers import f2b, ref_op

LATENCY = 3        # contract: out_valid exactly 3 cycles after in_valid
SEED = 1           # fixed RNG seed for reproducibility
N_RANDOM = 10_000  # ops per random category

# directed corner values (raw bit patterns)
Z_P = 0x0000000000000000   # +0
Z_N = 0x8000000000000000   # -0
INF_P = 0x7FF0000000000000
INF_N = 0xFFF0000000000000
QNAN = 0x7FF8000000000000
QNANP = 0x7FF800000000BEEF  # quiet NaN with payload
SNAN = 0x7FF0000000000001   # signaling NaN
SNANN = 0xFFF0000000000001
SMIN = 0x0000000000000001   # minimum subnormal
SMAX = 0x000FFFFFFFFFFFFF   # maximum subnormal
SMID = 0x0008000000000000
NMIN = 0x0010000000000000   # minimum normal
NMAX = 0x7FEFFFFFFFFFFFFF   # maximum normal
ONE = f2b(1.0)

DIRECTED_VALUES = [
    Z_P, Z_N, INF_P, INF_N, QNAN, QNANP, SNAN, SNANN,
    SMIN, SMIN | (1 << 63), SMAX, SMID, NMIN, NMAX, NMAX | (1 << 63),
    ONE, ONE + 1, ONE - 1, f2b(2.0), f2b(0.01),           # 1.0 +/- 1 ulp, benchmark dt
    f2b(2.0 ** -52), f2b(2.0 ** -53), f2b(2.0 ** -54),    # halfway-rounding neighbours
]

# targeted (a_bits, b_bits, sub) pairs: rounding boundaries and subnormal edges
DIRECTED_PAIRS = [
    (ONE, f2b(2.0 ** -53), 0),        # tie -> stays 1.0 (round to even)
    (ONE, f2b(2.0 ** -53), 1),
    (ONE + 1, f2b(2.0 ** -53), 0),    # tie with odd LSB -> rounds up
    (ONE, f2b(2.0 ** -54), 0),        # below half an ulp -> stays 1.0
    (ONE, f2b(2.0 ** -54), 1),        # 1 - 2^-54: tie at the binade boundary -> 1.0
    (NMIN, SMIN | (1 << 63), 0),      # min normal - min subnormal = max subnormal, exact
    (NMIN, SMIN, 1),
    (SMAX, SMIN, 0),                  # max subnormal + min subnormal = min normal, exact
    (NMAX, f2b(2.0 ** 970), 0),       # halfway to overflow -> rounds to +inf, overflow
    (NMAX, f2b(2.0 ** 969), 0),       # below halfway -> stays NMAX, no flags
    (f2b(1.5), f2b(1.5), 1),          # exact cancellation -> +0
    (f2b(-1.5), f2b(-1.5), 1),        # -1.5 - (-1.5) = +0 (RNE exact-zero sign rule)
]


def _expected(ops):
    return [ref_op("sub" if s else "add", a, b) for (a, b, s) in ops]


async def _init(dut):
    """Start the clock (fresh per test: cocotb kills tasks between tests) and reset."""
    Clock(dut.clk, 10, "ns").start()
    dut.in_valid.value = 0
    dut.sub.value = 0
    dut.a.value = 0
    dut.b.value = 0
    dut.rst_n.value = 0
    for _ in range(4):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


async def _stream_check(dut, ops, gap_rng=None, gap_prob=0.0):
    """Drive ops back-to-back (optionally with idle gaps); check bits, flags and latency.

    Driver and monitor count the same clock edges, so asserting
    out_edge - drive_edge == LATENCY for every op verifies both the fixed latency and,
    for gap-free streams, II = 1 (back-to-back results on consecutive cycles).
    """
    exp = _expected(ops)
    got = []
    out_edges = []
    edge = [0]

    async def monitor():
        while len(got) < len(ops):
            await RisingEdge(dut.clk)
            edge[0] += 1
            await ReadOnly()
            if dut.out_valid.value == 1:
                got.append((int(dut.result.value), int(dut.flags.value)))
                out_edges.append(edge[0])

    mon = cocotb.start_soon(monitor())
    drive_edges = []
    my_edge = 0
    i = 0
    while i < len(ops):
        if gap_rng is not None and gap_rng.random() < gap_prob:
            dut.in_valid.value = 0
        else:
            a_bits, b_bits, s = ops[i]
            dut.in_valid.value = 1
            dut.a.value = a_bits
            dut.b.value = b_bits
            dut.sub.value = s
            drive_edges.append(my_edge)
            i += 1
        await RisingEdge(dut.clk)
        my_edge += 1
    dut.in_valid.value = 0
    for _ in range(LATENCY + 20):
        if mon.done():
            break
        await RisingEdge(dut.clk)
    assert mon.done(), f"only {len(got)}/{len(ops)} results came out"
    # drain: no spurious out_valid after the last expected result
    for _ in range(LATENCY + 2):
        await RisingEdge(dut.clk)
        await ReadOnly()
        assert dut.out_valid.value == 0, "spurious out_valid after drain"
    await RisingEdge(dut.clk)  # leave the read-only phase before the caller writes again
    mismatches = []
    for k, ((eb, ef), (gb, gf)) in enumerate(zip(exp, got)):
        if eb != gb or ef != gf:
            a_bits, b_bits, s = ops[k]
            mismatches.append(
                f"op[{k}] a={a_bits:016x} b={b_bits:016x} sub={s}: "
                f"expected {eb:016x}/{ef:04b} got {gb:016x}/{gf:04b}"
            )
    assert not mismatches, (
        f"{len(mismatches)} mismatches; first 10:\n" + "\n".join(mismatches[:10])
    )
    lat_bad = [(d, o) for d, o in zip(drive_edges, out_edges) if o - d != LATENCY]
    assert not lat_bad, f"latency violations (drive_edge, out_edge): {lat_bad[:10]}"


@cocotb.test()
async def test_directed(dut):
    """All-pairs specials/subnormals/rounding-boundary cross plus targeted pairs."""
    await _init(dut)
    ops = [(x, y, s) for x in DIRECTED_VALUES for y in DIRECTED_VALUES for s in (0, 1)]
    ops += DIRECTED_PAIRS
    await _stream_check(dut, ops)


@cocotb.test()
async def test_random_bit_patterns(dut):
    """10,000 uniform 64-bit bit-pattern operand pairs with random sub."""
    await _init(dut)
    rng = random.Random(SEED)
    ops = [(rng.getrandbits(64), rng.getrandbits(64), rng.getrandbits(1))
           for _ in range(N_RANDOM)]
    await _stream_check(dut, ops)


def _window_bits(rng):
    """Log-uniform magnitude in the benchmark window 1e-5..1e2, random sign."""
    v = (10.0 ** rng.uniform(-5.0, 2.0)) * (1.0 if rng.random() < 0.5 else -1.0)
    return f2b(v)


@cocotb.test()
async def test_random_magnitude_window(dut):
    """10,000 magnitude-window (benchmark range) operand pairs with random sub."""
    await _init(dut)
    rng = random.Random(SEED + 1)
    ops = [(_window_bits(rng), _window_bits(rng), rng.getrandbits(1))
           for _ in range(N_RANDOM)]
    await _stream_check(dut, ops)


@cocotb.test()
async def test_latency_and_ii(dut):
    """out_valid exactly LATENCY cycles after in_valid, one cycle wide; II = 1 streaming."""
    await _init(dut)
    a_bits, b_bits = f2b(1.5), f2b(0.25)
    exp_bits, exp_flags = ref_op("add", a_bits, b_bits)
    dut.in_valid.value = 1
    dut.a.value = a_bits
    dut.b.value = b_bits
    dut.sub.value = 0
    await RisingEdge(dut.clk)  # the op is sampled on this edge
    dut.in_valid.value = 0
    for k in range(LATENCY - 1):
        await ReadOnly()
        assert dut.out_valid.value == 0, f"out_valid asserted {k + 1} cycle(s) early"
        await RisingEdge(dut.clk)
    await ReadOnly()
    assert dut.out_valid.value == 1, "out_valid not asserted exactly LATENCY cycles after in_valid"
    assert int(dut.result.value) == exp_bits and int(dut.flags.value) == exp_flags
    await RisingEdge(dut.clk)
    await ReadOnly()
    assert dut.out_valid.value == 0, "out_valid wider than the single issued op"
    await RisingEdge(dut.clk)
    # II = 1 burst (checked op-by-op by _stream_check) and a randomly-gapped stream
    rng = random.Random(SEED + 2)
    burst = [(f2b(float(i)), f2b(0.5), i % 2) for i in range(1, 33)]
    await _stream_check(dut, burst)
    gaps = [(rng.getrandbits(64), rng.getrandbits(64), rng.getrandbits(1))
            for _ in range(300)]
    await _stream_check(dut, gaps, gap_rng=rng, gap_prob=0.35)
