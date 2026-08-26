"""Direct O(N^2) summation vs Barnes-Hut O(N log N): where is the crossover?

The proposal under evaluation was to replace the benchmark's all-pairs force
loop with the Fast Multipole Method.  FMM and Barnes-Hut both beat direct
summation asymptotically, and both carry a large constant: they must build a
spatial tree every step (bodies move), compute cell aggregates bottom-up,
then walk the tree per body with an opening criterion.

Barnes-Hut is the *cheaper* of the two -- it aggregates a cell into a single
monopole (mass + centre of mass), whereas FMM carries a p-term multipole
expansion per cell plus M2M / M2L / L2L translation operators.  So Barnes-Hut
is a strict LOWER BOUND on FMM's constant factor: whatever N Barnes-Hut needs
to break even, FMM needs more.

This script measures, for N = 5 ... 5000 in 3D:
  * time per force evaluation, direct all-pairs, using Newton's third law so
    that only N(N-1)/2 pair evaluations happen -- the same form the benchmark
    itself uses;
  * time per force evaluation, Barnes-Hut, INCLUDING the per-step tree build,
    because the tree is invalid as soon as the bodies move;
  * the accuracy Barnes-Hut costs, as max relative acceleration error against
    the direct result.

Both implementations are plain CPython in the same style, so this is an
algorithmic crossover measurement, not an implementation-quality contest.

    python crossover.py [--theta 0.5] [--repeat 3] [--max-n 5000]
"""
import argparse
import gc
import math
import random
import sys
import time

import hygiene

SIZES = (5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 200, 500,
         1000, 2000, 5000)


# --------------------------------------------------------------------------
# bodies
# --------------------------------------------------------------------------
def make_bodies(n, seed=12345):
    """A clustered blob inside the unit sphere, favourable to the tree."""
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        r = rnd.random() ** (1.0 / 3.0)
        ct = 2.0 * rnd.random() - 1.0
        st = math.sqrt(max(0.0, 1.0 - ct * ct))
        ph = 2.0 * math.pi * rnd.random()
        out.append((r * st * math.cos(ph), r * st * math.sin(ph), r * ct,
                    1.0 / n))
    return out


# --------------------------------------------------------------------------
# direct O(N^2)
# --------------------------------------------------------------------------
def accel_direct(bodies):
    n = len(bodies)
    ax = [0.0] * n
    ay = [0.0] * n
    az = [0.0] * n
    sqrt = math.sqrt
    for i in range(n - 1):
        xi, yi, zi, mi = bodies[i]
        for j in range(i + 1, n):
            xj, yj, zj, mj = bodies[j]
            dx = xi - xj
            dy = yi - yj
            dz = zi - zj
            dsq = dx * dx + dy * dy + dz * dz + 1e-9
            inv = 1.0 / (dsq * sqrt(dsq))
            wi = mj * inv
            wj = mi * inv
            ax[i] -= dx * wi
            ay[i] -= dy * wi
            az[i] -= dz * wi
            ax[j] += dx * wj
            ay[j] += dy * wj
            az[j] += dz * wj
    return ax, ay, az


# --------------------------------------------------------------------------
# Barnes-Hut octree
# --------------------------------------------------------------------------
# node = [mass, comx, comy, comz, half_size, children|None, leaf_body|None]
M, CX, CY, CZ, HS, CH, LEAF = range(7)


def _octant(x, y, z, cx, cy, cz):
    return (1 if x > cx else 0) | (2 if y > cy else 0) | (4 if z > cz else 0)


def _child(node, body, half, depth):
    o = _octant(body[0], body[1], body[2], node[CX], node[CY], node[CZ])
    h = half * 0.5
    kid = node[CH][o]
    if kid is None:
        kid = node[CH][o] = [
            0.0,
            node[CX] + (h if o & 1 else -h),
            node[CY] + (h if o & 2 else -h),
            node[CZ] + (h if o & 4 else -h),
            h, None, None]
    return kid, h, depth + 1


def build_tree(bodies):
    xs = [b[0] for b in bodies]
    ys = [b[1] for b in bodies]
    zs = [b[2] for b in bodies]
    half = max(max(xs) - min(xs), max(ys) - min(ys),
               max(zs) - min(zs)) * 0.5 + 1e-12
    root = [0.0, (min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5,
            (min(zs) + max(zs)) * 0.5, half, None, None]
    for b in bodies:
        node, half_n, depth = root, half, 0
        while True:
            if node[CH] is None:
                if node[LEAF] is None:
                    node[LEAF] = b
                    break
                if depth > 48:              # coincident / near-coincident
                    node[LEAF] = b          # give up splitting; drop old one
                    break
                old = node[LEAF]
                node[LEAF] = None
                node[CH] = [None] * 8
                kid, h, d = _child(node, old, half_n, depth)
                kid[LEAF] = old
            node, half_n, depth = _child(node, b, half_n, depth)
    _aggregate(root)
    return root


def _aggregate(node):
    if node[CH] is None:
        b = node[LEAF]
        if b is None:
            return 0.0
        node[M] = b[3]
        node[CX], node[CY], node[CZ] = b[0], b[1], b[2]
        return b[3]
    mt = sx = sy = sz = 0.0
    for kid in node[CH]:
        if kid is None:
            continue
        m = _aggregate(kid)
        if m:
            mt += m
            sx += kid[CX] * m
            sy += kid[CY] * m
            sz += kid[CZ] * m
    node[M] = mt
    if mt:
        node[CX], node[CY], node[CZ] = sx / mt, sy / mt, sz / mt
    return mt


def accel_bh(bodies, theta):
    root = build_tree(bodies)
    inv_theta_sq = 1.0 / (theta * theta)
    sqrt = math.sqrt
    n = len(bodies)
    ax = [0.0] * n
    ay = [0.0] * n
    az = [0.0] * n
    for i in range(n):
        xi, yi, zi, _mi = bodies[i]
        gx = gy = gz = 0.0
        stack = [root]
        pop = stack.pop
        push = stack.append
        while stack:
            node = pop()
            m = node[M]
            if not m:
                continue
            dx = node[CX] - xi
            dy = node[CY] - yi
            dz = node[CZ] - zi
            dsq = dx * dx + dy * dy + dz * dz
            if node[CH] is None:
                if dsq < 1e-18:                     # self-interaction
                    continue
                dsq += 1e-9
                w = m / (dsq * sqrt(dsq))
                gx += dx * w
                gy += dy * w
                gz += dz * w
                continue
            size = node[HS] + node[HS]
            # accept the cell as a single monopole iff s/d < theta, i.e.
            # s^2 < theta^2 d^2, i.e. d^2 > s^2 / theta^2
            if dsq > size * size * inv_theta_sq:
                dsq += 1e-9
                w = m / (dsq * sqrt(dsq))
                gx += dx * w
                gy += dy * w
                gz += dz * w
            else:
                for kid in node[CH]:
                    if kid is not None:
                        push(kid)
        ax[i] = gx
        ay[i] = gy
        az[i] = gz
    return ax, ay, az


# --------------------------------------------------------------------------
def acc_err(a, b):
    """(median componentwise rel err, max |da| / rms|a|).

    Plain max-relative-error is misleading in a uniform blob: an interior body
    sits near the centre of a nearly isotropic mass distribution, its net
    acceleration nearly cancels to zero, and *any* absolute error divided by
    that near-zero norm explodes.  We therefore report the median relative
    error (typical accuracy) and the max error normalised by the RMS
    acceleration of the system (worst-case error at system scale)."""
    ax, ay, az = a
    bx, by, bz = b
    n = len(ax)
    rel = []
    worst_abs = 0.0
    sq = 0.0
    for i in range(n):
        na = math.sqrt(ax[i] * ax[i] + ay[i] * ay[i] + az[i] * az[i])
        d = math.sqrt((ax[i] - bx[i]) ** 2 + (ay[i] - by[i]) ** 2
                      + (az[i] - bz[i]) ** 2)
        sq += na * na
        worst_abs = max(worst_abs, d)
        if na:
            rel.append(d / na)
    rel.sort()
    med = rel[len(rel) // 2] if rel else 0.0
    rms = math.sqrt(sq / n) if n else 0.0
    return med, (worst_abs / rms if rms else 0.0)


def timeit(fn, repeat):
    best = float("inf")
    res = None
    for _ in range(repeat):
        gc.collect()
        gc.disable()
        t0 = time.perf_counter()
        res = fn()
        t1 = time.perf_counter()
        gc.enable()
        best = min(best, t1 - t0)
    return best, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--theta", type=float, default=0.5)
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--max-n", type=int, default=5000)
    a = ap.parse_args()

    print("hygiene: %s" % hygiene.tune())
    print("python %s | 3D | Barnes-Hut theta=%.2f | best-of-%d | tree rebuilt "
          "every evaluation" % (sys.version.split()[0], a.theta, a.repeat))
    print()
    print("%7s %13s %13s %11s %14s %11s %11s"
          % ("N", "direct ms", "barnes-hut ms", "BH/direct", "pairs N(N-1)/2",
             "med rel err", "max/rms"))
    for n in SIZES:
        if n > a.max_n:
            break
        bodies = make_bodies(n)
        root = build_tree(bodies)
        got, want = root[M], sum(b[3] for b in bodies)
        assert abs(got - want) < 1e-12 * max(1.0, want), (
            "tree lost mass at N=%d: %r vs %r" % (n, got, want))
        td, rd = timeit(lambda: accel_direct(bodies), a.repeat)
        tb, rb = timeit(lambda: accel_bh(bodies, a.theta), a.repeat)
        med, mx = acc_err(rd, rb)
        print("%7d %13.4f %13.4f %11.2f %14d %11.2e %11.2e"
              % (n, td * 1e3, tb * 1e3, tb / td, n * (n - 1) // 2, med, mx))


if __name__ == "__main__":
    main()
