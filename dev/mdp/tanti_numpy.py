"""T-anti - numpy vectorisation of the sweep.  Measured as an ANTI-RESULT.

The obvious vectorisation of a CSR value-iteration sweep is

    contrib = lo[col] * prb
    sum_lo  = np.add.reduceat(contrib, row[:-1])        # chance nodes
    max_lo  = np.maximum.reduceat(lo[col], row[:-1])    # choice nodes

...and that is exactly the problem.  Those three lines read the WHOLE lo
vector as it stood at the start of the sweep, i.e. they implement **Jacobi**
iteration.  The stock solver is **Gauss-Seidel**: it sweeps in reverse
topological order and every node reads the values its successors were given
earlier in the same sweep.  That is the entire reason 111 sweeps suffice.

So numpy does not just change the constant factor, it changes the algorithm:

  * sweep count goes 111 -> 369 (measured, t4_algo.py order)
  * the result lands on a different bracket midpoint and FAILS the
    benchmark's own 1e-6 assertion
  * and at n = 4823 nodes / 22418 edges each vectorised sweep is only a few
    hundred microseconds of real work wrapped in ~15 numpy call overheads,
    so the per-sweep win is largely eaten by the 3.3x sweep inflation.

Kept in the ladder because "we tried the obvious numpy move and here is why
it is wrong" is a stronger slide than not having tried it.
"""
import time

import numpy as np

import t3_intexact as T3

TOLERANCE = 0.192
EXPECTED = 0.89873589887


class NPGraph(object):
    __slots__ = ('n', 'row', 'col', 'prb', 'lo', 'hi', 'live', 'ischance',
                 'ischoice', 'root', 'stateps')


def to_numpy(g):
    q = NPGraph()
    q.n = g.n
    q.row = np.asarray(g.row[:-1], dtype=np.intp)
    q.col = np.asarray(g.col, dtype=np.intp)
    q.prb = np.asarray(g.prb, dtype=np.float64)
    q.lo = np.asarray(g.lo, dtype=np.float64)
    q.hi = np.asarray(g.hi, dtype=np.float64)
    frz = np.frombuffer(bytes(g.frz), dtype=np.uint8).astype(bool)
    kind = np.frombuffer(bytes(g.kind), dtype=np.uint8).astype(bool)
    q.live = ~frz
    q.ischance = q.live & kind
    q.ischoice = q.live & ~kind
    q.root = g.root
    q.stateps = g.stateps
    return q


def sweep_numpy(q, tolerance=TOLERANCE, maxit=5000):
    row, col, prb = q.row, q.col, q.prb
    lo, hi = q.lo, q.hi
    live, ischance, ischoice = q.live, q.ischance, q.ischoice
    root = q.root

    it = 0
    while hi[root] - lo[root] > tolerance and it < maxit:
        it += 1
        glo = lo[col]
        ghi = hi[col]
        slo = np.add.reduceat(glo * prb, row)
        shi = np.add.reduceat(ghi * prb, row)
        mlo = np.maximum.reduceat(glo, row)
        mhi = np.maximum.reduceat(ghi, row)

        nlo = np.where(ischance, slo, mlo)
        nhi = np.where(ischance, shi, mhi)

        cross = live & (nlo >= nhi)
        mid = (nlo + nhi) * 0.5
        nlo = np.where(cross, mid, nlo)
        nhi = np.where(cross, mid, nhi)

        lo = np.where(live, nlo, lo)
        hi = np.where(live, nhi, hi)
        if cross.any():
            live = live & ~cross
            ischance = ischance & live
            ischoice = ischoice & live
    q.lo, q.hi = lo, hi
    return (hi[root] + lo[root]) / 2, it


def solve(tolerance=TOLERANCE):
    t0 = time.perf_counter()
    g = T3.build_csr()
    q = to_numpy(g)
    t1 = time.perf_counter()
    r, it = sweep_numpy(q, tolerance)
    t2 = time.perf_counter()
    return float(r), it, t1 - t0, t2 - t1


def solve_verbose(tolerance=TOLERANCE):
    g = T3.build_csr()
    q = to_numpy(g)
    r, it = sweep_numpy(q, tolerance)
    return float(r), it, q.lo, q.hi


def run(tolerance=TOLERANCE):
    return solve(tolerance)[0]


if __name__ == '__main__':
    r, n, tb, ti = solve()
    print("result=%.12f sweeps=%d build=%.3fs iter=%.3fs  oracle=%s"
          % (r, n, tb, ti, "PASS" if abs(r - EXPECTED) <= 1e-6 else "FAIL"))
