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

import hashlib
import os

from math import cos, sin, sqrt

import pyperf

# Optional native tier: nbody_rs (rust/nbody/) is imported, never required.
# A missing wheel or wrong CPython ABI falls back to the generated Python
# below, which is itself the optimized version. Interface rules: rust/README.md.

# Back-end selection.  "auto" (the default) prefers the native kernel and falls
# back to Python; "python" and "native" pin it.  This exists because otherwise
# what gets measured depends on what happens to be installed in whichever venv
# pyperformance built -- two runs could measure different back ends and produce
# JSON that looks the same.  The choice is recorded in the pyperf metadata.
_BACKEND = os.environ.get("HWSW_BACKEND", "auto").lower()
if _BACKEND not in ("auto", "python", "native"):
    raise SystemExit("HWSW_BACKEND must be one of: auto, python, native")

try:
    import nbody_rs
except ImportError:                                          # pragma: no cover
    nbody_rs = None

if _BACKEND == "python":
    nbody_rs = None
elif _BACKEND == "native" and nbody_rs is None:
    raise SystemExit("HWSW_BACKEND=native but nbody_rs is not importable")

__contact__ = "collinwinter@google.com (Collin Winter)"
DEFAULT_ITERATIONS = 20000
DEFAULT_REFERENCE = 'sun'
DEFAULT_BODIES = 5


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


# --bodies N appends N-5 further bodies so the same all-pairs algorithm runs
# at a larger N. The integrator, step count and operation order are unchanged.
# N = 5 is the default and a no-op. Placement is closed-form and RNG-free, on
# wide circular orbits that stay >= 3 AU apart, so nothing can blow up and a
# run is reproducible. dev/nbody/FINDINGS.md section 7 has the derivation and
# the measured energy drift.

_GOLDEN_ANGLE = PI * (3.0 - 5.0 ** 0.5)


def _extra_bodies(n):
    """The N-5 bodies appended for --bodies N, as {name: (pos, vel, mass)}."""
    out = {}
    for k in range(1, n - DEFAULT_BODIES + 1):
        a = 40.0 + 3.0 * (k - 1)
        th = k * _GOLDEN_ANGLE
        inc = 0.05 * (k % 5)
        v = sqrt(SOLAR_MASS / a)
        ct, st = cos(th), sin(th)
        ci, si = cos(inc), sin(inc)
        out['b%03d' % k] = ([a * ct, a * st * ci, a * st * si],
                            [-v * st, v * ct * ci, v * ct * si],
                            SOLAR_MASS * 1e-5 * (1.0 + (k % 8) / 8.0))
    return out


# Above this many pairs, stop unrolling and use the rolled loop instead.
# Emitted source is O(N^2) and CPython needs ~40 kB of working set per pair:
# 20,000 pairs is N = 200, and N = 700 OOM-killed a 7 GB machine. Past the
# limit the technique still wins (1.37x at N = 400) but stops being sane.
# Override with NBODY_MAX_UNROLL_PAIRS.
_MAX_UNROLL_PAIRS = int(os.environ.get("NBODY_MAX_UNROLL_PAIRS", 20000))


def _advance_rolled(dt, n, bodies=SYSTEM, pairs=PAIRS):
    """The stock rolled loop, verbatim, for N too large to unroll.

    Same operations in the same order as the generated code, so results stay
    bit-identical; it just pays the interpreter overhead the emitter exists to
    remove. Used above _MAX_UNROLL_PAIRS, and on the native path for N > 5.
    """
    for _ in range(n):
        for (((x1, y1, z1), v1, m1),
             ((x2, y2, z2), v2, m2)) in pairs:
            dx = x1 - x2
            dy = y1 - y2
            dz = z1 - z2
            mag = dt * ((dx * dx + dy * dy + dz * dz) ** (-1.5))
            b1m = m1 * mag
            b2m = m2 * mag
            v1[0] -= dx * b2m
            v1[1] -= dy * b2m
            v1[2] -= dz * b2m
            v2[0] += dx * b1m
            v2[1] += dy * b1m
            v2[2] += dz * b1m
        for (r, [vx, vy, vz], m) in bodies:
            r[0] += dt * vx
            r[1] += dt * vy
            r[2] += dt * vz


def _configure(nbodies):
    """Re-derive SYSTEM / PAIRS / advance for --bodies N.  No-op at N = 5.

    SYSTEM and PAIRS are rewritten *in place* on purpose: they are the bound
    default arguments of report_energy() and offset_momentum(), which are
    left exactly as stock wrote them.  Rebinding the globals would not reach
    those defaults; mutating the list objects does.
    """
    global advance
    if nbodies == DEFAULT_BODIES:
        return
    if nbodies < DEFAULT_BODIES:
        raise ValueError("--bodies must be >= %d" % DEFAULT_BODIES)
    BODIES.update(_extra_bodies(nbodies))
    SYSTEM[:] = list(BODIES.values())
    PAIRS[:] = combinations(SYSTEM)

    # Regenerating advance() is the expensive part, and it is pure waste on the
    # native path, which never calls it -- the kernel owns the integration. Not
    # skipping it here would make `--bodies 1000 HWSW_BACKEND=native` attempt a
    # ~20 GB compile to build a function nothing invokes.
    if nbody_rs is not None:
        # ...but advance() must not be left describing the 5-body system. The
        # benchmark never calls it on this path, yet it is still a public,
        # callable function, and dev/nbody/verify.py once called it: on the
        # course VM that integrated half of a 10-body system and read as an
        # 18 AU divergence. The rolled loop needs no code generation, costs
        # nothing to bind, and is bit-identical to the generated kernel.
        advance = _advance_rolled
        return
    if len(PAIRS) > _MAX_UNROLL_PAIRS:
        advance = _advance_rolled
        return
    advance = _build_advance(SYSTEM, PAIRS)


# ---------------------------------------------------------------------------
# OPTIMISATION: partial evaluation of advance()
#
# ~95% of runtime is 20,000 steps x 10 pairs, and the inner loop re-discovers
# a schedule that is fixed for the whole run. So compute it once at import
# time and emit a straight-line advance(dt, n) with every coordinate a local
# and every mass a literal. State is read out of the body lists before the
# step loop and written back after, so report_energy() and offset_momentum()
# see the same objects as before.
#
# Per step this drops 1484 bytecodes to 881, and 150 list subscripts to 4
# (dev/nbody/opcount.py). On 3.10 a list subscript is a full PyObject_GetItem
# round trip, which is where the speedup comes from.
#
# The emitter walks whatever bodies/pairs it is handed, so this specialises
# the given workload rather than hand-writing an answer for five bodies. The
# emitted code performs the identical FP operations in the identical order as
# stock, including dt * (dsq ** -1.5): after 20,000 steps the state vector and
# report_energy() are bit-for-bit equal (max |delta| == 0.0).
# dev/nbody/FINDINGS.md sections 2 and 7.
# ---------------------------------------------------------------------------

def _advance_source(bodies, pairs, hoist=None):
    """Emit straight-line source for advance(dt, n) over `bodies`/`pairs`.

    `hoist` overrides the slot-index heuristic below; it exists so the A/B in
    dev/nbody/sweep_n.py can build both variants from this one emitter.
    """
    index = {id(b): i for i, b in enumerate(bodies)}
    out = ["def advance(dt, n):"]
    add = out.append
    # A local whose slot index is >= 256 costs an EXTENDED_ARG dispatch every
    # time it is touched, and the per-pair temporaries bind last. Binding them
    # first moves them to low slots: at N = 200 that is 1.13x, and it removes a
    # cliff at N = 31. Dead stores, so no arithmetic changes, and it is emitted
    # only when it can matter -- the shipped N = 5 source is unchanged.
    if hoist is None:
        hoist = 8 * len(bodies) + 10 > 255
    if hoist:
        add("    dx = dy = dz = mag = b1m = b2m = 0.0")
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
        # inlined exactly as stock writes it: same ops, same order
        add("        mag = dt * ((dx * dx + dy * dy + dz * dz)"
            " ** (-1.5))")
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
    # The source is generated once and reused for __source__.  At N = 5 that
    # is a 173-line string and generating it twice cost nothing; the emitted
    # code is O(N^2) in size, so at --bodies 200 it is 239k lines / 9.4 MB and
    # generating it twice is 1.4 s of pure waste.
    src = _advance_source(bodies, pairs)
    namespace = {"_bodies": bodies}
    exec(compile(src, "<nbody-advance>", "exec"), namespace)
    fn = namespace["advance"]
    fn.__source__ = src
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


def _bench_nbody_native(loops, reference, iterations):
    """The same benchmark, integrated by the Rust kernel.

    WHY THIS IS A DIFFERENT SHAPE FROM THE PYTHON PATH.  The kernel does not
    replace `advance()` call-for-call; it owns the state for the duration of
    the run.  `SYSTEM` is handed over once, the loop below is three method
    calls, and the state is read back at the end.  That is deliberate and it is
    the same reasoning the TPU case study uses when it preloads weights into
    the array and then streams inputs: crossing the boundary costs more than
    the work when the payload is small, so you move the data once and leave it
    there.  Marshalling 6N Python floats across the FFI on every one of 20,000
    steps would have cost more than the interpreter we are trying to escape.
    In the hardware proposal this object is the accelerator's register file and
    `advance()` is its doorbell -- see the report's HW section.

    WHY NATIVE CODE WINS HERE, in the terms of Lecture 4 ("it is always the
    memory").  `SYSTEM` is a list of tuples of lists of Python floats, so one
    coordinate is a `PyObject*` in a list, pointing at a separately heap
    allocated 32-byte `PyFloat`.  Reading `x1` is two dependent pointer hops to
    fetch eight bytes, and the ten pairs touch thirty such objects per step in
    whatever order the allocator happened to place them.  The Rust side holds
    `Vec<Vec3>` with `#[repr(C)]`: contiguous 24-byte records, one cache line
    per two bodies, no indirection and no boxing.  That is the lecture's
    "merging arrays" transformation, and it is the part of the win that partial
    evaluation cannot reach -- the generated Python removes the *subscript*
    but still ends up dereferencing boxed floats.

    Arithmetic is unchanged: same operations, same order, including the
    `dsq ** -1.5`.  Rust does not contract to FMA or reassociate floats without
    being asked, and it is not asked.  `dev/nbody/rs_check.py` asserts the full
    state vector and `report_energy()` are bit-identical to the Python path;
    that check is what makes this a substitution rather than an approximation.
    """
    # Setup, outside the timed region -- exactly where the Python path does its
    # own setup (offset_momentum, and the import-time codegen for advance()).
    system = nbody_rs.System(list(SYSTEM))
    system.offset_momentum(list(BODIES).index(reference))

    range_it = range(loops)
    t0 = pyperf.perf_counter()

    for _ in range_it:
        system.energy()
        system.advance(0.01, iterations)
        system.energy()

    elapsed = pyperf.perf_counter() - t0

    # Write the state back into SYSTEM. pyperf calls this function repeatedly
    # with different `loops`, and the Python path leaves SYSTEM mutated between
    # calls, so the native path has to as well or the two would drift apart
    # after the first invocation.
    pos, vel, _ = system.state()
    for i, (r, v, _m) in enumerate(SYSTEM):
        r[0], r[1], r[2] = pos[3 * i:3 * i + 3]
        v[0], v[1], v[2] = vel[3 * i:3 * i + 3]

    return elapsed


def bench_nbody(loops, reference, iterations):
    if nbody_rs is not None:
        return _bench_nbody_native(loops, reference, iterations)

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
    # Workers are spawned as fresh processes and re-import this module, so the
    # body count has to travel on their command line or they would silently
    # time the 5-body system while the manager thought it asked for N.
    cmd.extend(("--bodies", str(args.bodies)))



def _native_extension_file(module):
    """Path of the compiled extension behind `module`, not its package stub.

    maturin installs the crate as a package: `nbody_rs/__init__.py` is a
    three-line re-export generated identically for every build, and the kernel
    itself is the `.so` beside it. Hashing `module.__file__` would give the same
    digest for any two builds -- exactly what the hash exists to tell apart.
    """
    import importlib.machinery
    import sys
    suffixes = tuple(importlib.machinery.EXTENSION_SUFFIXES)
    name = module.__name__
    sub = sys.modules.get(name + '.' + name.rpartition('.')[2])
    for candidate in (sub, module):
        path = getattr(candidate, '__file__', None) or ''
        if path.endswith(suffixes):
            return path
    for entry in getattr(module, '__path__', None) or ():
        for fn in sorted(os.listdir(entry)):
            if fn.endswith(suffixes):
                return os.path.join(entry, fn)
    return getattr(module, '__file__', None)


def _backend_metadata(runner, module, requested):
    """Record which back end ran, and which binary it was.

    "native" is not a sufficient description of a measurement: the crate's
    version never changes between builds, so two result files can both say
    native and describe different compiled kernels.  The loaded path and its
    SHA-256 are what tie a JSON to the wheel that tools/build_wheel.sh
    installed.
    """
    runner.metadata['hwsw_backend'] = 'native' if module is not None else 'python'
    runner.metadata['hwsw_backend_requested'] = requested
    if module is not None:
        path = _native_extension_file(module)
        if path:
            runner.metadata['hwsw_native_module'] = path
            try:
                with open(path, 'rb') as fh:
                    runner.metadata['hwsw_native_sha256'] = \
                        hashlib.sha256(fh.read()).hexdigest()
            except OSError:                              # pragma: no cover
                pass


def _propagate_backend(runner):
    """Make the requested back end reach the worker processes.

    pyperf re-executes every worker with a scrubbed environment
    (``pyperf._utils.create_environ``), so ``HWSW_BACKEND`` is dropped unless
    the caller passed ``--inherit-environ HWSW_BACKEND``.  That was forgotten
    once: both sides of a "Python vs native" comparison measured native, and
    only the recorded metadata caught it.  Leaving the fix in the caller means
    every future caller has to remember it, and ``pyperformance run`` offers no
    way to pass the flag through to the benchmark at all -- so the benchmark
    propagates its own configuration here, and the flag on the command line
    becomes belt-and-braces rather than the only thing standing between a
    reader and a wrong number.
    """
    args = runner.parse_args()            # idempotent; returns the cached args
    inherit = list(getattr(args, 'inherit_environ', None) or [])
    if 'HWSW_BACKEND' not in inherit:
        inherit.append('HWSW_BACKEND')
    args.inherit_environ = inherit
    return args

if __name__ == '__main__':
    runner = pyperf.Runner(add_cmdline_args=add_cmdline_args)
    runner.metadata['description'] = "n-body benchmark"
    # so the result JSON says which back end produced it, and which binary
    _backend_metadata(runner, nbody_rs, _BACKEND)
    runner.argparser.add_argument("--iterations",
                                  type=int, default=DEFAULT_ITERATIONS,
                                  help="Number of nbody advance() iterations "
                                       "(default: %s)" % DEFAULT_ITERATIONS)
    runner.argparser.add_argument("--reference",
                                  type=str, default=DEFAULT_REFERENCE,
                                  help="nbody reference (default: %s)"
                                       % DEFAULT_REFERENCE)
    runner.argparser.add_argument("--bodies",
                                  type=int, default=DEFAULT_BODIES,
                                  help="Number of bodies to simulate; N > %s "
                                       "appends deterministic circular orbits "
                                       "(default: %s)"
                                       % (DEFAULT_BODIES, DEFAULT_BODIES))

    args = _propagate_backend(runner)   # parses; must follow every add_argument()
    # Outside the timed region: bench_time_func() times bench_nbody(), and the
    # source generation + compile() for the larger system happens here, once,
    # before the first loop.  It is measured separately by dev/nbody/sweep_n.py
    # because at large N it stops being negligible.
    _configure(args.bodies)
    runner.bench_time_func('nbody', bench_nbody,
                           args.reference, args.iterations)
