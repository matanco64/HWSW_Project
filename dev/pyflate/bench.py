"""Ladder harness for pyflate: times every tier back-to-back and verifies the
output against BOTH the benchmark's MD5 oracle and Python's own `bz2` module.

Usage:
    <python> dev/pyflate/bench.py            # verify + time all tiers
    <python> dev/pyflate/bench.py -r 7       # 7 repeats per tier
    <python> dev/pyflate/bench.py -t t3_table  # only one tier
    <python> dev/pyflate/bench.py --profile t0_stock   # cProfile a tier
"""

import argparse
import bz2
import cProfile
import hashlib
import importlib
import os
import pstats
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

DATA = os.path.normpath(os.path.join(
    HERE, '..', '..', 'benchmarks', 'bm_pyflate', 'data', 'interpreter.tar.bz2'))

MD5 = "afa004a630fe072901b1d9628b960974"

TIERS = ['t0_stock', 't1_micro', 't2_canonical', 't3_table']


def verify(out, ref):
    problems = []
    if hashlib.md5(out).hexdigest() != MD5:
        problems.append('MD5 mismatch')
    if out != ref:
        problems.append('byte-diff vs bz2 module')
        for i, (a, b) in enumerate(zip(out, ref)):
            if a != b:
                problems.append('first differing byte at offset %d (%r vs %r)'
                                % (i, a, b))
                break
        if len(out) != len(ref):
            problems.append('length %d vs %d' % (len(out), len(ref)))
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-r', '--repeats', type=int, default=5)
    ap.add_argument('-t', '--tier', action='append')
    ap.add_argument('--profile')
    ap.add_argument('--sort', default='tottime')
    args = ap.parse_args()

    ref = bz2.decompress(open(DATA, 'rb').read())

    if args.profile:
        mod = importlib.import_module(args.profile)
        mod.decompress(DATA)          # warm caches / bytecode
        pr = cProfile.Profile()
        pr.enable()
        out = mod.decompress(DATA)
        pr.disable()
        print("### cProfile: %s (%s)  python %s" %
              (args.profile, mod.NAME, sys.version.split()[0]))
        print("### correctness:", verify(out, ref) or 'OK')
        pstats.Stats(pr).sort_stats(args.sort).print_stats(18)
        return

    names = args.tier or TIERS
    mods = []
    for name in names:
        try:
            mods.append((name, importlib.import_module(name)))
        except ImportError as e:
            print("%-14s SKIP (%s)" % (name, e))
    # Windows desktop is noisy: INTERLEAVE the tiers round-robin so that any
    # drift (thermal, background load) hits every tier equally, then report
    # best-of, which is the noise-robust statistic for a deterministic workload.
    times = {n: [] for n, _ in mods}
    outs = {}
    for n, m in mods:
        outs[n] = m.decompress(DATA)          # warm up
    for _ in range(args.repeats):
        for n, m in mods:
            t = time.perf_counter()
            outs[n] = m.decompress(DATA)
            times[n].append(time.perf_counter() - t)

    print("python %s   data=%s   repeats=%d (interleaved)"
          % (sys.version.split()[0], os.path.basename(DATA), args.repeats))
    print("%-14s %-10s %-10s %-12s %s"
          % ('tier', 'best(s)', 'median(s)', 'vs T0(best)', 'correctness'))
    base = None
    for n, m in mods:
        ts = times[n]
        best, med = min(ts), statistics.median(ts)
        if base is None:
            base = best
        problems = verify(outs[n], ref)
        print("%-14s %-10.4f %-10.4f %-12s %s"
              % (n, best, med, '%.3fx' % (base / best),
                 'OK (md5+bz2)' if not problems else '; '.join(problems)))


if __name__ == '__main__':
    main()
