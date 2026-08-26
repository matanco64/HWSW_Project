"""Code generator for a fully register-allocated `advance()`.

This is *partial evaluation*: the pair schedule (which bodies interact, in
which order) and the masses are compile-time constants of the problem, not
data that changes during the run.  We therefore emit, once at import time, a
straight-line function in which every position and velocity component is a
Python *local* (LOAD_FAST/STORE_FAST) and every mass is a *literal*
(LOAD_CONST).  The result contains ZERO list subscripts and ZERO iterator
protocol in the hot path; state is loaded into locals before the step loop
and written back after it.

Crucially the generator is generic in N -- `make_source()` takes the mass
vector and the pair list and works for any body count.  It is not "the answer
hardcoded"; it is the same schedule the stock loop walks at run time, walked
once at import time instead.

Two arithmetic modes:
  exact=True   emits `dt * (dsq ** -1.5)`, i.e. the identical FP operation
               sequence as stock  ->  bit-for-bit identical results.
  exact=False  emits `dt / (dsq * sqrt(dsq))`  ->  same quantity, cheaper
               route, ~2 ulp different rounding.
And an optional strength reduction:
  fold_mass=True  hoists `m_i * dt` out of the step loop, so the pair body
               does `rinv = 1.0 / (dsq*sqrt(dsq)); b1m = md_i * rinv`.
               Saves one multiply per pair; reassociates (m*dt)*r instead of
               m*(dt*r), so it is NOT bit-identical.
"""


def make_source(masses, pairs, exact=False, fold_mass=False, name="advance"):
    n = len(masses)
    out = []
    add = out.append

    add("def %s(st, dt, n):" % name)
    add("    bodies = st[0]")
    add("    sqrt = _sqrt")
    # --- load state into locals -------------------------------------------
    for i in range(n):
        add("    r%d = bodies[%d][0]; v%d = bodies[%d][1]" % (i, i, i, i))
    for i in range(n):
        add("    x%d = r%d[0]; y%d = r%d[1]; z%d = r%d[2]" % (i, i, i, i, i, i))
        add("    ux%d = v%d[0]; uy%d = v%d[1]; uz%d = v%d[2]"
            % (i, i, i, i, i, i))
    if fold_mass:
        for i in range(n):
            add("    md%d = %r * dt" % (i, masses[i]))
    # --- the step loop -----------------------------------------------------
    add("    for _ in range(n):")
    for (i, j) in pairs:
        add("        dx = x%d - x%d" % (i, j))
        add("        dy = y%d - y%d" % (i, j))
        add("        dz = z%d - z%d" % (i, j))
        add("        dsq = dx * dx + dy * dy + dz * dz")
        if exact:
            add("        mag = dt * (dsq ** (-1.5))")
        elif fold_mass:
            add("        mag = 1.0 / (dsq * sqrt(dsq))")
        else:
            add("        mag = dt / (dsq * sqrt(dsq))")
        if fold_mass:
            add("        b1m = md%d * mag" % i)
            add("        b2m = md%d * mag" % j)
        else:
            add("        b1m = %r * mag" % masses[i])
            add("        b2m = %r * mag" % masses[j])
        add("        ux%d -= dx * b2m" % i)
        add("        uy%d -= dy * b2m" % i)
        add("        uz%d -= dz * b2m" % i)
        add("        ux%d += dx * b1m" % j)
        add("        uy%d += dy * b1m" % j)
        add("        uz%d += dz * b1m" % j)
    for i in range(n):
        add("        x%d += dt * ux%d" % (i, i))
        add("        y%d += dt * uy%d" % (i, i))
        add("        z%d += dt * uz%d" % (i, i))
    # --- write state back --------------------------------------------------
    for i in range(n):
        add("    r%d[0] = x%d; r%d[1] = y%d; r%d[2] = z%d"
            % (i, i, i, i, i, i))
        add("    v%d[0] = ux%d; v%d[1] = uy%d; v%d[2] = uz%d"
            % (i, i, i, i, i, i))
    return "\n".join(out) + "\n"


def build(masses, pairs, exact=False, fold_mass=False, name="advance"):
    """exec() the generated source and return the function object."""
    from math import sqrt
    src = make_source(masses, pairs, exact=exact, fold_mass=fold_mass,
                      name=name)
    ns = {"_sqrt": sqrt}
    exec(compile(src, "<nbody-unrolled>", "exec"), ns)
    fn = ns[name]
    fn.__source__ = src
    return fn


if __name__ == "__main__":
    import sys
    from common import BODIES, pair_indices
    masses = [b[2] for b in BODIES.values()]
    src = make_source(masses, pair_indices(len(masses)),
                      exact="--exact" in sys.argv,
                      fold_mass="--fold" in sys.argv)
    sys.stdout.write(src)
