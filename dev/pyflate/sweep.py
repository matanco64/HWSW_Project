"""Sweep PRIMARY_BITS for the T3 flat lookup table, and measure the
table-build cost so the amortisation claim is evidence-based.

Usage: <python> dev/pyflate/sweep.py
"""
import bz2
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import t2_canonical as T2          # noqa: E402
import t3_table as T3              # noqa: E402

DATA = os.path.normpath(os.path.join(
    HERE, '..', '..', 'benchmarks', 'bm_pyflate', 'data', 'interpreter.tar.bz2'))


def capture_lengths():
    """Grab the six real code-length vectors from the benchmark block."""
    got = []
    orig = T3.build_canonical

    def spy(lengths):
        got.append(list(lengths))
        return orig(lengths)
    T3.build_canonical = spy
    T3.decompress(DATA)
    T3.build_canonical = orig
    return got


def main():
    ref = bz2.decompress(open(DATA, 'rb').read())
    lens = capture_lengths()
    print("captured %d code-length vectors, alphabet %d" % (len(lens), len(lens[0])))

    print("\n-- table build cost (all 6 tables, best of 200) --")
    for pb in (8, 9, 10, 11, 12, 13, 15, 20):
        best = 1e9
        for _ in range(200):
            t = time.perf_counter()
            for g in lens:
                T3.build_table(g, pb)
            best = min(best, time.perf_counter() - t)
        entries = sum(1 << min(pb, max(g)) for g in lens)
        print("   PRIMARY_BITS=%-2d  %7.3f ms  (%d table entries total)"
              % (pb, best * 1000, entries))

    print("\n-- end-to-end decode, interleaved best-of-5 --")
    cands = (8, 9, 10, 11, 12, 13, 15)
    times = {pb: [] for pb in cands}
    for _ in range(5):
        for pb in cands:
            T3.PRIMARY_BITS = pb
            t = time.perf_counter()
            out = T3.decompress(DATA)
            times[pb].append(time.perf_counter() - t)
            assert out == ref, pb
    for pb in cands:
        print("   PRIMARY_BITS=%-2d  best %.4f s" % (pb, min(times[pb])))
    T3.PRIMARY_BITS = 11


if __name__ == '__main__':
    main()
