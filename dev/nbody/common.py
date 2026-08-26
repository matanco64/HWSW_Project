"""Shared initial state + canonical state dump for every nbody tier.

Every tier module exposes the same tiny protocol so `verify.py` and `bench.py`
can drive them uniformly:

    make_state()          -> opaque per-tier state object
    advance(st, dt, n)    -> mutate state in place, n symplectic-Euler steps
    energy(st)            -> float, total energy (== stock report_energy())
    dump(st)              -> list[float], 35 values in canonical order
                             body-major: x, y, z, vx, vy, vz, m

Canonical body order is the stock `list(BODIES.values())` order:
    sun, jupiter, saturn, uranus, neptune
Canonical pair order is stock `combinations()`:
    (0,1) (0,2) (0,3) (0,4) (1,2) (1,3) (1,4) (2,3) (2,4) (3,4)
"""

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

NAMES = list(BODIES)
REFERENCE = 'sun'


def fresh_bodies():
    """A brand new AoS body list: [ [pos3], [vel3], mass ] per body."""
    return [[list(r), list(v), m] for (r, v, m) in BODIES.values()]


def pair_indices(n):
    """Stock combinations() order, as (i, j) index pairs."""
    out = []
    for x in range(n - 1):
        for y in range(x + 1, n):
            out.append((x, y))
    return out


def offset_momentum_aos(bodies, ref_index=0):
    """Stock offset_momentum(), operating on the AoS body list."""
    px = py = pz = 0.0
    for (r, [vx, vy, vz], m) in bodies:
        px -= vx * m
        py -= vy * m
        pz -= vz * m
    (r, v, m) = bodies[ref_index]
    v[0] = px / m
    v[1] = py / m
    v[2] = pz / m
