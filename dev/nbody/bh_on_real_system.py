"""Barnes-Hut vs direct summation on the ACTUAL --bodies N system.

`crossover.py` answered "where is the BH crossover?" on a clustered blob inside
the unit sphere -- a distribution its own docstring calls "favourable to the
tree", chosen deliberately so the anti-result would be conservative. That was
the right call when the benchmark only ever ran N = 5.

`--bodies N` changes the question. The report dismisses Barnes-Hut partly
because its crossover sits near N = 300-400 while the benchmark runs at N = 5,
and we can now run at N = 400. Anyone reading that will immediately ask whether
the tree wins once you actually go there. This measures it, and on the right
distribution: the `--bodies N` system is not a blob, it is a set of nearly
coplanar circular orbits with semi-major axes marching outward from 40 AU, plus
one dominant central mass. Spatial distribution is exactly what a tree code is
sensitive to, so reusing the blob number here would not be honest.

    python bh_on_real_system.py [--theta 0.5] [--repeat 5]
                                [--bodies 5,20,50,100,200,400]
"""
import argparse
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import crossover                                             # noqa: E402

BM = os.path.join(ROOT, "benchmarks", "bm_nbody", "run_benchmark.py")


def real_system(n):
    """The exact bodies `--bodies n` simulates, as crossover's (x,y,z,m)."""
    spec = importlib.util.spec_from_file_location("bm_n%d" % n, BM)
    m = importlib.util.module_from_spec(spec)
    # the native kernel is irrelevant here and only slows the import
    os.environ["HWSW_BACKEND"] = "python"
    spec.loader.exec_module(m)
    m._configure(n)
    return [(r[0], r[1], r[2], mass) for (r, _v, mass) in m.SYSTEM]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--theta", type=float, default=0.5)
    ap.add_argument("--repeat", type=int, default=5)
    ap.add_argument("--bodies", default="5,20,50,100,200,400")
    args = ap.parse_args()

    sizes = [int(x) for x in args.bodies.split(",") if x.strip()]

    print("Barnes-Hut vs direct summation, on the --bodies N system")
    print("theta = %g, best of %d, per force evaluation (tree rebuild "
          "included -- the bodies move every step)\n" % (args.theta,
                                                         args.repeat))
    print("%5s %12s %12s %9s  %11s %11s"
          % ("N", "direct ms", "BH ms", "BH/direct", "med rel err",
             "max/rms err"))

    for n in sizes:
        bodies = real_system(n)
        t_dir, a_dir = crossover.timeit(
            lambda: crossover.accel_direct(bodies), args.repeat)
        t_bh, a_bh = crossover.timeit(
            lambda: crossover.accel_bh(bodies, args.theta), args.repeat)
        med, worst = crossover.acc_err(a_dir, a_bh)
        print("%5d %12.3f %12.3f %8.2fx  %11.2e %11.2e"
              % (n, t_dir * 1e3, t_bh * 1e3, t_bh / t_dir, med, worst))

    print("\nBH/direct > 1 means the tree is SLOWER. The tree also costs the "
          "accuracy in\nthe last two columns, which the exact O(N^2) kernel "
          "does not.")


if __name__ == "__main__":
    main()
