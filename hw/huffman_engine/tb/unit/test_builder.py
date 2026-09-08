"""Unit tests for huff_builder + huff_tables (uArch section 3.2, rtl_contracts.md builder/tables).

DUT: huff_build_tb_top (TB-only wrapper) — builder + tables plus small behavioral stand-ins for
huff_regs' lengths window ({t,sym} -> 5b, 1-cycle registered) and folded count bins ((t,l) -> 9b
comb), loaded by the test through simple write ports.

Oracle: golden/canonical_model.py class Table (its first_code/base/symtab/ERR_TABLE definitions
are mirrored exactly); benchmark lengths come from golden/pyflate_ref.trace_benchmark().

Cases:
  1. the REAL benchmark's 6 tables (bzip2 block 0): every set's first_code/base/limit_la,
     table_base-resolved symtab content, EOB latch, vs Table(lengths, 20)
  2. random Kraft-legal tables (incl. complete ladder/uniform codes and the complete-at-l<20
     first_code truncation edge)
  3. Kraft over-subscribed table -> err_table pulse and build abort (oracle raises ERR_TABLE)
  4. EOB latch lifecycle: updates on rebuild, PREP-entry clear of all six latches, DEFLATE
     distance set never latches (eob_len stays 0)
  5. build_cycles_o == alphabet + MAXLEN per table (K2 evidence: 167 for the benchmark's 147)

Run (from the repo root, after `source ./hw/env.sh`):

    make -C hw/huffman_engine sim TOPLEVEL=huff_build_tb_top MODULE=unit.test_builder \
        VERILOG_SOURCES="rtl/huff_builder.sv rtl/huff_tables.sv rtl/huff_build_tb_top.sv"

Notes (contract-faithful, decided here, contracts untouched):
  * table_base[t] = t*288 (fixed stride; documented in the RTL headers).
  * first_code is stored 20 bits wide; a code complete at length l < 20 makes the model's
    first_code[20] equal 2^20, which truncates to 0 in the stored field — harmless (that l can
    never win the decode compare) — so the comparison masks to 20 bits.
"""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

import pyflate_ref
from canonical_model import Table

MAXLEN = 20            # bzip2 MAXLEN; DEFLATE uses the same datapath with zero 16..20 bins
STRIDE = 288           # table_base[t] = t * STRIDE
MASK20 = (1 << 20) - 1
MASK21 = (1 << 21) - 1


# ---- oracle helpers ----------------------------------------------------------------------------

def extended_arrays(model):
    """first_code/count/base continued to l = MAXLEN with zero counts above model.maxlen —
    exactly what the hardware recurrence produces when it always runs l = 1..20 (DEFLATE)."""
    fc = list(model.first_code[: model.maxlen + 1])
    cnt = list(model.count[: model.maxlen + 1])
    base = list(model.base[: model.maxlen + 1])
    code = (fc[model.maxlen] + cnt[model.maxlen]) << 1
    idx = base[model.maxlen] + cnt[model.maxlen]
    for _ in range(model.maxlen + 1, MAXLEN + 1):
        fc.append(code)
        cnt.append(0)
        base.append(idx)
        code <<= 1
    return fc, cnt, base


def expected_limit_la(model, l):
    """limit_la[l] = (first_code[l] + count[l]) << (MAXLEN - l), UQ21.0 (uArch section 3.2/4)."""
    fc, cnt, _ = extended_arrays(model)
    return ((fc[l] + cnt[l]) << (MAXLEN - l)) & MASK21


def eob_expect(model, lengths, eob_sym):
    """(eob_len, eob_code) the latch should hold: the EOB symbol's canonical (l, code)."""
    length = lengths[eob_sym] if eob_sym < len(lengths) else 0
    if length == 0:
        return 0, None
    pos = model.symtab.index(eob_sym)
    return length, model.first_code[length] + (pos - model.base[length])


def counts_of(lengths):
    cnt = [0] * (MAXLEN + 1)
    for l in lengths:
        if l:
            cnt[l] += 1
    return cnt


def random_legal_lengths(rng, alphabet):
    """Random Kraft-legal (sum <= 1) lengths 0..MAXLEN over `alphabet` symbols, 0 = unused."""
    budget = 1 << MAXLEN
    lengths = []
    for _ in range(alphabet):
        if budget == 0 or rng.random() < 0.25:
            lengths.append(0)
            continue
        for _ in range(10):
            l = rng.randint(1, MAXLEN)
            if (1 << (MAXLEN - l)) <= budget:
                budget -= 1 << (MAXLEN - l)
                lengths.append(l)
                break
        else:
            lengths.append(0)
    if not any(lengths):
        lengths[0] = 1
    return lengths


def ladder_lengths(alphabet, depth):
    """Kraft-COMPLETE ladder: lengths 1,2,...,depth-1,depth,depth then zeros (depth+1 symbols)."""
    assert alphabet >= depth + 1
    return list(range(1, depth)) + [depth, depth] + [0] * (alphabet - depth - 1)


# ---- DUT helpers -------------------------------------------------------------------------------

def field(flat, idx, width):
    return (flat >> (idx * width)) & ((1 << width) - 1)


async def setup(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst_n.value = 0
    dut.start_i.value = 0
    dut.mode_deflate_i.value = 0
    dut.alphabet_i.value = 0
    dut.n_tables_i.value = 0
    dut.len_wr_en_i.value = 0
    dut.len_wr_addr_i.value = 0
    dut.len_wr_data_i.value = 0
    dut.cnt_wr_en_i.value = 0
    dut.cnt_wr_addr_i.value = 0
    dut.cnt_wr_data_i.value = 0
    dut.cur_set_i.value = 0
    dut.symtab_rd_addr_i.value = 0
    dut.dbg_rd_addr_i.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)


async def load_table(dut, t, lengths, alphabet):
    """Load one table's lengths window and its folded count bins (as huff_regs would hold them)."""
    for s in range(alphabet):
        dut.len_wr_en_i.value = 1
        dut.len_wr_addr_i.value = (t << 9) | s
        dut.len_wr_data_i.value = lengths[s] if s < len(lengths) else 0
        await RisingEdge(dut.clk)
    dut.len_wr_en_i.value = 0
    cnt = counts_of(lengths)
    for l in range(1, MAXLEN + 1):
        dut.cnt_wr_en_i.value = 1
        dut.cnt_wr_addr_i.value = (t << 5) | l
        dut.cnt_wr_data_i.value = cnt[l]
        await RisingEdge(dut.clk)
    dut.cnt_wr_en_i.value = 0
    await RisingEdge(dut.clk)


async def run_build(dut, alphabet, n_tables, deflate=0, max_cycles=5000):
    """Pulse start; returns (done, err, cycles) with cycles counted from the start pulse."""
    dut.alphabet_i.value = alphabet
    dut.n_tables_i.value = n_tables
    dut.mode_deflate_i.value = deflate
    await RisingEdge(dut.clk)
    dut.start_i.value = 1
    await RisingEdge(dut.clk)
    dut.start_i.value = 0
    cycles = 0
    while cycles < max_cycles:
        await RisingEdge(dut.clk)
        cycles += 1
        if int(dut.build_done_o.value):
            return True, False, cycles
        if int(dut.err_table_o.value):
            return False, True, cycles
    raise AssertionError(f"build neither finished nor errored within {max_cycles} cycles")


async def read_symtab(dut, addr):
    dut.symtab_rd_addr_i.value = addr
    await ClockCycles(dut.clk, 2)   # registered read, 1 cycle (C1) + sample margin
    return int(dut.symtab_rd_data_o.value)


async def select_set(dut, t):
    dut.cur_set_i.value = t
    await Timer(1, unit="ns")       # combinational read view


async def check_set(dut, t, lengths, alphabet, check_symtab=True):
    """Compare set t's registers + reachable symtab content + EOB latch against the oracle."""
    model = Table(lengths, MAXLEN)
    fc, cnt, base = extended_arrays(model)
    await select_set(dut, t)
    la_flat = int(dut.limit_la_flat_o.value)
    fc_flat = int(dut.first_code_flat_o.value)
    base_flat = int(dut.base_flat_o.value)
    for l in range(1, MAXLEN + 1):
        got_fc = field(fc_flat, l - 1, 20)
        got_base = field(base_flat, l - 1, 11)
        got_la = field(la_flat, l - 1, 21)
        assert got_fc == fc[l] & MASK20, \
            f"set {t} first_code[{l}]: got {got_fc:#x}, expected {fc[l] & MASK20:#x}"
        assert got_base == base[l], \
            f"set {t} base[{l}]: got {got_base}, expected {base[l]}"
        exp_la = expected_limit_la(model, l)
        assert got_la == exp_la, \
            f"set {t} limit_la[{l}]: got {got_la:#x}, expected {exp_la:#x}"
    got_tb = int(dut.table_base_o.value)
    assert got_tb == t * STRIDE, f"set {t} table_base: got {got_tb}, expected {t * STRIDE}"
    if check_symtab:
        for i, s in enumerate(model.symtab):
            got = await read_symtab(dut, t * STRIDE + i)
            exp = (1 << 9) | s
            assert got == exp, \
                f"set {t} symtab[{t * STRIDE + i}]: got {got:#x}, expected {exp:#x} (sym {s})"
    return model


async def check_eob(dut, t, lengths, eob_sym):
    model = Table(lengths, MAXLEN)
    exp_len, exp_code = eob_expect(model, lengths, eob_sym)
    await select_set(dut, t)
    got_len = int(dut.eob_len_o.value)
    assert got_len == exp_len, f"set {t} eob_len: got {got_len}, expected {exp_len}"
    if exp_len:
        got_code = int(dut.eob_code_o.value)
        assert got_code == exp_code, \
            f"set {t} eob_code: got {got_code:#x}, expected {exp_code:#x}"


# ---- tests -------------------------------------------------------------------------------------

@cocotb.test()
async def test_benchmark_tables(dut):
    """(1)+(5) The real benchmark's 6 tables: all set registers, symtab, EOB, K2 cycle count."""
    tr = pyflate_ref.trace_benchmark()
    blk = tr.blocks[0]
    lengths_per_table = blk["lengths"]
    alphabet = blk["symbols_in_use"]
    assert len(lengths_per_table) == 6 and alphabet == 147

    await setup(dut)
    for t, lengths in enumerate(lengths_per_table):
        await load_table(dut, t, lengths, alphabet)
    done, err, cycles = await run_build(dut, alphabet, 6)
    assert done and not err, "benchmark build must complete without ERR_TABLE"

    bc = int(dut.build_cycles_o.value)
    assert bc == alphabet + MAXLEN, \
        f"build_cycles_o: got {bc}, expected alphabet+MAXLEN = {alphabet + MAXLEN} (K2)"
    assert bc == 167, "K2 evidence: benchmark per-table build = 167 cycles (uArch section 7)"
    exp_total = 6 * (alphabet + MAXLEN)
    assert exp_total <= cycles <= exp_total + 3, \
        f"total build wall-clock {cycles}, expected ~{exp_total} (+small pulse latency)"

    for t, lengths in enumerate(lengths_per_table):
        await check_set(dut, t, lengths, alphabet)
        await check_eob(dut, t, lengths, alphabet - 1)   # bzip2 EOB = symbols_in_use - 1

    # opportunistic C1/DBG check: outside FILL, dbg port mirrors the symtab
    dut.dbg_rd_addr_i.value = 0
    await Timer(1, unit="ns")
    got_dbg = int(dut.dbg_rd_data_o.value)
    exp0 = (1 << 9) | Table(lengths_per_table[0], MAXLEN).symtab[0]
    assert got_dbg == exp0, f"dbg_rd_data outside FILL: got {got_dbg:#x}, expected {exp0:#x}"


@cocotb.test()
async def test_random_valid_tables(dut):
    """(2) Random Kraft-legal tables over random alphabets, plus complete-code corner cases."""
    rng = random.Random(0x48554646)
    await setup(dut)

    # deterministic corner invocation: complete codes incl. the first_code[20]=2^20 truncation
    corner = [
        ladder_lengths(24, 20),                    # complete, every length 1..20 used
        [1, 1] + [0] * 22,                         # complete at depth 1 -> fc[20] = 2^20
        [3] * 8 + [0] * 16,                        # uniform complete power-of-two code
        [2, 2, 2, 3, 4, 5] + [0] * 18,             # incomplete (Kraft sum < 1)
    ]
    alphabet = 24
    for t, lengths in enumerate(corner):
        Table(lengths, MAXLEN)                     # oracle agrees these are legal
        await load_table(dut, t, lengths, alphabet)
    done, err, _ = await run_build(dut, alphabet, len(corner))
    assert done and not err
    for t, lengths in enumerate(corner):
        await check_set(dut, t, lengths, alphabet)
        await check_eob(dut, t, lengths, alphabet - 1)

    # random invocations
    for _ in range(3):
        n_tables = rng.randint(1, 6)
        alphabet = rng.randint(10, 288)
        tables = [random_legal_lengths(rng, alphabet) for _ in range(n_tables)]
        for t, lengths in enumerate(tables):
            Table(lengths, MAXLEN)                 # must not raise
            await load_table(dut, t, lengths, alphabet)
        done, err, cycles = await run_build(dut, alphabet, n_tables)
        assert done and not err
        bc = int(dut.build_cycles_o.value)
        assert bc == alphabet + MAXLEN, \
            f"build_cycles_o {bc} != alphabet+MAXLEN {alphabet + MAXLEN}"
        for t, lengths in enumerate(tables):
            await check_set(dut, t, lengths, alphabet, check_symtab=(alphabet <= 64))
            await check_eob(dut, t, lengths, alphabet - 1)


@cocotb.test()
async def test_kraft_oversubscribed_aborts(dut):
    """(3) Over-subscribed table -> err_table pulse, build aborted (no build_done, busy drops)."""
    await setup(dut)
    alphabet = 8

    for bad in ([1, 1, 1, 0, 0, 0, 0, 0],          # count[1] = 3 > 2: overflow at l = 1
                [2, 2, 2, 2, 3, 0, 0, 0]):         # legal through l = 2, overflow at l = 3
        try:
            Table(bad, MAXLEN)
            raise AssertionError("oracle accepted an over-subscribed table")
        except ValueError as e:
            assert "ERR_TABLE" in str(e)

    # bad table as table 1 of 3: table 0 completes, the build aborts during table 1's PREFIX
    good = [2, 2, 2, 3, 3, 0, 0, 0]
    await load_table(dut, 0, good, alphabet)
    await load_table(dut, 1, [1, 1, 1, 0, 0, 0, 0, 0], alphabet)
    await load_table(dut, 2, good, alphabet)
    done, err, cycles = await run_build(dut, alphabet, 3)
    assert err and not done, "expected err_table_o pulse, no build_done_o"
    # abort: well before the full 3-table build, and the FSM returns to idle
    assert cycles < 2 * (alphabet + MAXLEN), f"abort took {cycles} cycles — did not abort early"
    assert int(dut.busy_o.value) == 0, "busy_o still high after Kraft abort"
    for _ in range(50):
        await RisingEdge(dut.clk)
        assert int(dut.build_done_o.value) == 0, "build_done_o pulsed after an aborted build"
    # table 0 (built before the abort) is still coherent
    await check_set(dut, 0, good, alphabet)

    # a subsequent good build recovers
    await load_table(dut, 1, good, alphabet)
    done, err, _ = await run_build(dut, alphabet, 3)
    assert done and not err, "builder did not recover after a Kraft abort"
    await check_set(dut, 1, good, alphabet)


@cocotb.test()
async def test_eob_latch_lifecycle(dut):
    """(4) EOB latch: rebuild updates it; PREP-entry clear wipes all six; DEFLATE distance set
    (never latching) keeps eob_len 0; bzip2 EOB-with-length-0 stays 0."""
    await setup(dut)
    alphabet = 16

    # build 6 tables, all with a coded EOB (symbol alphabet-1)
    l_a = [3, 3, 3, 3, 3, 3, 4, 5, 5, 0, 0, 0, 0, 0, 0, 5]      # EOB len 5
    for t in range(6):
        await load_table(dut, t, l_a, alphabet)
    done, err, _ = await run_build(dut, alphabet, 6)
    assert done and not err
    for t in range(6):
        await check_eob(dut, t, l_a, alphabet - 1)
    await select_set(dut, 0)
    assert int(dut.eob_len_o.value) == 5

    # rebuild table 0 with a different EOB length -> latch updates
    l_b = [2, 2, 3, 4, 5, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3]      # EOB len 3
    await load_table(dut, 0, l_b, alphabet)
    done, err, _ = await run_build(dut, alphabet, 1)
    assert done and not err
    await check_eob(dut, 0, l_b, alphabet - 1)
    # PREP-entry clear: sets 1..5 were NOT rebuilt this invocation -> their latches are cleared
    for t in range(1, 6):
        await select_set(dut, t)
        assert int(dut.eob_len_o.value) == 0, \
            f"set {t} eob_len stale after 1-table rebuild (PREP-entry clear violated)"

    # bzip2 EOB with length 0 never latches
    l_c = [2, 2, 2, 3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]      # EOB (sym 15) len 0
    await load_table(dut, 0, l_c, alphabet)
    done, err, _ = await run_build(dut, alphabet, 1)
    assert done and not err
    await select_set(dut, 0)
    assert int(dut.eob_len_o.value) == 0, "eob_len latched for an uncoded EOB symbol"

    # DEFLATE: literal table (t=0) latches at symbol 256; distance table (t=1) never latches
    deflate_alphabet = 288
    lit = [8] * 144 + [9] * 112 + [7] * 24 + [8] * 8              # RFC 1951 fixed lit/len code
    assert len(lit) == 288 and lit[256] == 7
    dist = [5] * 30 + [0] * 258                                   # fixed distance code
    await load_table(dut, 0, lit, deflate_alphabet)
    await load_table(dut, 1, dist, deflate_alphabet)
    done, err, _ = await run_build(dut, deflate_alphabet, 2, deflate=1)
    assert done and not err
    lit15 = Table(lit, 15)                                        # DEFLATE oracle (maxlen 15)
    exp_len = lit[256]
    pos = lit15.symtab.index(256)
    exp_code = lit15.first_code[exp_len] + (pos - lit15.base[exp_len])
    await select_set(dut, 0)
    assert int(dut.eob_len_o.value) == exp_len
    assert int(dut.eob_code_o.value) == exp_code, \
        f"DEFLATE eob_code: got {int(dut.eob_code_o.value):#x}, expected {exp_code:#x}"
    await select_set(dut, 1)
    assert int(dut.eob_len_o.value) == 0, "DEFLATE distance set latched an EOB"
    # and the DEFLATE sets themselves obey the 20-aligned recurrence with zero 16..20 bins
    for t, lengths in enumerate((lit, dist)):
        await check_set(dut, t, lengths, deflate_alphabet, check_symtab=False)


@cocotb.test()
async def test_build_cycles_alphabet_max(dut):
    """(5) K2 at capacity: alphabet 288, 6 tables -> build_cycles_o = 308 (uArch section 7)."""
    await setup(dut)
    alphabet = 288
    lengths = ladder_lengths(alphabet, 20)
    for t in range(6):
        await load_table(dut, t, lengths, alphabet)
    done, err, cycles = await run_build(dut, alphabet, 6)
    assert done and not err
    bc = int(dut.build_cycles_o.value)
    assert bc == alphabet + MAXLEN == 308, f"build_cycles_o {bc}, expected 308"
    exp_total = 6 * (alphabet + MAXLEN)
    assert exp_total <= cycles <= exp_total + 3
    await check_set(dut, 5, lengths, alphabet, check_symtab=True)
    await check_eob(dut, 5, lengths, alphabet - 1)
