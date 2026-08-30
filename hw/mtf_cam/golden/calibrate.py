#!/usr/bin/env python3
"""Calibration for the mtf_cam PRD: cross-checks the emulation model against the golden L-vector
(stock pyflate, itself == libbzip2 via the huffman_engine calibration) and prints the numbers
quoted in docs/prd.md: MTF rank distribution, run statistics, expander width sweep.

    python3 hw/mtf_cam/golden/calibrate.py
"""
import bz2
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import list_model as M    # noqa: E402
import mtf_ref as G       # noqa: E402


def main():
    data = G.BENCH_INPUT.read_bytes()
    mt = G.trace_benchmark()
    assert mt.output == bz2.decompress(data)
    l, ev = M.expand(mt.symbols, mt.used, mt.alphabet)
    assert l == mt.l_vector, "emulation model L-vector != golden"
    mtf_ev = [e for e in ev if e[0] == "mtf"]
    assert [e[2] for e in mtf_ev] == mt.mtf_out, "per-symbol MTF bytes != golden"
    runs = [e[1] for e in ev if e[0] == "run"]
    ranks = [e[1] for e in mtf_ev]
    n_in = len(mt.symbols)
    n_used = sum(mt.used)
    print("== mtf_cam workload (%s)" % G.BENCH_INPUT.name)
    print(f"used bytes / alphabet       : {n_used} / {mt.alphabet}")
    print(f"input symbols               : {n_in} = {len(mtf_ev)} MTF + {sum(1 for s in mt.symbols if s <= 1)} RUNA/RUNB + 1 EOB")
    print(f"L-vector bytes              : {len(l)} = {len(mtf_ev)} MTF bytes + {sum(runs)} run bytes ({100*sum(runs)/len(l):.1f} %)")
    q = statistics.quantiles(ranks, n=100)
    print(f"MTF rank                    : mean {statistics.mean(ranks):.2f}, p50 {q[49]:.0f}, p90 {q[89]:.0f}, p99 {q[98]:.0f}, max {max(ranks)}, "
          f"rank 0 = {ranks.count(0)} (never: zeros are runs), rank 1 = {100*ranks.count(1)/len(ranks):.1f} %")
    qr = statistics.quantiles(runs, n=100)
    print(f"run groups                  : {len(runs)}, length mean {statistics.mean(runs):.2f}, p50 {qr[49]:.0f}, max {max(runs)}; "
          f"run symbols per group max {max(len(bin(r+1))-3 for r in runs)}")
    print(f"L-vector beats at W=8       : {-(-len(l)//8)} (byte-packed, TKEEP partial only on the last)")
    print("expander width sweep (output cycles = MTF + sum ceil(run/W); input cycles = %d):" % n_in)
    for W in (1, 2, 4, 8, 16, 32):
        out_cyc = len(mtf_ev) + sum(-(-r // W) for r in runs)
        print(f"  W={W:2d}: output {out_cyc:7d} ({out_cyc/n_in:.3f} x input)")
    print("block cycle model, doorbell -> DONE (init + symbol side + drain side; item FIFO depth D):")
    for W in (4, 8, 16):
        row = []
        for D in (0, 8, 32, 128, 1024):
            cyc = M.cycles(mt.symbols, mt.used, mt.alphabet, W=W, D=D)
            row.append(f"D={D:4d}: {cyc} ({cyc/n_in:.3f})")
        print(f"  W={W:2d}: " + " | ".join(row))
    print("cross-checks                : stock == bz2 OK; emulation L-vector == golden OK; per-symbol MTF bytes == golden OK")


if __name__ == "__main__":
    main()
