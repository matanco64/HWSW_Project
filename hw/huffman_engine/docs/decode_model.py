#!/usr/bin/env python3
"""Cycle-accurate decode model for huffman_engine uArch §7 (ADR-0008): simulates the 1-cycle
decode loop, the 64-bit aligner with 32-bit concurrent refill, folded-counts table builds and
0-cycle selector switches over the REAL benchmark trace (golden trace_benchmark(): per-symbol
(table_id, code_len, symbol)). K1 = total cycles / symbols must be <= 1.1 (PRD K1); grape
sign-off lesson: KPIs are simulated on the full workload, never stage-summed.

    python3 hw/huffman_engine/docs/decode_model.py            # benchmark + worst-case sweeps
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "golden"))
import pyflate_ref as G  # noqa: E402

MAXLEN = 20
BUF_BITS = 64
FIFO_BEATS = 2           # prefetch FIFO (review U9: buffer 64b + 2 beats = 128b = 4-beat OVERFETCH cap)
REFILL = 32              # bits per refill, concurrent with the consume
ALPHABET_MAX = 288


def simulate(lengths, alphabet, n_tables, start_bit=0, beat_every=1, out_stall_every=0):
    """lengths: per-symbol code lengths. beat_every: a new input beat is available every N
    cycles (1 = DMA saturates; models starvation for real — review should-fix: the old knob
    sat inside a never-entered loop). Aligner: 64b buffer + FIFO_BEATS prefetch; refill 32b
    when a beat is available and there is room; decode gated on occ >= MAXLEN until TLAST
    (tail zero-padded). SKIP (whole-word discard of start_bit) runs in PARALLEL with the
    builds (independent units — review U8). Returns cycles/stalls dict."""
    build = n_tables * (alphabet + MAXLEN)      # folded counts (ADR-0008 #4)
    skip = start_bit // 32                      # whole-word discards, 1 per delivered beat
    cycles = max(build, skip * beat_every)      # overlapped (U8); skip throttled by DMA (N8)
    occ = 0
    fifo = 0                                    # beats waiting in the prefetch FIFO
    next_beat = skip * beat_every + 1           # payload beats follow the skipped words
    refill_stall = 0
    out_stall = 0
    total_bits = sum(lengths)
    consumed = 0

    def tick(k):
        nonlocal fifo, next_beat
        # beat arrivals up to cycle k
        while next_beat <= k and fifo < FIFO_BEATS:
            fifo += 1
            next_beat += beat_every

    def refill():
        nonlocal occ, fifo
        if fifo > 0 and occ <= BUF_BITS - REFILL:
            occ = min(BUF_BITS, occ + REFILL)
            fifo -= 1

    for n, ln in enumerate(lengths):
        if out_stall_every and n % out_stall_every == 0:
            cycles += 1
            out_stall += 1
            tick(cycles)
            refill()
        # decode gate: full MAXLEN window unless the stream tail is already in (zero-pad)
        tail = (total_bits - consumed) <= occ and (total_bits - consumed) < MAXLEN
        while occ < MAXLEN and not tail:
            cycles += 1
            refill_stall += 1
            tick(cycles)
            refill()
            tail = (total_bits - consumed) <= occ and (total_bits - consumed) < MAXLEN
        occ -= ln
        consumed += ln
        cycles += 1
        tick(cycles)
        refill()
    cycles += 2                                  # backend drain + EOB TLAST beat
    return {"cycles": cycles, "build": build, "skip": skip, "refill_stall": refill_stall,
            "out_stall": out_stall, "symbols": len(lengths)}


def report(tag, r):
    k1 = r["cycles"] / r["symbols"]
    print(f"{tag}: {r['cycles']} cycles / {r['symbols']} symbols = {k1:.4f} cycles/symbol "
          f"(build {r['build']}, skip {r['skip']}, refill stalls {r['refill_stall']}, "
          f"out stalls {r['out_stall']})")
    return k1


if __name__ == "__main__":
    tr = G.trace_benchmark()
    blk = tr.blocks[0]
    lens = [l for (_, l, _, _) in tr.symbols]        # per-symbol code length (stock trace)
    alphabet = blk["symbols_in_use"]                 # already the alphabet size (calibrate.py)
    n_tables = len(blk["lengths"])
    start_bit = blk["sym_start_bit"]
    k1 = report(f"benchmark ({n_tables} tables, alphabet {alphabet}, start_bit {start_bit})",
                simulate(lens, alphabet, n_tables, start_bit=start_bit))
    assert k1 <= 1.1, f"K1 {k1:.4f} > 1.1"
    # worst-case sweeps
    report("all-20-bit codes (max consume)", simulate([20] * 10000, 288, 6))
    k1s = report("input beat only every 5 cycles (DMA 6.4b/cy < mean consume rate)",
                 simulate(lens, alphabet, n_tables, start_bit=start_bit, beat_every=5))
    report("input beat every 8 cycles (4b/cy, sustained starvation)",
           simulate(lens, alphabet, n_tables, start_bit=start_bit, beat_every=8))
    report("output backpressure every 4 symbols", simulate(lens, alphabet, n_tables,
                                                           start_bit=start_bit,
                                                           out_stall_every=4))
    for a, tag in ((147, "benchmark"), (ALPHABET_MAX, "ALPHABET_MAX")):
        k2, bound = a + MAXLEN, 2 * a + MAXLEN
        print(f"K2 per table, {tag} alphabet {a} (folded counts): {k2} <= {bound} bound "
              f"(margin {bound / k2:.2f}x); first symbol after {6 * k2} cycles worst case")
