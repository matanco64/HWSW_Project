"""Correctness oracle: every tier vs the stock kernel, bit for bit where
possible and to a stated tolerance otherwise.

For each tier we integrate the identical initial condition for N steps and
compare, component by component, the 35-float body-state vector (x, y, z,
vx, vy, vz, m per body) and the reported total energy.

Reported per tier:
  max |abs delta|   over the 35 state components
  max |rel delta|   over the 35 state components (guarded for exact zeros)
  energy abs/rel    divergence of report_energy()
  bit-identical     True iff every component compares == to stock

Also checks the *landed* benchmark file (benchmarks/bm_nbody/run_benchmark.py)
against the stock pyperformance file, which is the claim that actually has to
hold for the report.

    python verify.py [--steps 20000]
"""
import argparse
import importlib.machinery
import importlib.util
import os
import sys

import t0_stock
import t1_micro
import t2_soa
import t3_unroll

TIERS = [
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
    pass

# Tolerances.
#
# Componentwise *relative* error is the wrong metric here: the Sun sits near
# the origin after offset_momentum(), so its coordinates are ~1e-3 while
# Neptune's are ~30.  A 1e-12 absolute wobble is 1e-9 relative on the Sun and
# 3e-14 relative on Neptune, even though both are the same physical nothing.
# We therefore score the state vector by max|delta| scaled by the largest
# component of the reference state (an infinity-norm relative error), and the
# energy -- the benchmark's actual observable -- by ordinary relative error.
#
# For reference, symplectic Euler at dt=0.01 has its own O(dt) truncation
# error: it drifts the total energy by ~1e-5 relative over these 20,000 steps.
# Everything reported below is 6+ orders of magnitude under that, i.e. pure
# floating-point rounding, not a change in the physics.
TOL_STATE = 1e-11          # ||delta||_inf / ||reference||_inf
TOL_ENERGY = 1e-12         # relative


def _rel(a, b):
    d = abs(a - b)
    s = max(abs(a), abs(b))
    return d / s if s else d


def compare(label, ref_state, ref_e, got_state, got_e):
    assert len(ref_state) == len(got_state), label
    abs_d = max(abs(a - b) for a, b in zip(ref_state, got_state))
    scale = max(abs(a) for a in ref_state) or 1.0
    inf_rel = abs_d / scale
    worst_component_rel = max(_rel(a, b) for a, b in zip(ref_state, got_state))
    e_abs = abs(ref_e - got_e)
    e_rel = _rel(ref_e, got_e)
    exact = (list(ref_state) == list(got_state)) and (ref_e == got_e)
    print("%-24s state |d|=%8.2e (inf-rel %8.2e, worst-comp %8.2e) | "
          "energy rel=%8.2e | bit-identical=%s"
          % (label, abs_d, inf_rel, worst_component_rel, e_rel, exact))
    ok = inf_rel <= TOL_STATE and e_rel <= TOL_ENERGY
    if not ok:
        print("    *** FAIL: exceeds tolerance (state %g / energy %g)"
              % (TOL_STATE, TOL_ENERGY))
    return ok, exact


def _load(path, name):
    # An explicit SourceFileLoader is required because the pristine stock copy
    # is kept as ".py.bak", and spec_from_file_location returns None for a
    # suffix it does not recognise as importable.
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_file_location(name, path, loader=loader)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_landed(steps):
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(os.path.dirname(here))
    stock_path = os.path.join(
        os.path.dirname(repo), "pyperformance", "pyperformance", "data-files",
        "benchmarks", "bm_nbody", "run_benchmark.py")
    opt_path = os.path.join(repo, "benchmarks", "bm_nbody",
                            "run_benchmark.py")
    if not os.path.exists(stock_path):
        # WSL working copy has no sibling pyperformance checkout; fall back to
        # the pristine copy kept next to this file.
        stock_path = os.path.join(here, "stock_run_benchmark.py.bak")
    if not os.path.exists(stock_path):
        print("\n(stock pyperformance source not found at %s -- "
              "skipping landed-benchmark check)" % stock_path)
        return True
    print("\nLANDED BENCHMARK: %s\n           versus: %s"
          % (opt_path, stock_path))
    stock = _load(stock_path, "_nbody_stock")
    opt = _load(opt_path, "_nbody_opt")

    def flat(m):
        out = []
        for (r, v, mass) in m.SYSTEM:
            out.extend(r)
            out.extend(v)
            out.append(mass)
        return out

    for m in (stock, opt):
        m.offset_momentum(m.BODIES[m.DEFAULT_REFERENCE])
    e0s, e0o = stock.report_energy(), opt.report_energy()
    stock.advance(0.01, steps)
    opt.advance(0.01, steps)
    ok0, ex0 = compare("  initial energy", [e0s], e0s, [e0o], e0o)
    ok1, ex1 = compare("  after %d steps" % steps, flat(stock),
                       stock.report_energy(), flat(opt), opt.report_energy())
    return ok0 and ok1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=20000)
    a = ap.parse_args()

    ref = t0_stock.make_state()
    t0_stock.advance(ref, 0.01, a.steps)
    ref_state, ref_e = t0_stock.dump(ref), t0_stock.energy(ref)
    print("reference: T0 stock, %d steps, energy = %.17g"
          % (a.steps, ref_e))
    print("tolerance: ||delta||_inf / ||ref||_inf <= %g, energy rel <= %g\n"
          % (TOL_STATE, TOL_ENERGY))

    all_ok = True
    for (name, mk, adv, en, dp) in TIERS:
        st = mk()
        adv(st, 0.01, a.steps)
        ok, _ = compare(name, ref_state, ref_e, dp(st), float(en(st)))
        all_ok &= ok

    all_ok &= check_landed(a.steps)
    print("\n%s" % ("ALL TIERS WITHIN TOLERANCE" if all_ok
                    else "*** SOME TIERS FAILED ***"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
