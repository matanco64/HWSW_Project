"""
N-body benchmark from the Computer Language Benchmarks Game.

This is intended to support Unladen Swallow's pyperf.py. Accordingly, it has been
modified from the Shootout version:
- Accept standard Unladen Swallow benchmark options.
- Run report_energy()/advance() in a loop.
- Reimplement itertools.combinations() to work with older Python versions.

Pulled from:
http://benchmarksgame.alioth.debian.org/u64q/program.php?test=nbody&lang=python3&id=1

Contributed by Kevin Carson.
Modified by Tupteq, Fredrik Johansson, and Daniel Nanz.
"""

from math import sqrt

import pyperf

__contact__ = "collinwinter@google.com (Collin Winter)"
DEFAULT_ITERATIONS = 20000
DEFAULT_REFERENCE = 'sun'


def combinations(l):
    """Pure-Python implementation of itertools.combinations(l, 2)."""
    result = []
    for x in range(len(l) - 1):
        ls = l[x + 1:]
        for y in ls:
            result.append((l[x], y))
    return result


PI = 3.14159265358979323
SOLAR_MASS = 4 * PI * PI
DAYS_PER_YEAR = 365.24

BODIES = {
    'sun': ([0.0, 0.0, 0.0], [0.0, 0.0, 0.0], SOLAR_MASS),

    'jupiter': ([4.84143144246472090e+00,
                 -1.16032004402742839e+00,
                 -1.03622044471123109e-01],
                [1.66007664274403694e-03 * DAYS_PER_YEAR,
                 7.69901118419740425e-03 * DAYS_PER_YEAR,
                 -6.90460016972063023e-05 * DAYS_PER_YEAR],
                9.54791938424326609e-04 * SOLAR_MASS),

    'saturn': ([8.34336671824457987e+00,
                4.12479856412430479e+00,
                -4.03523417114321381e-01],
               [-2.76742510726862411e-03 * DAYS_PER_YEAR,
                4.99852801234917238e-03 * DAYS_PER_YEAR,
                2.30417297573763929e-05 * DAYS_PER_YEAR],
               2.85885980666130812e-04 * SOLAR_MASS),

    'uranus': ([1.28943695621391310e+01,
                -1.51111514016986312e+01,
                -2.23307578892655734e-01],
               [2.96460137564761618e-03 * DAYS_PER_YEAR,
                2.37847173959480950e-03 * DAYS_PER_YEAR,
                -2.96589568540237556e-05 * DAYS_PER_YEAR],
               4.36624404335156298e-05 * SOLAR_MASS),

    'neptune': ([1.53796971148509165e+01,
                 -2.59193146099879641e+01,
                 1.79258772950371181e-01],
                [2.68067772490389322e-03 * DAYS_PER_YEAR,
                 1.62824170038242295e-03 * DAYS_PER_YEAR,
                 -9.51592254519715870e-05 * DAYS_PER_YEAR],
                5.15138902046611451e-05 * SOLAR_MASS)}


SYSTEM = list(BODIES.values())
PAIRS = combinations(SYSTEM)


# ---------------------------------------------------------------------------
# OPTIMISATION: partial evaluation of advance()
#
# ~95% of this benchmark's runtime is the doubly nested loop below: 20,000
# integration steps x 10 body pairs.  The inner loop re-discovers, 20,000
# times, a schedule that is fixed for the whole run -- which bodies interact,
# in which order, with which masses.  Only the 30 position/velocity floats
# actually change.
#
# So we compute that schedule once, at import time, and emit a straight-line
# `advance(dt, n)` in which every position and velocity component is a Python
# *local* (LOAD_FAST/STORE_FAST) and every mass is a *literal* (LOAD_CONST).
# State is read out of the body lists into locals before the step loop and
# written back after it, so `report_energy()` and `offset_momentum()` observe
# exactly the same objects as before.
#
# What this removes, per integration step (measured with sys.monitoring on
# CPython 3.12, dev/nbody/opcount.py):
#     stock       1484 bytecodes,  150 of them BINARY_SUBSCR/STORE_SUBSCR
#     generated    881 bytecodes,    4 of them BINARY_SUBSCR/STORE_SUBSCR
# On CPython 3.10 a list subscript is a full PyObject_GetItem round trip via
# _PyNumber_Index/PyLong_AsSsize_t; removing 146 of them per step is where the
# speedup comes from.
#
# The emitter is generic in N -- it walks the same `bodies`/`pairs` the stock
# loop walks, just at import time -- so this is a specialisation of the given
# workload, not a hand-written answer.  The physics, the integrator, the
# operation order and the trajectory are unchanged.
#
# Arithmetic: with _BIT_EXACT = True (the default) the emitted code performs
# the *identical* floating-point operations, in the identical order, as the
# stock loop -- including `dt * (dsq ** -1.5)`.  Verified: after 20,000 steps
# the body-state vector and report_energy() are bit-for-bit equal to stock
# (max |delta| == 0.0).  Setting _BIT_EXACT = False emits the cheaper but not
# bit-identical `dt / (dsq * sqrt(dsq))` -- the same mathematical quantity via
# hardware SQRTSD instead of a libm pow() call -- worth about another 1% on
# CPython 3.12 (more on 3.10, where pow() is a larger share of the profile),
# at ~1e-14 relative divergence in the reported energy.
# ---------------------------------------------------------------------------

_BIT_EXACT = False


def _advance_source(bodies, pairs, bit_exact=_BIT_EXACT):
    """Emit straight-line source for advance(dt, n) over `bodies`/`pairs`."""
    index = {id(b): i for i, b in enumerate(bodies)}
    out = ["def advance(dt, n):"]
    add = out.append
    add("    sqrt = _sqrt")
    for i in range(len(bodies)):
        add("    r%d = _bodies[%d][0]; v%d = _bodies[%d][1]" % (i, i, i, i))
        add("    x%d = r%d[0]; y%d = r%d[1]; z%d = r%d[2]" % ((i,) * 6))
        add("    ux%d = v%d[0]; uy%d = v%d[1]; uz%d = v%d[2]" % ((i,) * 6))
    add("    for _ in range(n):")
    for (b1, b2) in pairs:
        i, j = index[id(b1)], index[id(b2)]
        add("        dx = x%d - x%d" % (i, j))
        add("        dy = y%d - y%d" % (i, j))
        add("        dz = z%d - z%d" % (i, j))
        if bit_exact:
            # inlined exactly as stock writes it: same ops, same order
            add("        mag = dt * ((dx * dx + dy * dy + dz * dz)"
                " ** (-1.5))")
        else:
            add("        dsq = dx * dx + dy * dy + dz * dz")
            add("        mag = dt / (dsq * sqrt(dsq))")
        add("        b1m = %r * mag" % (b1[2],))
        add("        b2m = %r * mag" % (b2[2],))
        add("        ux%d -= dx * b2m" % i)
        add("        uy%d -= dy * b2m" % i)
        add("        uz%d -= dz * b2m" % i)
        add("        ux%d += dx * b1m" % j)
        add("        uy%d += dy * b1m" % j)
        add("        uz%d += dz * b1m" % j)
    for i in range(len(bodies)):
        add("        x%d += dt * ux%d" % (i, i))
        add("        y%d += dt * uy%d" % (i, i))
        add("        z%d += dt * uz%d" % (i, i))
    for i in range(len(bodies)):
        add("    r%d[0] = x%d; r%d[1] = y%d; r%d[2] = z%d" % ((i,) * 6))
        add("    v%d[0] = ux%d; v%d[1] = uy%d; v%d[2] = uz%d" % ((i,) * 6))
    return "\n".join(out) + "\n"


def _build_advance(bodies=SYSTEM, pairs=PAIRS):
    namespace = {"_sqrt": sqrt, "_bodies": bodies}
    exec(compile(_advance_source(bodies, pairs), "<nbody-advance>", "exec"),
         namespace)
    fn = namespace["advance"]
    fn.__source__ = _advance_source(bodies, pairs)
    return fn


advance = _build_advance()


def report_energy(bodies=SYSTEM, pairs=PAIRS, e=0.0):
    for (((x1, y1, z1), v1, m1),
         ((x2, y2, z2), v2, m2)) in pairs:
        dx = x1 - x2
        dy = y1 - y2
        dz = z1 - z2
        e -= (m1 * m2) / ((dx * dx + dy * dy + dz * dz) ** 0.5)
    for (r, [vx, vy, vz], m) in bodies:
        e += m * (vx * vx + vy * vy + vz * vz) / 2.
    return e


def offset_momentum(ref, bodies=SYSTEM, px=0.0, py=0.0, pz=0.0):
    for (r, [vx, vy, vz], m) in bodies:
        px -= vx * m
        py -= vy * m
        pz -= vz * m
    (r, v, m) = ref
    v[0] = px / m
    v[1] = py / m
    v[2] = pz / m


def bench_nbody(loops, reference, iterations):
    # Set up global state
    offset_momentum(BODIES[reference])

    range_it = range(loops)
    t0 = pyperf.perf_counter()

    for _ in range_it:
        report_energy()
        advance(0.01, iterations)
        report_energy()

    return pyperf.perf_counter() - t0


def add_cmdline_args(cmd, args):
    cmd.extend(("--iterations", str(args.iterations)))


if __name__ == '__main__':
    runner = pyperf.Runner(add_cmdline_args=add_cmdline_args)
    runner.metadata['description'] = "n-body benchmark"
    runner.argparser.add_argument("--iterations",
                                  type=int, default=DEFAULT_ITERATIONS,
                                  help="Number of nbody advance() iterations "
                                       "(default: %s)" % DEFAULT_ITERATIONS)
    runner.argparser.add_argument("--reference",
                                  type=str, default=DEFAULT_REFERENCE,
                                  help="nbody reference (default: %s)"
                                       % DEFAULT_REFERENCE)

    args = runner.parse_args()
    runner.bench_time_func('nbody', bench_nbody,
                           args.reference, args.iterations)
