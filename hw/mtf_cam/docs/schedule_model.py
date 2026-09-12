#!/usr/bin/env python3
"""uArch §7 driver for mtf_cam: reproduces the latency/throughput numbers quoted in
`docs/uarch.md` by running the *golden* cycle model (`golden/list_model.cycles`) on the real
benchmark symbol trace (`golden/mtf_ref.trace_benchmark`). Nothing here re-implements the model —
it imports the frozen golden so the doc's K3, the D-sweep and the W-table are reproduced, not
invented (grape/huffman uArch practice: `docs/schedule_model.py`, `docs/decode_model.py`).

    python3 hw/mtf_cam/docs/schedule_model.py     # after `source hw/env.sh`

Design point documented by the uArch: W = 8, D = 8 (item FIFO). Prints:
  * the workload slice (init = N_USED cycles, symbols, output bytes/beats);
  * the K3 headline (CYCLES / SYMBOLS_IN) at the design point, asserted <= 1.10;
  * the D-sweep at W = 8 and the W-table at D = 8 (the two tables §7 cites);
  * the K1 directed-stream latency bound and INIT_CYCLES bound.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "golden"))
import list_model as M    # noqa: E402  (frozen golden cycle + functional model)
import mtf_ref as G       # noqa: E402  (golden trace: used map, symbol stream, L-vector)

K3_REQ = 1.10
LATENCY_MAX = 8           # PRD K1 pipeline latency bound (cycles)
INIT_MAX = 256            # PRD-F4 / MAS INIT_CYCLES bound


def k3(symbols, used, alphabet, W, D):
    cyc = M.cycles(symbols, used, alphabet, W=W, D=D)
    return cyc, cyc / len(symbols)


def main():
    mt = G.trace_benchmark()
    symbols, used, alphabet = mt.symbols, mt.used, mt.alphabet
    n_in = len(symbols)
    n_used = sum(used)

    # Cross-check the functional model against the golden L-vector (same guarantee calibrate.py gives).
    l, ev = M.expand(symbols, used, alphabet)
    assert l == mt.l_vector, "functional model L-vector != golden"
    runs = [e[1] for e in ev if e[0] == "run"]
    n_mtf = sum(1 for e in ev if e[0] == "mtf")

    print("== mtf_cam uArch §7 latency/throughput (golden model on %s)" % G.BENCH_INPUT.name)
    print(f"used bytes N_USED           : {n_used}  (alphabet {alphabet}, EOB value {alphabet - 1})")
    print(f"init cycles (= N_USED)      : {n_used}  <= INIT_CYCLES bound {INIT_MAX}  {'OK' if n_used <= INIT_MAX else 'FAIL'}")
    print(f"input symbols SYMBOLS_IN    : {n_in} = {n_mtf} MTF + {n_in - n_mtf - 1} run + 1 EOB")
    print(f"L-vector BYTES_OUT          : {len(l)}  ({-(-len(l)//8)} beats at W=8)")
    print(f"run groups / MAX_RUN        : {len(runs)} / {max(runs)}")

    W, D = 8, 8
    cyc, ratio = k3(symbols, used, alphabet, W, D)
    print(f"\nDESIGN POINT W={W}, D={D}     : CYCLES {cyc} -> K3 = {ratio:.3f} cycles/symbol  "
          f"(<= {K3_REQ}: {'OK' if ratio <= K3_REQ else 'FAIL'})")
    lower = max(n_in, n_mtf + sum(-(-r // W) for r in runs)) / n_in
    print(f"lower bound max(sym,drain)  : {lower:.3f} cycles/symbol")

    print(f"\nD-sweep at W=8 (item-FIFO depth trades area for K3):")
    for D_ in (0, 8, 32, 128):
        c, r = k3(symbols, used, alphabet, 8, D_)
        tag = "  <- chosen" if D_ == 8 else ("  (fully serialised)" if D_ == 0 else "")
        print(f"  D={D_:4d}: {c:7d} cycles -> {r:.3f}{tag}")

    print(f"\nW-table at D=8 (expander/packer width; PPA sweep):")
    for W_ in (4, 8, 16):
        c, r = k3(symbols, used, alphabet, W_, 8)
        print(f"  W={W_:2d}: {c:7d} cycles -> {r:.3f}")

    print(f"\nK1 pipeline latency bound   : <= {LATENCY_MAX} cycles (directed run-free stream, tready=1)")
    print(f"K5 block time @ 50 MHz      : {cyc} cycles / 50e6 = {cyc / 50e6 * 1e3:.2f} ms")

    assert ratio <= K3_REQ, f"K3 {ratio:.3f} > {K3_REQ}"
    print("\nall §7 numbers reproduced from the golden model.")


if __name__ == "__main__":
    main()
