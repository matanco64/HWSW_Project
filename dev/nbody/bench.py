"""Times every nbody tier back-to-back, interleaved round-robin.

Protocol (see hygiene.py for why):
  * process pinned to one core at HIGH priority;
  * R rounds; each round runs every tier once, in the same order, from a
    freshly built state, with the GC off;
  * the reported estimator is the MINIMUM over rounds (a hard lower bound on
    the true cost; noise only ever adds), with the median alongside so the
    spread is visible.
  * "E for_ only (control)" in t1_variants.py is a semantic no-op; it should
    read 1.00x.  If it doesn't, the run is too noisy to quote.

    python bench.py [--steps 4000] [--rounds 41]
"""
import argparse
import gc
import statistics
import sys
import time

import hygiene
import t0_stock
import t1_micro
import t2_soa
import t3_unroll

TIERS = [
    ("T0  stock (reference)", t0_stock.make_state, t0_stock.advance,
     t0_stock.energy, t0_stock.dump),
    ("T1  micro-opt AoS", t1_micro.make_state, t1_micro.advance,
     t1_micro.energy, t1_micro.dump),
    ("T2  SoA flat lists", t2_soa.make_state, t2_soa.advance,
     t2_soa.energy, t2_soa.dump),
    ("T3e unrolled bit-exact", t3_unroll.make_state_exact,
     t3_unroll.advance_exact, t3_unroll.energy_exact, t3_unroll.dump),
    ("T3  unrolled sqrt", t3_unroll.make_state, t3_unroll.advance,
     t3_unroll.energy, t3_unroll.dump),
    ("T3f unrolled sqrt+fold", t3_unroll.make_state_fold,
     t3_unroll.advance_fold, t3_unroll.energy, t3_unroll.dump),
]

try:
    import tanti_numpy
    TIERS += [
        ("TA  numpy 10-pair", tanti_numpy.make_state, tanti_numpy.advance,
         tanti_numpy.energy, tanti_numpy.dump),
        ("TA  numpy NxN", tanti_numpy.make_state_nxn, tanti_numpy.advance_nxn,
         tanti_numpy.energy, tanti_numpy.dump),
    ]
except ImportError:                                   # pragma: no cover
    sys.stderr.write("note: numpy unavailable, skipping the anti-result\n")


def run(tiers, steps, rounds):
    times = {n: [] for (n, _, _, _, _) in tiers}
    energies = {}
    for _ in range(rounds):
        for (name, mk, adv, en, dp) in tiers:
            st = mk()
            gc.collect()
            gc.disable()
            t0 = time.perf_counter()
            en(st)
            adv(st, 0.01, steps)
            e = en(st)
            t1 = time.perf_counter()
            gc.enable()
            times[name].append(t1 - t0)
            energies[name] = float(e)
    return times, energies


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=4000)
    ap.add_argument("--rounds", type=int, default=41)
    a = ap.parse_args()

    print("hygiene: %s" % hygiene.tune())
    print("python %s  |  steps=%d  rounds=%d  |  estimator = min over rounds"
          % (sys.version.split()[0], a.steps, a.rounds))
    times, energies = run(TIERS, a.steps, a.rounds)
    base = min(times[TIERS[0][0]])
    print("%-24s %9s %9s %9s   %s"
          % ("tier", "best ms", "med ms", "speedup", "energy"))
    for (name, _, _, _, _) in TIERS:
        v = times[name]
        print("%-24s %9.3f %9.3f %8.3fx   %.15g"
              % (name, min(v) * 1e3, statistics.median(v) * 1e3,
                 base / min(v), energies[name]))


if __name__ == "__main__":
    main()
