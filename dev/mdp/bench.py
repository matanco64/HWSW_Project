"""Times every mdp tier back-to-back on the real workload and checks it.

Each repetition runs a complete Battle().evaluate(0.192) from scratch -- the
same unit pyperf's inner loop times -- and records the build/iterate phase
split, the sweep count and the result.  We report best-of-R (the minimum is
the least noise-contaminated estimator on a noisy desktop) plus the median.

    python bench.py [--repeat 7] [--only t2,t3]
"""
import argparse
import gc
import statistics
import time

import t0_stock
import t1_micro
import t2_csr
import t3_intexact

EXPECTED = 0.89873589887
TOL = 1e-6

TIERS = [
    ("T0   stock (reference)", lambda: t0_stock.solve()),
    ("T1   memoise + active list", lambda: t1_micro.solve()),
    ("T2g  CSR, C-gather sweep", lambda: t2_csr.solve(flavour='gather')),
    ("T2   CSR, flat-array sweep", lambda: t2_csr.solve(flavour='flat')),
    ("T3   T2 + exact int build", lambda: t3_intexact.solve()),
]

try:
    import tanti_numpy
    TIERS.append(("TA   numpy reduceat (Jacobi)", lambda: tanti_numpy.solve()))
except ImportError:                                     # pragma: no cover
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repeat', type=int, default=7)
    ap.add_argument('--only', default=None)
    args = ap.parse_args()

    tiers = TIERS
    if args.only:
        want = set(args.only.lower().split(','))
        tiers = [t for t in TIERS
                 if t[0].split()[0].lower() in want]

    print("mdp tiers, best-of-%d complete evaluate(0.192) runs\n" % args.repeat)
    hdr = ("%-30s %9s %9s %9s %9s %7s  %-16s %s"
           % ("tier", "best(s)", "median", "build", "iterate", "sweeps",
              "result", "oracle"))
    print(hdr)
    print("-" * len(hdr))

    # Interleaved rounds: every round runs every tier once, so slow thermal
    # drift and background load hit all tiers equally instead of penalising
    # whichever tier happened to run during a noisy stretch.
    acc = {name: ([], [], [], [None, None]) for name, _ in tiers}
    for _ in range(args.repeat):
        for name, fn in tiers:
            gc.collect()
            gc.disable()
            t0 = time.perf_counter()
            res, swp, tb, ti = fn()
            dt = time.perf_counter() - t0
            gc.enable()
            totals, builds, iters, last = acc[name]
            totals.append(dt)
            builds.append(tb)
            iters.append(ti)
            last[0], last[1] = res, swp

    base = None
    rows = []
    for name, fn in tiers:
        totals, builds, iters, last = acc[name]
        res, swp = last
        best = min(totals)
        k = totals.index(best)
        ok = "PASS" if abs(res - EXPECTED) <= TOL else "FAIL"
        if base is None:
            base = best
        print("%-30s %9.4f %9.4f %9.4f %9.4f %7d  %.12f %s"
              % (name, best, statistics.median(totals), builds[k], iters[k],
                 swp, res, ok))
        rows.append((name, best, builds[k], iters[k], swp, res, ok))

    print()
    print("%-30s %10s %10s %10s" % ("tier", "speedup", "build x", "iter x"))
    b0, bb0, bi0 = rows[0][1], rows[0][2], rows[0][3]
    for name, best, tb, ti, swp, res, ok in rows:
        print("%-30s %9.2fx %9.2fx %9.2fx"
              % (name, b0 / best, bb0 / tb, bi0 / ti))


if __name__ == '__main__':
    main()
