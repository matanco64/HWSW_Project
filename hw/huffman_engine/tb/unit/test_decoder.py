"""huff_decoder unit TB: the C0 combinationals vs golden CanonicalTable.decode over random
tables and the benchmark's real ones (contract: rtl_contracts.md; oracle: canonical_model)."""
import random

import cocotb
from cocotb.triggers import Timer

import canonical_model as CM
import pyflate_ref as G

MAXLEN = 20


def build_refs(lengths, maxlen=MAXLEN):
    t = CM.Table(lengths, maxlen)
    fc = [0] * (maxlen + 1)
    cnt = [0] * (maxlen + 2)
    for l in lengths:
        if l:
            cnt[l] += 1
    code = 0
    base = [0] * (maxlen + 1)
    run = 0
    for l in range(1, maxlen + 1):
        code = (code + cnt[l - 1]) << 1
        fc[l] = code
        base[l] = run
        run += cnt[l]
    limit = [(fc[l] + cnt[l]) << (maxlen - l) for l in range(1, maxlen + 1)]
    return t, fc, base, limit


def pack(vals, w):
    out = 0
    for i, v in enumerate(vals):
        out |= (v & ((1 << w) - 1)) << (i * w)
    return out


async def drive_table(dut, lengths, table_base=0, eob_sym=None):
    t, fc, base, limit = build_refs(lengths)
    dut.limit_la_i.value = pack(limit, 21)
    dut.first_code_i.value = pack([fc[l] for l in range(1, MAXLEN + 1)], 20)
    dut.base_i.value = pack([base[l] for l in range(1, MAXLEN + 1)], 11)
    dut.table_base_i.value = table_base
    if eob_sym is not None and lengths[eob_sym]:
        el = lengths[eob_sym]
        # code of eob_sym: rank among same-length symbols
        rank = sum(1 for s in range(eob_sym) if lengths[s] == el)
        dut.eob_len_i.value = el
        dut.eob_code_i.value = fc[el] + rank
    else:
        dut.eob_len_i.value = 0
        dut.eob_code_i.value = 0
    return t


async def check_windows(dut, t, lengths, n, rng, table_base=0, eob_sym=None):
    for _ in range(n):
        w = rng.getrandbits(MAXLEN)
        dut.window_i.value = w
        await Timer(1, unit="ns")
        try:
            ref = t.decode(w)
        except ValueError:
            assert int(dut.nocode_o.value) == 1, f"w={w:05x}: expected nocode"
            continue
        if True:
            sym, ln = ref
            assert int(dut.match_o.value) == 1
            assert int(dut.len_o.value) == ln, f"w={w:05x}: len {int(dut.len_o.value)} != {ln}"
            code = w >> (MAXLEN - ln)
            assert int(dut.code_o.value) == code
            exp_index = table_base + sum(1 for s in range(len(lengths))
                                         if 0 < lengths[s] < ln) + \
                sum(1 for s in range(sym) if lengths[s] == ln)
            assert int(dut.index_o.value) == exp_index, \
                f"w={w:05x}: index {int(dut.index_o.value)} != {exp_index}"
            exp_eob = (eob_sym is not None and sym == eob_sym)
            assert int(dut.eob_o.value) == int(exp_eob), f"w={w:05x}: eob mismatch"


@cocotb.test()
async def decode_random_tables(dut):
    rng = random.Random(7)
    for trial in range(20):
        nsym = rng.randrange(3, 60)
        # legal canonical table: assign lengths via a random Kraft-complete tree
        lengths = kraft_lengths(rng, nsym)
        tbase = rng.randrange(0, 1000)
        t = await drive_table(dut, lengths, table_base=tbase, eob_sym=nsym - 1)
        await check_windows(dut, t, lengths, 200, rng, table_base=tbase, eob_sym=nsym - 1)


@cocotb.test()
async def decode_benchmark_tables(dut):
    tr = G.trace_benchmark()
    blk = tr.blocks[0]
    rng = random.Random(11)
    for lengths in blk["lengths"]:
        t = await drive_table(dut, list(lengths), table_base=0,
                              eob_sym=len(lengths) - 1)
        await check_windows(dut, t, list(lengths), 400, rng, eob_sym=len(lengths) - 1)


def kraft_lengths(rng, nsym):
    """Random Kraft-complete length assignment via Huffman on random weights."""
    import heapq
    h = [(rng.randrange(1, 1000), i, 0) for i in range(nsym)]
    trees = [(w, [i]) for (w, i, _) in h]
    heapq.heapify(trees)
    depth = [0] * nsym
    while len(trees) > 1:
        w1, s1 = heapq.heappop(trees)
        w2, s2 = heapq.heappop(trees)
        for s in s1 + s2:
            depth[s] += 1
        heapq.heappush(trees, (w1 + w2, s1 + s2))
    if any(d > MAXLEN for d in depth):
        return kraft_lengths(rng, nsym)          # retry: stay Kraft-complete within MAXLEN
    return [d if d else 1 for d in depth]
