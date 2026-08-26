"""T1 -- micro-optimised stock kernel.  Same AoS layout, same loop shape.

Winner of the `t1_variants.py` shoot-out (variant G).  Three changes:

  1. **Velocity components read into locals, stored back with a plain
     assignment.**  This is the whole win (~1.13x measured, on its own).
     Stock writes `v1[0] -= dx * b2m`, which is BINARY_SUBSCR -> BINARY_OP ->
     STORE_SUBSCR: a read-modify-write through the list object for each of the
     six velocity components of every pair.  Unpacking `a1, c1, e1 = v1` once
     (one UNPACK_SEQUENCE) and writing `v1[0] = a1 - dx * b2m` removes six
     subscript *reads* per pair and turns six read-modify-writes into six
     plain stores.

  2. `dsq ** -1.5`  ->  `dt / (dsq * sqrt(dsq))` with `math.sqrt` bound to a
     function-local.  Same mathematical quantity by a cheaper route: the
     hardware SQRTSD instruction plus a multiply and a divide, instead of a
     libm `pow()` call.  Worth ~1-2% on 3.12 (pow is well optimised there);
     expected to be worth more on 3.10, where `BINARY_POWER` is unspecialised.
     NOT bit-identical -- rounding differs by ~2 ulp per step.

  3. PAIRS pre-flattened to 6-tuples (r1, v1, m1, r2, v2, m2), so the loop
     header is one flat UNPACK_SEQUENCE-6 instead of a nested destructuring of
     a tuple-of-(list, list, float) pairs.  Worth ~1%.

Note what is deliberately NOT here: replacing the position destructuring with
direct `r1[0] - r2[0]` indexing *loses* (0.94-1.01x) -- six BINARY_SUBSCRs
cost more than two UNPACK_SEQUENCE-3s.  See `t1_variants.py` variant B.
"""
from math import sqrt as _sqrt

from common import fresh_bodies, pair_indices, offset_momentum_aos

NAME = "T1 micro"


def make_state():
    bodies = fresh_bodies()
    offset_momentum_aos(bodies)
    pairs = [(bodies[i][0], bodies[i][1], bodies[i][2],
              bodies[j][0], bodies[j][1], bodies[j][2])
             for (i, j) in pair_indices(len(bodies))]
    return (bodies, pairs)


def advance(st, dt, n):
    bodies, pairs = st
    sqrt = _sqrt
    for _ in range(n):
        for r1, v1, m1, r2, v2, m2 in pairs:
            x1, y1, z1 = r1
            x2, y2, z2 = r2
            dx = x1 - x2
            dy = y1 - y2
            dz = z1 - z2
            dsq = dx * dx + dy * dy + dz * dz
            mag = dt / (dsq * sqrt(dsq))
            b1m = m1 * mag
            b2m = m2 * mag
            a1, c1, e1 = v1
            a2, c2, e2 = v2
            v1[0] = a1 - dx * b2m
            v1[1] = c1 - dy * b2m
            v1[2] = e1 - dz * b2m
            v2[0] = a2 + dx * b1m
            v2[1] = c2 + dy * b1m
            v2[2] = e2 + dz * b1m
        for (r, [vx, vy, vz], m) in bodies:
            r[0] += dt * vx
            r[1] += dt * vy
            r[2] += dt * vz


def energy(st):
    bodies, pairs = st
    sqrt = _sqrt
    e = 0.0
    for r1, v1, m1, r2, v2, m2 in pairs:
        dx = r1[0] - r2[0]
        dy = r1[1] - r2[1]
        dz = r1[2] - r2[2]
        e -= (m1 * m2) / sqrt(dx * dx + dy * dy + dz * dz)
    for r, (vx, vy, vz), m in bodies:
        e += m * (vx * vx + vy * vy + vz * vz) / 2.
    return e


def dump(st):
    bodies, _ = st
    out = []
    for (r, v, m) in bodies:
        out.extend(r)
        out.extend(v)
        out.append(m)
    return out
