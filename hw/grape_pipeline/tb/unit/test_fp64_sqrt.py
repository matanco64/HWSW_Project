"""Unit test for fp64_sqrt_srt (rtl_contracts.md unit test contract).

Checks every result and flag word bit-exactly against the numpy oracle
``fp_helpers.ref_op("sqrt", a)``, plus the timing contract: out_valid exactly
LATENCY = 30 cycles after in_valid, streaming at II = 2.

Run (from the repo root; PYTHONPATH is exported by hw/common/Makefile.cocotb,
which puts ``tb/`` on the path so this file resolves as package module
``unit.test_fp64_sqrt`` — same invocation pattern as the skid-buffer smoke test):

    source hw/env.sh
    make -C hw/grape_pipeline sim TOPLEVEL=fp64_sqrt_srt MODULE=unit.test_fp64_sqrt

Fixed seed (SEED_BASE below); cocotb's own RANDOM_SEED is not used.
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge

from unit.fp_helpers import f2b, ref_op

LATENCY = 30  # must match localparam LATENCY in fp64_sqrt_srt.sv
SEED_BASE = 20260904  # fixed seed for reproducible random stimulus

ONE = f2b(1.0)


def directed_ops():
    """Directed cases from the contract + task list."""
    ops = [
        0x0000000000000000, 0x8000000000000000,  # +0, -0 (signed zero passthrough)
        0x7FF0000000000000, 0xFFF0000000000000,  # +inf, -inf (-inf -> invalid qNaN)
        0x7FF8000000000000, 0xFFF8000000000000,  # +qNaN, -qNaN (quiet: no invalid)
        0x7FF0000000000001, 0xFFF0000000000001,  # +sNaN, -sNaN (invalid)
        0x7FFDEADBEEFDEADB, 0x7FF7DEADBEEFDEAD,  # payload qNaN / sNaN -> canonical out
        0xBFF0000000000000, 0xC000000000000000,  # -1.0, -2.0 (negative -> invalid qNaN)
        0x8000000000000001, 0x800FFFFFFFFFFFFF,  # negative subnormals -> invalid qNaN
        0x0000000000000001, 0x000FFFFFFFFFFFFF,  # subnormal min / max
        0x0000000000000002, 0x0008000000000000,  # more subnormals (odd/even exponent)
        0x0010000000000000, 0x7FEFFFFFFFFFFFFF,  # normal min / max
        ONE, ONE + 1, ONE - 1,                   # 1.0, 1.0 + ulp, 1.0 - ulp
        f2b(2.0), f2b(2.0) + 1, f2b(2.0) - 1,
        f2b(4.0), f2b(4.0) + 1, f2b(4.0) - 1,    # perfect square / power of 4 +- ulp
        f2b(0.25), f2b(0.0625), f2b(9.0),        # powers of 4, perfect square
        f2b(16.0), f2b(1024.0), f2b(2.25),       # more exact roots (incl. 1.5^2)
        f2b(0.01), f2b(1e-5), f2b(1e2),          # benchmark dt = 0.01 and window edges
    ]
    # Rounding-boundary halfway hunting: squares of 53-bit significands +-1/+-2 ulp
    # put sqrt just above/below an RNE decision boundary (the round bit flips on the
    # sticky computed from the final remainder). Fixed seed => reproducible.
    rng = random.Random(SEED_BASE)
    for _ in range(60):
        r = rng.getrandbits(52) | (1 << 52)  # random 53-bit significand
        ee = rng.randrange(-500, 500)
        v = r * (2.0 ** (ee - 52))
        sq = f2b(v * v)
        for d in (-2, -1, 0, 1, 2):
            b = sq + d
            if (b >> 63) == 0 and ((b >> 52) & 0x7FF) != 0x7FF:
                ops.append(b)
    return ops


def random_ops(n_bits=10000, n_window=10000):
    """Random cases: uniform non-negative bit patterns AND magnitude-window reals."""
    rng = random.Random(SEED_BASE + 1)
    ops = [rng.getrandbits(63) for _ in range(n_bits)]  # non-negative uniform bits
    for _ in range(n_window):
        ops.append(f2b(10.0 ** rng.uniform(-5.0, 2.0)))  # benchmark range 1e-5..1e2
    return ops


async def run_ops(dut, ops, gaps=None, name=""):
    """Drive `ops` (gap[i] cycles between issue i and i+1, default II=2 streaming),
    monitor out_valid, and check bits + flags + exact latency 30 for every op.
    Returns the list of (issue_edge, output_edge) pairs."""
    if gaps is None:
        gaps = [2] * len(ops)
    assert min(gaps) >= 2, "TB bug: II=2 contract requires spacing >= 2"

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.in_valid.value = 0
    dut.a.value = 0
    dut.rst_n.value = 0
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    for _ in range(3):
        await RisingEdge(dut.clk)

    issues = []   # (edge_index, operand_bits) as sampled at the DUT boundary
    outputs = []  # (edge_index, result_bits, flags)
    done = False

    async def monitor():
        edge = 0
        while not done:
            await RisingEdge(dut.clk)
            await ReadOnly()
            edge += 1
            if int(dut.in_valid.value) == 1:
                issues.append((edge, int(dut.a.value)))
            if int(dut.out_valid.value) == 1:
                # ReadOnly sees the post-NBA value: out_valid was registered at this
                # edge, so a synchronous consumer flop samples it at edge + 1. Record
                # that consumer-visible edge so latency counts register levels the
                # same way in_valid does (fp64_add with 3 registers <=> LATENCY 3).
                outputs.append((edge + 1, int(dut.result.value), int(dut.flags.value)))

    mon = cocotb.start_soon(monitor())

    # Drive on falling edges so inputs are stable across each rising edge: the DUT
    # samples in_valid at the same rising edge the monitor records it (no race with
    # the monitor's ReadOnly sampling).
    for op, gap in zip(ops, gaps):
        await FallingEdge(dut.clk)
        dut.a.value = op
        dut.in_valid.value = 1
        await FallingEdge(dut.clk)
        dut.in_valid.value = 0
        for _ in range(gap - 2):
            await FallingEdge(dut.clk)

    for _ in range(LATENCY + 4):  # drain
        await RisingEdge(dut.clk)
    done = True
    await RisingEdge(dut.clk)
    mon.kill()

    assert len(issues) == len(ops), f"{name}: monitor saw {len(issues)} issues != {len(ops)}"
    assert len(outputs) == len(ops), (
        f"{name}: {len(outputs)} out_valid pulses for {len(ops)} ops"
    )

    mismatches = 0
    for k, ((ie, abits), (oe, rbits, rflags)) in enumerate(zip(issues, outputs)):
        lat = oe - ie
        assert lat == LATENCY, f"{name}[{k}]: a={abits:016x} latency {lat} != {LATENCY}"
        ebits, eflags = ref_op("sqrt", abits)
        if rbits != ebits or rflags != eflags:
            mismatches += 1
            if mismatches <= 10:
                dut._log.error(
                    f"{name}[{k}]: a={abits:016x} got=({rbits:016x},{rflags:x}) "
                    f"exp=({ebits:016x},{eflags:x})"
                )
    assert mismatches == 0, f"{name}: {mismatches}/{len(ops)} result/flag mismatches"
    dut._log.info(f"{name}: {len(ops)} ops, 0 mismatches, latency {LATENCY} for all")
    return [(i[0], o[0]) for i, o in zip(issues, outputs)]


@cocotb.test()
async def test_directed(dut):
    """Directed: specials, subnormal extremes, perfect squares, 1.0+-ulp, halfway."""
    await run_ops(dut, directed_ops(), name="directed")


@cocotb.test()
async def test_random(dut):
    """20,000 random ops: uniform non-negative bit patterns + 1e-5..1e2 window."""
    await run_ops(dut, random_ops(), name="random")


@cocotb.test()
async def test_latency_single(dut):
    """A lone op: out_valid exactly LATENCY cycles after in_valid, single pulse."""
    await run_ops(dut, [f2b(2.0)], gaps=[LATENCY + 10], name="single")


@cocotb.test()
async def test_ii2_stream(dut):
    """II = 2 streaming: 64 back-to-back ops every 2 cycles; outputs must stream at
    exactly 2-cycle spacing with latency 30 each; then an irregular >= 2 gap pattern."""
    rng = random.Random(SEED_BASE + 2)
    ops = [rng.getrandbits(63) & ~(1 << 63) for _ in range(64)]
    pairs = await run_ops(dut, ops, gaps=[2] * len(ops), name="ii2")
    out_edges = [oe for _, oe in pairs]
    for k in range(1, len(out_edges)):
        d = out_edges[k] - out_edges[k - 1]
        assert d == 2, f"ii2: output spacing {d} != 2 between ops {k-1},{k}"
    # irregular legal spacing (>= 2) keeps every op independent and correct
    ops2 = [f2b(10.0 ** rng.uniform(-5.0, 2.0)) for _ in range(40)]
    gaps2 = [rng.choice([2, 2, 3, 5]) for _ in range(40)]
    await run_ops(dut, ops2, gaps=gaps2, name="ii-irregular")
