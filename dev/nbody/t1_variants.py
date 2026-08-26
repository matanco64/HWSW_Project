"""Shoot-out of candidate T1 micro-optimisations, interleaved round-robin.

The received wisdom for this benchmark ("index p1[0]-p2[0] directly instead of
destructuring") turns out to be WRONG on CPython: the stock nested
`for (([x1,y1,z1], v1, m1), ([x2,y2,z2], v2, m2)) in pairs:` header costs two
UNPACK_SEQUENCE-3 per pair, whereas direct indexing costs six BINARY_SUBSCR.
This file measures it rather than guessing.

    python t1_variants.py [--steps 20000] [--rounds 9]
"""
import argparse
import gc
import statistics
import time
from math import sqrt as _sqrt

from common import fresh_bodies, pair_indices, offset_momentum_aos


def mk_nested():
    b = fresh_bodies()
    offset_momentum_aos(b)
    return b, [(b[i], b[j]) for i, j in pair_indices(len(b))]


def mk_flat():
    b = fresh_bodies()
    offset_momentum_aos(b)
    return b, [(b[i][0], b[i][1], b[i][2], b[j][0], b[j][1], b[j][2])
               for i, j in pair_indices(len(b))]


def adv_stock(st, dt, n):
    bodies, pairs = st
    for i in range(n):
        for (([x1, y1, z1], v1, m1), ([x2, y2, z2], v2, m2)) in pairs:
            dx = x1 - x2; dy = y1 - y2; dz = z1 - z2
            mag = dt * ((dx * dx + dy * dy + dz * dz) ** (-1.5))
            b1m = m1 * mag; b2m = m2 * mag
            v1[0] -= dx * b2m; v1[1] -= dy * b2m; v1[2] -= dz * b2m
            v2[0] += dx * b1m; v2[1] += dy * b1m; v2[2] += dz * b1m
        for (r, [vx, vy, vz], m) in bodies:
            r[0] += dt * vx; r[1] += dt * vy; r[2] += dt * vz


def adv_sqrt(st, dt, n):
    """A: stock shape; only pow -> sqrt, with math.sqrt bound to a local."""
    bodies, pairs = st
    sqrt = _sqrt
    for _ in range(n):
        for (([x1, y1, z1], v1, m1), ([x2, y2, z2], v2, m2)) in pairs:
            dx = x1 - x2; dy = y1 - y2; dz = z1 - z2
            dsq = dx * dx + dy * dy + dz * dz
            mag = dt / (dsq * sqrt(dsq))
            b1m = m1 * mag; b2m = m2 * mag
            v1[0] -= dx * b2m; v1[1] -= dy * b2m; v1[2] -= dz * b2m
            v2[0] += dx * b1m; v2[1] += dy * b1m; v2[2] += dz * b1m
        for (r, [vx, vy, vz], m) in bodies:
            r[0] += dt * vx; r[1] += dt * vy; r[2] += dt * vz


def adv_idx(st, dt, n):
    """B: flat 6-tuple pairs, positions read by direct subscript."""
    bodies, pairs = st
    sqrt = _sqrt
    for _ in range(n):
        for r1, v1, m1, r2, v2, m2 in pairs:
            dx = r1[0] - r2[0]; dy = r1[1] - r2[1]; dz = r1[2] - r2[2]
            dsq = dx * dx + dy * dy + dz * dz
            mag = dt / (dsq * sqrt(dsq))
            b1m = m1 * mag; b2m = m2 * mag
            v1[0] -= dx * b2m; v1[1] -= dy * b2m; v1[2] -= dz * b2m
            v2[0] += dx * b1m; v2[1] += dy * b1m; v2[2] += dz * b1m
        for r, v, m in bodies:
            r[0] += dt * v[0]; r[1] += dt * v[1]; r[2] += dt * v[2]


def adv_flatunpack(st, dt, n):
    """C: flat 6-tuple pairs, positions unpacked with UNPACK_SEQUENCE."""
    bodies, pairs = st
    sqrt = _sqrt
    for _ in range(n):
        for r1, v1, m1, r2, v2, m2 in pairs:
            x1, y1, z1 = r1
            x2, y2, z2 = r2
            dx = x1 - x2; dy = y1 - y2; dz = z1 - z2
            dsq = dx * dx + dy * dy + dz * dz
            mag = dt / (dsq * sqrt(dsq))
            b1m = m1 * mag; b2m = m2 * mag
            v1[0] -= dx * b2m; v1[1] -= dy * b2m; v1[2] -= dz * b2m
            v2[0] += dx * b1m; v2[1] += dy * b1m; v2[2] += dz * b1m
        for (r, [vx, vy, vz], m) in bodies:
            r[0] += dt * vx; r[1] += dt * vy; r[2] += dt * vz


def adv_vellocals(st, dt, n):
    """D: also unpack the two velocity lists, store back with plain assign."""
    bodies, pairs = st
    sqrt = _sqrt
    for _ in range(n):
        for (([x1, y1, z1], v1, m1), ([x2, y2, z2], v2, m2)) in pairs:
            dx = x1 - x2; dy = y1 - y2; dz = z1 - z2
            dsq = dx * dx + dy * dy + dz * dz
            mag = dt / (dsq * sqrt(dsq))
            b1m = m1 * mag; b2m = m2 * mag
            a1, c1, e1 = v1
            a2, c2, e2 = v2
            v1[0] = a1 - dx * b2m; v1[1] = c1 - dy * b2m; v1[2] = e1 - dz * b2m
            v2[0] = a2 + dx * b1m; v2[1] = c2 + dy * b1m; v2[2] = e2 + dz * b1m
        for (r, [vx, vy, vz], m) in bodies:
            r[0] += dt * vx; r[1] += dt * vy; r[2] += dt * vz


def adv_powonly(st, dt, n):
    """E: stock arithmetic (pow kept), only `for _ in range(n)`."""
    bodies, pairs = st
    for _ in range(n):
        for (([x1, y1, z1], v1, m1), ([x2, y2, z2], v2, m2)) in pairs:
            dx = x1 - x2; dy = y1 - y2; dz = z1 - z2
            mag = dt * ((dx * dx + dy * dy + dz * dz) ** (-1.5))
            b1m = m1 * mag; b2m = m2 * mag
            v1[0] -= dx * b2m; v1[1] -= dy * b2m; v1[2] -= dz * b2m
            v2[0] += dx * b1m; v2[1] += dy * b1m; v2[2] += dz * b1m
        for (r, [vx, vy, vz], m) in bodies:
            r[0] += dt * vx; r[1] += dt * vy; r[2] += dt * vz


def adv_vellocals_pow(st, dt, n):
    """F: variant D but keeping stock's `** -1.5` -- isolates the store-back
    change from the pow->sqrt change."""
    bodies, pairs = st
    for _ in range(n):
        for (([x1, y1, z1], v1, m1), ([x2, y2, z2], v2, m2)) in pairs:
            dx = x1 - x2; dy = y1 - y2; dz = z1 - z2
            mag = dt * ((dx * dx + dy * dy + dz * dz) ** (-1.5))
            b1m = m1 * mag; b2m = m2 * mag
            a1, c1, e1 = v1
            a2, c2, e2 = v2
            v1[0] = a1 - dx * b2m; v1[1] = c1 - dy * b2m; v1[2] = e1 - dz * b2m
            v2[0] = a2 + dx * b1m; v2[1] = c2 + dy * b1m; v2[2] = e2 + dz * b1m
        for (r, [vx, vy, vz], m) in bodies:
            r[0] += dt * vx; r[1] += dt * vy; r[2] += dt * vz


def adv_vellocals_flat(st, dt, n):
    """G: variant D on flat 6-tuple pairs (positions unpacked in the body)."""
    bodies, pairs = st
    sqrt = _sqrt
    for _ in range(n):
        for r1, v1, m1, r2, v2, m2 in pairs:
            x1, y1, z1 = r1
            x2, y2, z2 = r2
            dx = x1 - x2; dy = y1 - y2; dz = z1 - z2
            dsq = dx * dx + dy * dy + dz * dz
            mag = dt / (dsq * sqrt(dsq))
            b1m = m1 * mag; b2m = m2 * mag
            a1, c1, e1 = v1
            a2, c2, e2 = v2
            v1[0] = a1 - dx * b2m; v1[1] = c1 - dy * b2m; v1[2] = e1 - dz * b2m
            v2[0] = a2 + dx * b1m; v2[1] = c2 + dy * b1m; v2[2] = e2 + dz * b1m
        for (r, [vx, vy, vz], m) in bodies:
            r[0] += dt * vx; r[1] += dt * vy; r[2] += dt * vz


VARIANTS = [
    ("stock", mk_nested, adv_stock),
    ("A pow->sqrt", mk_nested, adv_sqrt),
    ("B flat+subscript", mk_flat, adv_idx),
    ("C flat+unpack", mk_flat, adv_flatunpack),
    ("D vel-locals", mk_nested, adv_vellocals),
    ("E for_ only (control)", mk_nested, adv_powonly),
    ("F vel-locals, pow", mk_nested, adv_vellocals_pow),
    ("G vel-locals, flat", mk_flat, adv_vellocals_flat),
]


def round_robin(variants, steps, rounds, label="variant"):
    """Interleave rounds so slow drift/thermal effects hit every entry alike."""
    res = {n: [] for n, _, _ in variants}
    for _ in range(rounds):
        for name, mk, adv in variants:
            st = mk()
            gc.collect()
            gc.disable()
            t0 = time.perf_counter()
            adv(st, 0.01, steps)
            t1 = time.perf_counter()
            gc.enable()
            res[name].append(t1 - t0)
    base = min(res[variants[0][0]])
    print("%-20s %9s %9s %9s" % (label, "best ms", "med ms", "speedup"))
    for name, _, _ in variants:
        v = res[name]
        print("%-20s %9.2f %9.2f %8.3fx"
              % (name, min(v) * 1e3, statistics.median(v) * 1e3, base / min(v)))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=20000)
    ap.add_argument("--rounds", type=int, default=31)
    a = ap.parse_args()
    import hygiene
    print("hygiene:", hygiene.tune())
    round_robin(VARIANTS, a.steps, a.rounds)
