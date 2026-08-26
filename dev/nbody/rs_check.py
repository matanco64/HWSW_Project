"""Correctness + speed check for the Rust/PyO3 `nbody_rs` wheel.

Run inside WSL after `maturin build --release` and installing the wheel:

    /root/hwsw-env/py310/bin/python dev/nbody/rs_check.py

The claim being tested is EQUALITY, not closeness: `src/lib.rs` is written to
perform the same IEEE-754 double operations in the same order as the Python
loop, so the 35-float state after 20,000 steps should compare `==` to stock.
If it does not, the divergence will be in `powf`, and the honest claim
degrades to a stated tolerance -- which this script prints either way.
"""
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
    print("python %s | steps=%d rounds=%d" % (sys.version.split()[0], STEPS,
                                              ROUNDS))

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
    print("   energy rel delta    : %.3e"
          % (abs(e_py - e_rs) / denom if denom else 0.0))

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


if __name__ == "__main__":
    main()
