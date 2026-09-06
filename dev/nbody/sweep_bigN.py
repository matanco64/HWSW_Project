"""Stock rolled Python vs the native kernel, at N far beyond the unroll wall.

`sweep_n.py` stops at N = 400 because that is where emitting an O(N^2) function
stops being survivable. The interesting region starts right after: the native
kernel is O(N^2) in *time* but O(1) in *code size*, so it keeps going where
partial evaluation cannot follow. This measures that region on the shipped
benchmark, with the back end pinned, so both sides are the same file.

Work is held roughly constant by scaling the step count with the pair count, so
the columns are comparable down the table rather than exploding as N^2.

    python sweep_bigN.py [--bodies 100,200,400,800,1600,3200] [--work 4000000]
"""
import argparse
import gc
import importlib.util
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BM = os.path.join(ROOT, "benchmarks", "bm_nbody", "run_benchmark.py")


def load(backend, nbodies, tag):
    """Fresh module with the back end pinned, configured for N bodies."""
    os.environ["HWSW_BACKEND"] = backend
    # NBODY_MAX_UNROLL_PAIRS=0 forces the rolled loop for the Python side at
    # every N, so the Python column measures one implementation throughout
    # rather than silently switching from unrolled to rolled mid-table.
    os.environ["NBODY_MAX_UNROLL_PAIRS"] = "0"
    spec = importlib.util.spec_from_file_location("bm_%s_%d" % (tag, nbodies),
                                                  BM)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    if backend == "native" and m.nbody_rs is None:
        return None
    m._configure(nbodies)
    return m


def timed(fn, repeat):
    best = float("inf")
    for _ in range(repeat):
        gc.collect()
        gc.disable()
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
        gc.enable()
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bodies", default="100,200,400,800,1600,3200")
    ap.add_argument("--work", type=int, default=4000000,
                    help="target pair-updates per timed call")
    ap.add_argument("--repeat", type=int, default=3)
    args = ap.parse_args()

    sizes = [int(x) for x in args.bodies.split(",") if x.strip()]

    print("Rolled Python vs native kernel, constant pair-updates per call")
    print("target work = %d pair-updates, best of %d\n"
          % (args.work, args.repeat))
    print("%6s %11s %6s %12s %12s %9s"
          % ("N", "pairs", "steps", "python ms", "native ms", "speedup"))

    for n in sizes:
        pairs = n * (n - 1) // 2
        steps = max(1, args.work // pairs)

        mp = load("python", n, "py")
        tp = timed(lambda: mp.advance(0.01, steps), args.repeat)

        mn = load("native", n, "rs")
        if mn is None:
            print("%6d %11d %6d %12.1f %12s %9s"
                  % (n, pairs, steps, tp * 1e3, "n/a", "-"))
            continue
        sysn = mn.nbody_rs.System(list(mn.SYSTEM))
        tn = timed(lambda: sysn.advance(0.01, steps), args.repeat)

        print("%6d %11d %6d %12.1f %12.2f %8.1fx"
              % (n, pairs, steps, tp * 1e3, tn * 1e3, tp / tn))

    print("\nBoth columns are the same run_benchmark.py with HWSW_BACKEND "
          "pinned.\nThe Python side is forced to the rolled loop at every N "
          "(NBODY_MAX_UNROLL_PAIRS=0)\nso the column measures one "
          "implementation throughout.")


if __name__ == "__main__":
    main()
