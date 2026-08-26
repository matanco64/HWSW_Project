"""T-anti -- NumPy vectorisation at N=5.  The expected anti-result.

Two honest variants:

  pairs : keep the 10-pair Newton's-third-law formulation and vectorise it.
          Needs scatter-accumulate (`np.subtract.at`) because a body appears
          in 4 pairs; ufunc.at is the slowest path in NumPy.

  nxn   : the branch-free all-pairs broadcast, (5,5,3) difference tensor.
          No scatter, but 25 pair evaluations instead of 10 and a bunch of
          temporary (5,5,3) allocations.

Both pay ~5-15 NumPy C-call dispatches (each ~0.5-2 us of arg parsing,
broadcasting setup and temporary allocation) to do 10 pairs of arithmetic
that pure Python does in ~200 bytecodes.  Vectorisation amortises fixed
per-call cost over array length; at length 5-25 there is nothing to amortise.
The crossover is measured in `crossover.py`.
"""
import numpy as np

from common import fresh_bodies, pair_indices, offset_momentum_aos

NAME = "T-anti numpy"


def _base():
    bodies = fresh_bodies()
    offset_momentum_aos(bodies)
    pos = np.array([b[0] for b in bodies], dtype=np.float64)
    vel = np.array([b[1] for b in bodies], dtype=np.float64)
    m = np.array([b[2] for b in bodies], dtype=np.float64)
    return pos, vel, m


def make_state():
    pos, vel, m = _base()
    pi = pair_indices(len(m))
    I = np.array([i for i, _ in pi])
    J = np.array([j for _, j in pi])
    return [pos, vel, m, I, J, m[I].copy(), m[J].copy()]


def advance(st, dt, n):
    pos, vel, m, I, J, mI, mJ = st
    sub_at = np.subtract.at
    add_at = np.add.at
    for _ in range(n):
        d = pos[I] - pos[J]
        dsq = np.einsum('ij,ij->i', d, d)
        mag = dt / (dsq * np.sqrt(dsq))
        sub_at(vel, I, d * (mJ * mag)[:, None])
        add_at(vel, J, d * (mI * mag)[:, None])
        pos += dt * vel


def make_state_nxn():
    pos, vel, m = _base()
    n = len(m)
    eye = np.eye(n, dtype=bool)
    return [pos, vel, m, eye]


def advance_nxn(st, dt, n):
    pos, vel, m, eye = st
    for _ in range(n):
        d = pos[:, None, :] - pos[None, :, :]
        dsq = np.einsum('ijk,ijk->ij', d, d)
        dsq[eye] = 1.0
        w = (dt * m[None, :]) / (dsq * np.sqrt(dsq))
        w[eye] = 0.0
        vel -= np.einsum('ijk,ij->ik', d, w)
        pos += dt * vel


def energy(st):
    pos, vel, m = st[0], st[1], st[2]
    n = len(m)
    e = 0.0
    for i in range(n - 1):
        for j in range(i + 1, n):
            d = pos[i] - pos[j]
            e -= (m[i] * m[j]) / float(np.sqrt(d @ d))
    e += float(0.5 * (m * np.einsum('ij,ij->i', vel, vel)).sum())
    return e


def dump(st):
    pos, vel, m = st[0], st[1], st[2]
    out = []
    for i in range(len(m)):
        out.extend(float(v) for v in pos[i])
        out.extend(float(v) for v in vel[i])
        out.append(float(m[i]))
    return out
