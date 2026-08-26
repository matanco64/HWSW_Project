"""T2 -- struct-of-arrays (SoA) layout.

Body state lives in six flat float lists (x, y, z, vx, vy, vz) plus a mass
tuple; the pair table is a list of (i, j) integer index tuples.  This is the
textbook AoS->SoA transform, and on a compiled language it is the right move
(contiguous f64 lanes, SIMD-friendly).

In CPython it is expected to LOSE, because a Python list subscript is not a
pointer add: `x[i]` is BINARY_SUBSCR -> PyObject_GetItem -> list_item, and
`vx[i] -= t` is a full get/compute/set round trip.  The stock AoS layout
already hands the loop body two *direct* velocity-list locals (v1, v2), so
SoA strictly adds indexing work.  Measured, this is an instructive
anti-result that pairs with the NumPy one.
"""
from math import sqrt as _sqrt

from common import fresh_bodies, pair_indices, offset_momentum_aos

NAME = "T2 SoA"


def make_state():
    bodies = fresh_bodies()
    offset_momentum_aos(bodies)
    n = len(bodies)
    x = [b[0][0] for b in bodies]
    y = [b[0][1] for b in bodies]
    z = [b[0][2] for b in bodies]
    vx = [b[1][0] for b in bodies]
    vy = [b[1][1] for b in bodies]
    vz = [b[1][2] for b in bodies]
    m = [b[2] for b in bodies]
    return [x, y, z, vx, vy, vz, m, pair_indices(n), list(range(n))]


def advance(st, dt, n):
    x, y, z, vx, vy, vz, m, pairs, idx = st
    sqrt = _sqrt
    for _ in range(n):
        for i, j in pairs:
            dx = x[i] - x[j]
            dy = y[i] - y[j]
            dz = z[i] - z[j]
            dsq = dx * dx + dy * dy + dz * dz
            mag = dt / (dsq * sqrt(dsq))
            b1m = m[i] * mag
            b2m = m[j] * mag
            vx[i] -= dx * b2m
            vy[i] -= dy * b2m
            vz[i] -= dz * b2m
            vx[j] += dx * b1m
            vy[j] += dy * b1m
            vz[j] += dz * b1m
        for i in idx:
            x[i] += dt * vx[i]
            y[i] += dt * vy[i]
            z[i] += dt * vz[i]


def energy(st):
    x, y, z, vx, vy, vz, m, pairs, idx = st
    sqrt = _sqrt
    e = 0.0
    for i, j in pairs:
        dx = x[i] - x[j]
        dy = y[i] - y[j]
        dz = z[i] - z[j]
        e -= (m[i] * m[j]) / sqrt(dx * dx + dy * dy + dz * dz)
    for i in idx:
        e += m[i] * (vx[i] * vx[i] + vy[i] * vy[i] + vz[i] * vz[i]) / 2.
    return e


def dump(st):
    x, y, z, vx, vy, vz, m, pairs, idx = st
    out = []
    for i in idx:
        out.extend((x[i], y[i], z[i], vx[i], vy[i], vz[i], m[i]))
    return out
