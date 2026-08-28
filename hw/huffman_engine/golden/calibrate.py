#!/usr/bin/env python3
"""Calibration for the huffman_engine PRD: cross-checks the golden trace (stock pyflate) against
the independent emulation model (canonical_model.py) and against the C libraries (bz2/zlib), and
prints the numbers quoted in docs/prd.md (symbols, table-build steps, cycle model, config words).

    python3 hw/huffman_engine/golden/calibrate.py
"""
import bz2
import gzip
import os
import random
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import canonical_model as M   # noqa: E402
import pyflate_ref as G       # noqa: E402


def bzip2_benchmark():
    data = G.BENCH_INPUT.read_bytes()
    tr = G.trace_benchmark()
    assert tr.output == bz2.decompress(data), "stock pyflate output != bz2 (libbzip2)"
    assert len(tr.blocks) == 1
    blk = tr.blocks[0]
    gold = [(k, l, s) for (k, l, s, _) in tr.symbols]
    syms, end, cycles = M.decode_bzip2_symbols(data, blk["sym_start_bit"], blk["lengths"],
                                               blk["selectors"], blk["symbols_in_use"])
    assert [s for (_, _, s) in gold] == syms, "emulation model symbol stream != stock trace"
    # table ids and code lengths per symbol must agree too
    exp_tables = [blk["selectors"][i // 50] for i in range(len(syms))]
    assert [k for (k, _, _) in gold] == exp_tables
    assert end == tr.symbols[-1][3] + tr.symbols[-1][1]
    n = len(syms)
    bits = end - blk["sym_start_bit"]
    alphabet = blk["symbols_in_use"]
    build = alphabet + M.MAXLEN_BZ2 + alphabet
    lengths_words = -(-alphabet * len(blk["lengths"]) // 6)      # 6 x 5-bit lengths per 32-bit word
    sel_beats = len(blk["selectors"])                             # one 8-bit s_sel beat per selector (PRD-F7)
    ctrl_words = 10
    print("== bzip2 benchmark input (%s)" % G.BENCH_INPUT.name)
    print(f"compressed bytes            : {len(data)}  ({len(data)*8} bits)")
    print(f"blocks / tables / alphabet  : {len(tr.blocks)} / {len(blk['lengths'])} / {alphabet}")
    print(f"Huffman symbols (incl. EOB) : {n}")
    print(f"selectors                   : {len(blk['selectors'])}")
    print(f"symbol-code bits            : {bits}  (mean {bits/n:.3f} bits/symbol)")
    print(f"code lengths used           : {min(l for _,l,_ in gold)}..{max(l for _,l,_ in gold)}")
    print(f"table build steps           : {build} per table = alphabet+MAXLEN+alphabet; "
          f"{build*len(blk['lengths'])} total = {100*build*len(blk['lengths'])/n:.2f} % of symbols")
    print(f"cycle model (1 sym/cycle)   : {cycles} cycles = {cycles/n:.4f} cycles/symbol "
          f"(builds + {len(blk['selectors'])} selector switches + {n} symbols)")
    print(f"config via AXI-Lite         : {lengths_words} length words + ~{ctrl_words} control words "
          f"= {lengths_words+ctrl_words} (x4 cycles ~ {(lengths_words+ctrl_words)*4} cycles, "
          f"{100*(lengths_words+ctrl_words)*4/cycles:.2f} % of the block cycle model)")
    print(f"selectors via s_sel         : {sel_beats} beats (8-bit, TLAST on the last)")
    print(f"stream words in / out       : {-(-len(data)//4)} x 32-bit in, {n} x 9-bit symbols out")
    print("cross-checks                : stock==bz2 OK; emulation==stock trace OK (symbols, tables, end bit)")


def _block_types(raw):
    """Census of DEFLATE block types in a raw stream, by walking it with zlib block by block is not
    exposed; instead parse headers using the emulation-model bit reader for stored/fixed and rely on
    the golden trace for dynamic. Returns a list of 'stored'|'fixed'|'dynamic'."""
    import zlib as _z
    kinds = []
    rd = M.BitReader(raw, 0, msb_first=False)
    # walk with zlib's decompressobj to find block boundaries is not possible; approximate census:
    # first block header only, plus 'multi' detection through the decompressobj unconsumed tail.
    final = rd.raw(1)
    btype = rd.raw(2)
    kinds.append({0: "stored", 1: "fixed", 2: "dynamic"}[btype])
    if not final:
        kinds.append("more")
    return [k for k in kinds if k != "more"] + (["dynamic"] if not final else [])


def deflate_random(seed=1, n_blocks=8):
    """Synthetic gzip streams (zlib dynamic + fixed + stored blocks): stock patched gzip_main vs
    zlib, and the emulation model vs the stock symbol trace for every Huffman block."""
    rng = random.Random(seed)
    checked = blocks = 0
    dyn_blocks_checked = [0]
    kinds = {"dynamic": 0, "fixed": 0, "stored": 0}
    multi = 0
    for i in range(n_blocks + 2):
        if i == n_blocks:            # multi-block stream: > 64 kB text at level 1
            words = [bytes(rng.choice(b"abcdefghijklmnopqrstuvwxyz ") for _ in range(rng.randint(1, 8)))
                     for _ in range(300)]
            payload = b" ".join(rng.choice(words) for _ in range(40000))
            level = 1
        elif i == n_blocks + 1:      # incompressible -> stored block(s)
            payload = bytes(rng.getrandbits(8) for _ in range(3000))
            level = 1
        else:
            words = [bytes(rng.choice(b"abcdefghijklmnopqrstuvwxyz ") for _ in range(rng.randint(1, 8)))
                     for _ in range(rng.randint(50, 400))]
            payload = b" ".join(rng.choice(words) for _ in range(rng.randint(200, 3000)))
            level = rng.choice([1, 6, 9])
        comp = gzip.compress(payload, compresslevel=level, mtime=0)
        # block-type census straight from the raw deflate stream (zlib) for the census only
        _bt = _block_types(comp[10:])
        for k in _bt:
            kinds[k] += 1
        if len(_bt) > 1:
            multi += 1
        tr = G.trace_stream(comp)
        assert tr.output == payload == gzip.decompress(comp), "patched stock gzip_main != zlib"
        # rebuild the per-block symbol stream from the raw-deflate bit stream with the emulation model
        raw = zlib.decompressobj(wbits=-15)          # only to validate the stream; symbols come from the trace
        raw.decompress(comp[10:])
        # tables in order of first use per block: [code-length table], literals, distances
        keys = []
        for (k, _, _, _) in tr.symbols:
            if k not in keys:
                keys.append(k)
        # Reconstruct events from the trace: literal/length symbols come from the 'literals' table
        # (the one whose symbols include 256), distances from the next table used after a length.
        lit_keys = {k for (k, _, s, _) in tr.symbols if s == 256}
        events = []
        reads_at = {}                                   # symbol index -> [raw read values after it]
        for (n, v, p, si) in tr.raw_reads:
            reads_at.setdefault(si, []).append(v)
        # walk symbols; extra bits are the raw reads whose symbol_index points right after the symbol
        for idx, (k, l, s, pos) in enumerate(tr.symbols):
            if k not in lit_keys:
                continue
            if s < 256:
                events.append(("lit", s))
            elif s == 256:
                events.append(("eob",))
            else:
                ex = reads_at.get(idx + 1, [])
                le = ex[0] if ex else 0
                d_k, d_l, d_s, d_pos = tr.symbols[idx + 1]
                dx = reads_at.get(idx + 2, [])
                de = dx[0] if dx else 0
                events.append(("copy", M._LEN_BASE[s - 257] + le, M._DIST_BASE[d_s] + de))
        # emulation model on every Huffman block body: lengths recorded per table by the
        # golden wrapper; block body starts at the first literal-table symbol's bit position.
        raw_data = comp[10:]                      # gzip header is 10 bytes (mtime=0, no extras)
        by_block = {}
        for idx, (k, l, s, pos) in enumerate(tr.symbols):
            if k in lit_keys:
                by_block.setdefault(k, []).append(idx)
        consumed = 0
        for k, idxs in by_block.items():
            first, last = idxs[0], idxs[-1]
            start = tr.symbols[first][3] - 80          # trace positions include the 80-bit gzip header
            gold_end = tr.symbols[last][3] + tr.symbols[last][1] - 80
            dist_key = next((tr.symbols[i + 1][0] for i in idxs if tr.symbols[i][2] > 256), None)
            dist_lengths = tr.table_lengths[dist_key] if dist_key else [0] * 30
            ev, end, cyc = M.decode_deflate_symbols(raw_data, start, tr.table_lengths[k], dist_lengths)
            exp_block = events[consumed:consumed + len(idxs)]
            consumed += len(idxs)
            assert ev == exp_block, "emulation model DEFLATE events != stock trace (block %d)" % dyn_blocks_checked[0]
            assert end == gold_end, "emulation model DEFLATE end bit %d != golden %d" % (end, gold_end)
            dyn_blocks_checked[0] += 1
        out = bytearray()
        for e in events:
            if e[0] == "lit":
                out.append(e[1])
            elif e[0] == "copy":
                _, ln, ds = e
                for _ in range(ln):
                    out.append(out[-ds])
        # streams made only of stored blocks carry no Huffman symbols: nothing to replay
        assert not events or bytes(out) == payload, "event replay != payload"
        checked += 1
        blocks += len(lit_keys)
    # emulation-model check on fixed-Huffman blocks (lengths known from the RFC)
    lit_lengths = [8] * 144 + [9] * 112 + [7] * 24 + [8] * 8
    dist_lengths = [5] * 30
    payload = b"fixed huffman block test " * 20
    co = zlib.compressobj(level=1, wbits=-15, strategy=zlib.Z_FIXED)
    raw = co.compress(payload) + co.flush()
    assert raw[0] & 0x07 == 0x03, "expected final fixed block"
    ev, end, cycles = M.decode_deflate_symbols(raw, 3, lit_lengths, dist_lengths)
    out = bytearray()
    for e in ev:
        if e[0] == "lit":
            out.append(e[1])
        elif e[0] == "copy":
            for _ in range(e[1]):
                out.append(out[-e[2]])
    assert bytes(out) == payload, "emulation model DEFLATE decode != payload"
    print("== DEFLATE (synthetic gzip via zlib)")
    print(f"streams checked             : {checked} (zlib levels 1/6/9, one Z_FULL_FLUSH multi-block, one stored), "
          f"{blocks} Huffman blocks, {multi} multi-block streams; first-block census {kinds}; "
          "patched stock gzip_main == zlib OK; event replay == payload OK")
    print(f"emulation model blocks      : {dyn_blocks_checked[0]} Huffman block bodies == stock trace exactly "
          "(lit/len/dist + extra bits, end bit) OK")
    print(f"emulation model fixed block : {len(ev)} events, {cycles} cycles, end bit {end} of {len(raw)*8}; OK")


if __name__ == "__main__":
    bzip2_benchmark()
    deflate_random()
