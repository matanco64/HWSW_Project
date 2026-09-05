"""Unit test for fp64_rcp_nr (rtl_contracts.md unit test contract).

Checks every result and flag word bit-exactly against the numpy oracle
``fp_helpers.ref_op("rcp", a)`` (== numpy's 1.0/a), plus the timing contract:
out_valid exactly LATENCY = 22 cycles after in_valid, streaming at II = 2.

Run (from the repo root; PYTHONPATH is exported by hw/common/Makefile.cocotb,
which puts ``tb/`` on the path so this file resolves as package module
``unit.test_fp64_rcp`` — same invocation pattern as the skid-buffer smoke test
hw/common/tb/tests/test_skid_buffer.py, whose module is likewise found via the
Makefile's exported PYTHONPATH):

    source hw/env.sh
    make -C hw/grape_pipeline sim TOPLEVEL=fp64_rcp_nr MODULE=unit.test_fp64_rcp

Fixed seed (SEED_BASE below); cocotb's own RANDOM_SEED is not used.

HARD_BOUNDARY below are factoring-constructed near-boundary vectors: mantissas M
dividing 2^(54+p) -+ k with odd cofactor and small k, so the exact reciprocal lies
within k/(2M) ~ k*2^-54 of an RNE rounding boundary at result precision p+1 bits
(p = 52 normal, 51/50 for subnormal results). These are the worst rounding cases
that exist for this operation; a faithful-but-not-correct rounding implementation
fails them.
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge

from unit.fp_helpers import f2b, ref_op

LATENCY = 22  # must match localparam LATENCY in fp64_rcp_nr.sv
SEED_BASE = 20260905  # fixed seed for reproducible random stimulus

ONE = f2b(1.0)

# Near-boundary hard cases (see module docstring). Both signs of the boundary
# offset, all three result precisions (normal / subnormal shift 1 / shift 2).
HARD_BOUNDARY = [
    0x113FFFFFF8000001,
    0x14313DEFF6B41E35,
    0x143334ADFE7A8DDB,
    0x14361C2909F39D4B,
    0x143EF43974550F69,
    0x143FFFFFF8000001,
    0x143FFFFFFFFFFFFD,
    0x143FFFFFFFFFFFFF,
    0x37461C2909F39D4B,
    0x3FA13DEFF6B41E35,
    0x3FA334ADFE7A8DDB,
    0x3FA61C2909F39D4B,
    0x3FAEF43974550F69,
    0x3FAFFFFFF8000001,
    0x3FAFFFFFFFFFFFFD,
    0x3FAFFFFFFFFFFFFF,
    0x3FF13DEFF6B41E35,
    0x3FF334ADFE7A8DDB,
    0x3FFFFFFFF8000001,
    0x3FFFFFFFFFFFFFFF,
    0x6A0FFFFFFFFFFFFF,
    0x6BB334ADFE7A8DDB,
    0x6BBFFFFFF8000001,
    0x6BBFFFFFFFFFFFFF,
    0x6BD334ADFE7A8DDB,
    0x7FD013B18ADB4CC9,
    0x7FD01B8DEF9E5187,
    0x7FD098546E106311,
    0x7FD09C2CD9A9752B,
    0x7FD0E9D3B7E10A6F,
    0x7FD14390E9E806A9,
    0x7FD15B635AD48A41,
    0x7FD15DCC5D19718B,
    0x7FD173E9E1CF7E77,
    0x7FD1EDB348DBFE63,
    0x7FD206510E5283F1,
    0x7FD27C89F605BFD9,
    0x7FD28F47FFFDAE17,
    0x7FD2EB6B451B14B9,
    0x7FD2F005F933845B,
    0x7FD326CF0ECA58DF,
    0x7FD3A64AC6287A4B,
    0x7FD3E45AC6E1B719,
    0x7FD3E7B517484E6B,
    0x7FD404B25A15C2BB,
    0x7FD41C0FE2B0DC07,
    0x7FD44D1A5F5D5651,
    0x7FD474DD987BCEA1,
    0x7FD486C278E17AD1,
    0x7FD49586739A5489,
    0x7FD4EB9046AE92AF,
    0x7FD57806FCA51601,
    0x7FD5A5E440E8D0BF,
    0x7FD5E9A23C9B1A79,
    0x7FD61129428247EF,
    0x7FD61ED9745FDB21,
    0x7FD7255CA25B68E1,
    0x7FD733B8284238F1,
    0x7FD75D929C3C2FC9,
    0x7FD7A6B0778D60C1,
    0x7FD7D93736C115FF,
    0x7FD90759A7F39561,
    0x7FD9385F4F83B2B1,
    0x7FD9939800033273,
    0x7FD9B8D7C084EE43,
    0x7FE0000000000001,
    0x7FE0AE08CB920061,
    0x7FE1634C8FA72CDB,
    0x7FE1A8D7958D9A5B,
    0x7FE1A9F22BDBA5A5,
    0x7FE211DC1CD0DE4D,
    0x7FE2222222222221,
    0x7FE2F80443BB1B25,
    0x7FE372FEC2EE192D,
    0x7FE528E734265AAD,
    0x7FE6BF350D597649,
    0x7FE783E57C25FDCF,
    0x7FE79CB84864C3CD,
    0x7FE7CEEF745D0B73,
    0x7FE7E9B8FFF0A5AF,
    0x7FE7FB282A0955B3,
    0x7FE7FCA7E889EA4D,
    0x7FE829230081F64B,
    0x7FE8495CDAAC82D1,
    0x7FE889C47B32E435,
    0x7FE8B3AC91007A47,
    0x7FE8ED7746FDC14B,
    0x7FEA9CD7762E19A7,
    0x7FEC6ED0219DC657,
    0x7FECDBC2E5DFEEED,
    0x7FEF7ADF5583F27D,
    0x7FEF9D5C70E28293,
    0x7FEF9F565678BD6D,
    0x913FFFFFF8000001,
    0x943334ADFE7A8DDB,
    0x943FFFFFF8000001,
    0x943FFFFFFFFFFFFF,
    0xBFA334ADFE7A8DDB,
    0xBFAFFFFFF8000001,
    0xBFAFFFFFFFFFFFFF,
    0xBFF334ADFE7A8DDB,
    0xBFFFFFFFF8000001,
    0xBFFFFFFFFFFFFFFF,
    0xEA0FFFFFFFFFFFFF,
    0xEBB334ADFE7A8DDB,
    0xEBBFFFFFF8000001,
    0xEBBFFFFFFFFFFFFF,
    0xEBD334ADFE7A8DDB,
    0xFFE0000000000001,
    0xFFE0AE08CB920061,
    0xFFE1634C8FA72CDB,
    0xFFE372FEC2EE192D,
    0xFFE6BF350D597649,
    0xFFE783E57C25FDCF,
    0xFFE7CEEF745D0B73,
    0xFFE8B3AC91007A47,
    0xFFEA9CD7762E19A7,
    0xFFEC6ED0219DC657,
    0xFFECDBC2E5DFEEED,
    0xFFEF7ADF5583F27D,
]


def directed_ops():
    """Directed cases from the contract + task list (rcp-specific)."""
    ops = [
        0x0000000000000000, 0x8000000000000000,  # +-0 -> +-inf, divzero
        0x7FF0000000000000, 0xFFF0000000000000,  # +-inf -> +-0, no flags
        0x7FF8000000000000, 0xFFF8000000000000,  # +-qNaN -> canonical qNaN, no invalid
        0x7FF0000000000001, 0xFFF0000000000001,  # +-sNaN -> canonical qNaN, invalid
        0x7FFDEADBEEFDEADB, 0x7FF7DEADBEEFDEAD,  # payload qNaN / sNaN
        0x0000000000000001, 0x8000000000000001,  # min subnormal -> +-inf, overflow
        0x000FFFFFFFFFFFFF, 0x800FFFFFFFFFFFFF,  # max subnormal -> huge normal
        0x0010000000000000, 0x8010000000000000,  # min normal -> 2^1022 exact
        0x7FEFFFFFFFFFFFFF, 0xFFEFFFFFFFFFFFFF,  # DBL_MAX -> subnormal, underflow
        0x7FE0000000000001,                      # (1+ulp)*2^1023 -> shift-2 subnormal
        0x7FE0000000000000, 0x7FD0000000000000,  # 2^1023 -> exact subnormal 2^-1023
        ONE, ONE + 1, ONE - 1,                   # 1.0, 1.0 +- ulp
        f2b(-1.0), f2b(-1.0) + 1,
        f2b(2.0), f2b(0.5), f2b(-2.0), f2b(3.0), f2b(10.0),
        f2b(0.01),                               # the benchmark's dt = 0.01
    ]
    # Powers of two both directions: exact reciprocals, incl. every interesting
    # edge (2^-1074..: 1/subnormal-pow2 -> inf overflow; 2^1023 -> 2^-1023 exact
    # subnormal; 2^1022 -> min normal).
    for k in range(-1022, 1024, 41):
        ops.append((k + 1023) << 52)             # +2^k
        ops.append((1 << 63) | ((k + 1023) << 52))
    for k in [-1022, -1021, 1020, 1021, 1022, 1023]:
        ops.append((k + 1023) << 52)
    for sh in [0, 1, 25, 49, 50, 51]:            # subnormal powers of two 2^(-1074+sh)
        ops.append(1 << sh)
        ops.append((1 << 63) | (1 << sh))
    # Subnormal-result inputs both directions of the subnormal edge, and subnormal
    # inputs with non-trivial mantissas (overflow threshold 1/x vs DBL_MAX).
    for base in [0x7FE0000000000000, 0x7FDFFFFFFFFFFFFF, 0x0010000000000000,
                 0x000FFFFFFFFFFFFF, 0x0004000000000000, 0x0000000000000003]:
        for off in (-2, -1, 0, 1, 2):
            b = (base + off) & ((1 << 63) - 1)
            if ((b >> 52) & 0x7FF) != 0x7FF:
                ops.append(b)
    # Typical benchmark d3 magnitudes ~1e-2..1e5 (rcp feeds mag = dt/d3).
    for v in [1e-2, 3.7e-1, 1.0e0, 4.2e1, 9.99e2, 1.3e4, 1e5, 2.5e3]:
        ops.append(f2b(v))
        ops.append(f2b(-v))
    # Constructed halfway/rounding-boundary cases (both boundary sides, all p).
    ops.extend(HARD_BOUNDARY)
    return ops


def random_ops(n_bits=10000, n_window=10000):
    """20,000 random ops: uniform 64-bit patterns (all classes: normals,
    subnormals, zeros, infs, NaNs, both signs) AND magnitude-window reals
    covering both the contract window 1e-5..1e2 and the rcp-specific d3 window
    1e-2..1e5."""
    rng = random.Random(SEED_BASE + 1)
    ops = [rng.getrandbits(64) for _ in range(n_bits)]
    for i in range(n_window):
        lo, hi = (-5.0, 2.0) if i % 2 == 0 else (-2.0, 5.0)
        v = 10.0 ** rng.uniform(lo, hi) * rng.choice([1.0, -1.0])
        ops.append(f2b(v))
    return ops


async def run_ops(dut, ops, gaps=None, name=""):
    """Drive `ops` (gap[i] cycles between issue i and i+1, default II=2 streaming),
    monitor out_valid, and check bits + flags + exact latency 22 for every op.
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
                # ReadOnly sees the post-NBA value: out_valid was registered at
                # this edge, so a synchronous consumer samples it at edge + 1;
                # record that edge so latency counts register levels the same
                # way in_valid does.
                outputs.append((edge + 1, int(dut.result.value), int(dut.flags.value)))

    mon = cocotb.start_soon(monitor())

    # Drive on falling edges so inputs are stable across each rising edge.
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
        ebits, eflags = ref_op("rcp", abits)
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
    """Directed: specials, powers of two, 1.0+-ulp, subnormal both directions,
    overflow/underflow edges, dt=0.01, d3 window, constructed halfway cases."""
    await run_ops(dut, directed_ops(), name="directed")


@cocotb.test()
async def test_random(dut):
    """20,000 random ops: uniform 64-bit patterns + magnitude windows."""
    await run_ops(dut, random_ops(), name="random")


@cocotb.test()
async def test_latency_single(dut):
    """A lone op: out_valid exactly LATENCY = 22 cycles after in_valid."""
    await run_ops(dut, [f2b(2.0)], gaps=[LATENCY + 10], name="single")


@cocotb.test()
async def test_ii2_stream(dut):
    """II = 2 streaming: 64 ops every 2 cycles; outputs stream at exactly
    2-cycle spacing with latency 22 each; then an irregular >= 2 gap pattern."""
    rng = random.Random(SEED_BASE + 2)
    ops = [rng.getrandbits(64) for _ in range(64)]
    pairs = await run_ops(dut, ops, gaps=[2] * len(ops), name="ii2")
    out_edges = [oe for _, oe in pairs]
    for k in range(1, len(out_edges)):
        d = out_edges[k] - out_edges[k - 1]
        assert d == 2, f"ii2: output spacing {d} != 2 between ops {k-1},{k}"
    # irregular legal spacing (>= 2) keeps every op independent and correct
    ops2 = [f2b(10.0 ** rng.uniform(-2.0, 5.0)) for _ in range(40)]
    gaps2 = [rng.choice([2, 2, 3, 5]) for _ in range(40)]
    await run_ops(dut, ops2, gaps=gaps2, name="ii-irregular")
