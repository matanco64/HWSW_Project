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

Two different contracts are checked, and they are not interchangeable:

  tiers            scored against TOL_STATE / TOL_ENERGY.  T3's sqrt variants
                   deliberately reorder the arithmetic, so they are close but
                   not bit-identical, and a tolerance verdict is the honest one.
  landed benchmark scored on EXACT equality.  benchmarks/bm_nbody/run_benchmark.py
                   keeps stock's operation order precisely so the reports can
                   say "compares exactly equal to stock", so that is the claim
                   the exit status defends.  Its tolerance verdict is still
                   computed and printed, but passing it is not sufficient.

A violation of either contract returns a nonzero exit status.

    python verify.py [--steps 20000] [--bodies 5[,10,20,...]]

`--bodies` takes a comma-separated list of body counts.  For each N it checks
(a) that dev/nbody/common.py's `extra_bodies()` and the landed benchmark's
`_extra_bodies()` emit bit-identical body tables, and (b) that the landed
benchmark's generated `advance()` is still bit-exact against the stock kernel
at that N.  N = 5 additionally runs the full tier ladder.
"""
import argparse
import importlib.machinery
import importlib.util
import os
import sys

import common
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


def _paths():
    """(stock, landed) benchmark sources.

    The stock reference is looked for in a sibling pyperformance checkout, then
    in the installed pyperformance package (the course VM has no checkout),
    then in the pristine copy kept next to this file.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(os.path.dirname(here))
    rel = ("data-files", "benchmarks", "bm_nbody", "run_benchmark.py")
    candidates = [os.path.join(os.path.dirname(repo), "pyperformance",
                               "pyperformance", *rel)]
    try:
        import pyperformance
        candidates.append(os.path.join(os.path.dirname(pyperformance.__file__),
                                       *rel))
    except ImportError:
        pass
    candidates.append(os.path.join(here, "stock_run_benchmark.py.bak"))
    stock = next((c for c in candidates if os.path.exists(c)), candidates[0])
    opt = os.path.join(repo, "benchmarks", "bm_nbody", "run_benchmark.py")
    return stock, opt


def _scale_stock_module(mod, n):
    """Give an *unmodified* stock run_benchmark module the N > 5 system.

    Does by hand exactly what the optimized file's `_configure()` does, so the
    stock reference at N is the stock kernel run on the identical bodies --
    no edit to the pristine stock source required.
    """
    if n == common.DEFAULT_BODIES:
        return
    for k, (r, v, m) in enumerate(common.extra_bodies(n), 1):
        mod.BODIES['b%03d' % k] = (r, v, m)
    mod.SYSTEM[:] = list(mod.BODIES.values())
    mod.PAIRS[:] = mod.combinations(mod.SYSTEM)


def check_generators(n):
    """common.extra_bodies(n) must equal the landed file's _extra_bodies(n)."""
    _, opt_path = _paths()
    opt = _load(opt_path, "_nbody_opt_gen_%d" % n)
    mine = common.extra_bodies(n)
    theirs = [[list(r), list(v), m]
              for (r, v, m) in opt._extra_bodies(n).values()]
    ok = (mine == theirs)
    print("  body generators (common.py vs run_benchmark.py): "
          "%d extra bodies, identical=%s" % (len(mine), ok))
    return ok


def check_landed_n(steps, n):
    """Stock kernel vs the landed benchmark at --bodies N, bit for bit."""
    stock_path, opt_path = _paths()
    if not os.path.exists(stock_path):
        # Not a pass: a contract that was never checked must not read as held.
        print("  *** FAIL: stock source not found (%s) -- cannot check N=%d"
              % (stock_path, n))
        return False
    stock = _load(stock_path, "_nbody_stock_%d" % n)
    opt = _load(opt_path, "_nbody_opt_%d" % n)
    _scale_stock_module(stock, n)
    opt._configure(n)
    assert len(stock.SYSTEM) == len(opt.SYSTEM) == n

    def flat(m):
        out = []
        for (r, v, mass) in m.SYSTEM:
            out.extend(r)
            out.extend(v)
            out.append(mass)
        return out

    for m in (stock, opt):
        m.offset_momentum(m.BODIES[m.DEFAULT_REFERENCE])
    # the initial condition itself must match or nothing below means much
    if flat(stock) != flat(opt):
        print("  *** FAIL: initial conditions differ at N=%d" % n)
        return False
    e0s, e0o = stock.report_energy(), opt.report_energy()
    stock.advance(0.01, steps)
    opt.advance(0.01, steps)
    ok0, ex0 = compare("  initial energy", [e0s], e0s, [e0o], e0o)
    st, se = flat(stock), stock.report_energy()
    ok1, ex1 = compare("  after %d steps" % steps, st, se, flat(opt),
                       opt.report_energy())
    finite = all(x == x and abs(x) != float("inf") for x in st)
    drift = abs(se - e0s) / abs(e0s)
    print("  physical sanity: all finite=%s | energy drift over %d steps "
          "= %.2e relative" % (finite, steps, drift))
    # Same contract as check_landed(): the generated advance() at N is claimed
    # bit-exact against the stock kernel at N, so exactness gates the result.
    exact = ex0 and ex1
    if not exact:
        print("    *** FAIL: landed benchmark at N=%d is not bit-identical to "
              "stock (the declared contract)" % n)
    return ok0 and ok1 and finite and exact


def check_landed(steps):
    stock_path, opt_path = _paths()
    if not os.path.exists(stock_path):
        # Not a pass. This used to print "skipping" and return True, so a host
        # without the stock source reported the landed benchmark's exactness
        # contract as held without ever comparing a single float.
        print("\n*** FAIL: stock pyperformance source not found (looked for "
              "%s) -- the landed-benchmark contract cannot be checked"
              % stock_path)
        return False
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
    # The landed benchmark's declared contract is EXACT equality, not a
    # tolerance -- the shipped kernel keeps stock's operation order precisely so
    # that it can make that claim.  Reporting only the tolerance verdict here
    # would let a rounding-changing edit land silently while the reports still
    # said "compares exactly equal to stock", so exactness is what gates the
    # exit status.  The tolerance verdict is kept as an independent check.
    exact = ex0 and ex1
    if not exact:
        print("    *** FAIL: landed benchmark is not bit-identical to stock "
              "(the declared contract); tolerance verdict was %s"
              % ("pass" if (ok0 and ok1) else "fail"))
    return ok0 and ok1 and exact


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=20000)
    ap.add_argument("--bodies", type=str, default="5",
                    help="comma-separated body counts, e.g. 5,10,20,50")
    a = ap.parse_args()
    counts = [int(x) for x in a.bodies.split(",") if x.strip()]

    if counts != [5]:
        all_ok = True
        for n in counts:
            print("\n=== N = %d (%d pairs), %d steps ==="
                  % (n, n * (n - 1) // 2, a.steps))
            all_ok &= check_generators(n)
            all_ok &= check_landed_n(a.steps, n)
        print("\n%s" % ("BIT-EXACT AT EVERY N TESTED" if all_ok
                        else "*** FAILED AT SOME N ***"))
        return 0 if all_ok else 1

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
    print("\n%s" % ("ALL TIERS WITHIN TOLERANCE, LANDED BENCHMARK BIT-EXACT"
                    if all_ok else "*** CONTRACT VIOLATED ***"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
