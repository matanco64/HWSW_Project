"""Correctness + speed check for the Rust/PyO3 `nbody_rs` wheel.

Run after building and installing the wheel with the interpreter you are
checking (tools/build_wheel.sh installs the file it just built, which the
two-step maturin/pip recipe does not):

    ./tools/build_wheel.sh nbody --python /root/hwsw-env/py310/bin/python
    /root/hwsw-env/py310/bin/python dev/nbody/rs_check.py

The claim being tested is EQUALITY, not closeness: `src/lib.rs` is written to
perform the same IEEE-754 double operations in the same order as the Python
loop, so the 35-float state after 20,000 steps should compare `==` to stock.
If it does not, the divergence will be in `powf`, and the honest claim
degrades to a stated tolerance -- which this script prints either way.

Which of those two is the *contract* is a command-line choice, and the exit
status follows it, so a downgrade from equality to closeness cannot happen
silently between a run and what the reports say about it:

    (default)     exact equality is required; nonzero exit if state or energy
                  differs by a single bit.
    --tolerance   closeness is required instead (the thresholds below), for a
                  build whose `powf` is known to differ.  Exactness is still
                  measured and printed, just not enforced.

Both checks are always computed and reported; only the gate moves.
"""
import argparse
import gc
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nbody_rs                                            # noqa: E402
import common                                              # noqa: E402
import t0_stock                                            # noqa: E402

STEPS = int(os.environ.get("NBODY_STEPS", "20000"))
ROUNDS = int(os.environ.get("NBODY_ROUNDS", "9"))

# Same thresholds as dev/nbody/verify.py, and for the same reason: the Sun sits
# near the origin after offset_momentum(), so componentwise relative error is
# meaningless for it.  State is scored as an infinity-norm relative error and
# energy as an ordinary relative error.
TOL_STATE = 1e-11
TOL_ENERGY = 1e-12


def make_rust():
    sysr = nbody_rs.System(
        [(list(r), list(v), m) for (r, v, m) in common.fresh_bodies()])
    sysr.offset_momentum(0)
    return sysr


def dump_rust(sysr):
    pos, vel, mass = sysr.state()
    out = []
    for i in range(len(mass)):
        out.extend(pos[3 * i:3 * i + 3])
        out.extend(vel[3 * i:3 * i + 3])
        out.append(mass[i])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tolerance", action="store_true",
                    help="require closeness (state inf-rel <= %g, energy rel "
                         "<= %g) instead of exact equality"
                         % (TOL_STATE, TOL_ENERGY))
    args = ap.parse_args()
    contract = "tolerance" if args.tolerance else "exact equality"
    print("python %s | steps=%d rounds=%d | contract: %s"
          % (sys.version.split()[0], STEPS, ROUNDS, contract))

    # ---- correctness -----------------------------------------------------
    py = t0_stock.make_state()
    rs = make_rust()
    e0_py, e0_rs = t0_stock.energy(py), rs.energy()
    print("\ninitial energy   py %r\n                 rs %r\n   equal: %s"
          % (e0_py, e0_rs, e0_py == e0_rs))

    t0_stock.advance(py, 0.01, STEPS)
    rs.advance(0.01, STEPS)
    a, b = t0_stock.dump(py), dump_rust(rs)
    e_py, e_rs = t0_stock.energy(py), rs.energy()
    max_abs = max(abs(x - y) for x, y in zip(a, b))
    scale = max(abs(x) for x in a)
    print("\nafter %d steps   py %r\n                 rs %r" % (STEPS, e_py,
                                                                e_rs))
    print("   state bit-identical : %s" % (a == b,))
    print("   energy bit-identical: %s" % (e_py == e_rs,))
    print("   max |delta| state   : %.3e  (inf-rel %.3e)"
          % (max_abs, max_abs / scale if scale else 0.0))
    denom = max(abs(e_py), abs(e_rs))
    e_rel = abs(e_py - e_rs) / denom if denom else 0.0
    print("   energy rel delta    : %.3e" % e_rel)

    # Exact and tolerance verdicts are kept separate on purpose: passing the
    # tolerance is not evidence for the equality claim the reports make, so the
    # two are never collapsed into one boolean.
    exact = (a == b) and (e_py == e_rs)
    inf_rel = max_abs / scale if scale else 0.0
    close = inf_rel <= TOL_STATE and e_rel <= TOL_ENERGY
    ok = close if args.tolerance else exact
    if not ok:
        if args.tolerance:
            print("\n*** FAIL: exceeds tolerance (state %g / energy %g); "
                  "bit-identical=%s" % (TOL_STATE, TOL_ENERGY, exact))
        else:
            print("\n*** FAIL: nbody_rs is not bit-identical to stock, which "
                  "is the declared contract. The tolerance check %s -- rerun "
                  "with --tolerance only after the reports have been changed "
                  "to claim closeness rather than equality."
                  % ("passes" if close else "also fails"))

    # ---- speed (interleaved, min-of-rounds) ------------------------------
    tpy = trs = float("inf")
    for _ in range(ROUNDS):
        st = t0_stock.make_state()
        gc.collect(); gc.disable()
        t = time.perf_counter(); t0_stock.advance(st, 0.01, STEPS)
        tpy = min(tpy, time.perf_counter() - t)
        gc.enable()

        sr = make_rust()
        gc.collect(); gc.disable()
        t = time.perf_counter(); sr.advance(0.01, STEPS)
        trs = min(trs, time.perf_counter() - t)
        gc.enable()
    print("\nadvance(0.01, %d), min of %d interleaved rounds:" % (STEPS,
                                                                  ROUNDS))
    print("   CPython stock : %9.3f ms" % (tpy * 1e3,))
    print("   Rust  nbody_rs: %9.3f ms" % (trs * 1e3,))
    print("   kernel speedup: %9.1fx" % (tpy / trs,))

    # ---- FFI boundary cost ----------------------------------------------
    sr = make_rust()
    n = 20000
    t = time.perf_counter()
    for _ in range(n):
        sr.energy()
    per_call = (time.perf_counter() - t) / n
    print("\nFFI crossing cost (System.energy(), %d calls): %.0f ns/call"
          % (n, per_call * 1e9))
    print("   -> %.2e of one advance(0.01, %d) call"
          % (per_call / trs, STEPS))

    print("\n%s" % ("CONTRACT HELD (%s)" % contract if ok
                    else "*** CONTRACT VIOLATED (%s) ***" % contract))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
