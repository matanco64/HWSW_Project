"""Ablation study: start from T3 and put ONE stock/T1 component back, so each
optimization's contribution is attributed independently rather than inferred
from the cumulative ladder.

Usage: <python> dev/pyflate/ablate.py [-r N]
"""
import argparse
import bz2
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import t1_micro as T1       # noqa: E402
import t2_canonical as T2   # noqa: E402
import t3_table as T3       # noqa: E402

DATA = os.path.normpath(os.path.join(
    HERE, '..', '..', 'benchmarks', 'bm_pyflate', 'data', 'interpreter.tar.bz2'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-r', '--repeats', type=int, default=7)
    args = ap.parse_args()
    ref = bz2.decompress(open(DATA, 'rb').read())

    t3_rle4 = T3.rle4_expand
    t3_bwt = T3.bwt_reverse

    def full():
        T3.rle4_expand, T3.bwt_reverse = t3_rle4, t3_bwt
        return T3.decompress(DATA)

    def no_rle4():
        T3.rle4_expand, T3.bwt_reverse = T1.rle4_expand, t3_bwt
        return T3.decompress(DATA)

    def no_bwt():
        T3.rle4_expand, T3.bwt_reverse = t3_rle4, T1.bwt_reverse
        return T3.decompress(DATA)

    # T2 loop + T3 back end: isolates "flat table vs canonical stepping"
    t2_rle4, t2_bwt = T2.rle4_expand, T2.bwt_reverse

    def t2_with_t3_backend():
        T2.rle4_expand, T2.bwt_reverse = t3_rle4, t3_bwt
        try:
            return T2.decompress(DATA)
        finally:
            T2.rle4_expand, T2.bwt_reverse = t2_rle4, t2_bwt

    cases = [
        ('T3 full', full),
        ('T3 - flat table (canonical step)', t2_with_t3_backend),
        ('T3 - counting-sort BWT (stock sort)', no_bwt),
        ('T3 - regex RLE4 (per-byte loop)', no_rle4),
        ('T1 (micro only)', lambda: T1.decompress(DATA)),
    ]

    times = {n: [] for n, _ in cases}
    for n, f in cases:
        assert f() == ref, n
    for _ in range(args.repeats):
        for n, f in cases:
            t = time.perf_counter()
            f()
            times[n].append(time.perf_counter() - t)

    print("python %s   interleaved best-of-%d" % (sys.version.split()[0], args.repeats))
    full_best = min(times['T3 full'])
    print("%-38s %-10s %-10s %s" % ('variant', 'best(s)', 'median(s)', 'cost of putting it back'))
    for n, _ in cases:
        b = min(times[n])
        print("%-38s %-10.4f %-10.4f %+.1f ms"
              % (n, b, statistics.median(times[n]), (b - full_best) * 1000))
    full()   # restore


if __name__ == '__main__':
    main()
