"""T2 - integer state renumbering + CSR flat arrays for the sweep.

Build phase is T1's (memoized getCritDist).  After topoSort we renumber every
statep to a dense integer 0..n-1 *in the stock topological order* and flatten
the successor lists into classic CSR:

    kind[i]        u8   0 = choice (max) node, 1 = chance (expectation) node
    row[i]..row[i+1]    slice of col[]/prb[] belonging to node i
    col[j]         i32  successor index
    prb[j]         f64  edge probability (unused for choice nodes)
    lo[i], hi[i]   f64  the dmin / dmax interval
    frz[i]         u8   frozen flag

This is exactly the layout the Rust kernel and the proposed hardware
accelerator consume -- see ../../rust/mdp/ and the HW proposal.

Why it is a pure constant-factor win, not an algorithmic one: every node is
still visited in the same order every sweep, every edge is still multiplied
and accumulated in the same left-to-right order, the freeze rule is
unchanged.  What disappears is CPython overhead:

  * 784k deep-namedtuple hashes per run (dict[statep] -> list[int] indexing)
  * 521k generator-expression frames for sum() and 312k for max()
  * the defaultdict lookups on every read of a successor's bound

Result and sweep count are bit-identical to stock.
"""
import time
from operator import itemgetter, mul

import t1_micro as B

TOLERANCE = 0.192
EXPECTED = 0.89873589887

CHOICE = 0
CHANCE = 1


class CSR(object):
    """Flat, index-addressed form of the state graph."""

    __slots__ = ('n', 'kind', 'row', 'col', 'prb', 'lo', 'hi', 'frz',
                 'root', 'order', 'stateps')

    def export(self):
        """The exact tuple handed to the Rust kernel / DMA'd by the HW unit."""
        return (self.n, bytes(self.kind), self.row, self.col, self.prb,
                self.lo, self.hi, bytes(self.frz), self.root)


def build_csr():
    """Build the graph (stock semantics) and flatten it.  Returns a CSR."""
    b = B.Battle()
    root = b.initial()
    stateps = B.topoSort([root], b.getSuccessorsList)
    succs = b.successors

    n = len(stateps)
    idx = {}
    for i, sp in enumerate(stateps):
        idx[sp] = i

    g = CSR()
    g.n = n
    g.stateps = stateps
    g.root = idx[root]
    g.kind = bytearray(n)
    g.row = [0] * (n + 1)
    g.lo = [0.0] * n
    g.hi = [1.0] * n
    g.frz = bytearray(n)
    col = []
    prb = []

    for i, sp in enumerate(stateps):
        st = sp[0]
        if st == 4:
            # terminal: win == (4, True) -> [1,1]; loss == (4, False) -> [0,0]
            if sp[1]:
                g.lo[i] = 1.0
                g.hi[i] = 1.0
            else:
                g.lo[i] = 0.0
                g.hi[i] = 0.0
            g.frz[i] = 1
        elif st == 0:
            g.kind[i] = CHOICE
            for sp2 in succs[sp]:
                col.append(idx[sp2])
                prb.append(0.0)
        else:
            g.kind[i] = CHANCE
            for sp2, p in succs[sp]:
                col.append(idx[sp2])
                prb.append(p)
        g.row[i + 1] = len(col)

    g.col = col
    g.prb = prb
    # sweep order == stock order == 0,1,...,n-1 minus the frozen terminals
    g.order = [i for i in range(n) if not g.frz[i]]
    return g


def sweep_flat(g, tolerance=TOLERANCE):
    """Reference CSR sweep: explicit index loops over the flat arrays.

    This is the literal software twin of the hardware datapath."""
    kind, row, col, prb = g.kind, g.row, g.col, g.prb
    lo, hi, frz = g.lo, g.hi, g.frz
    root = g.root
    order = g.order

    it = 0
    while hi[root] - lo[root] > tolerance:
        it += 1
        newly = False
        for i in order:
            s = row[i]
            e = row[i + 1]
            if kind[i]:
                a = 0.0
                c = 0.0
                for j in range(s, e):
                    k = col[j]
                    p = prb[j]
                    a += lo[k] * p
                    c += hi[k] * p
            else:
                k = col[s]
                a = lo[k]
                c = hi[k]
                for j in range(s + 1, e):
                    k = col[j]
                    v = lo[k]
                    if v > a:
                        a = v
                    v = hi[k]
                    if v > c:
                        c = v
            if a >= c:
                a = c = (a + c) / 2
                frz[i] = 1
                newly = True
            lo[i] = a
            hi[i] = c
        if newly:
            order = [i for i in order if not frz[i]]
    return (hi[root] + lo[root]) / 2, it


def _views(g):
    """Per-node C-level gather views, built from the same CSR arrays and kept
    in the stock topological order so the Gauss-Seidel trajectory is exact.

    op 0 = choice (max over 2), 1 = chance with out-degree > 1,
    op 2 = chance with out-degree 1 (931 of them -- worth its own branch)."""
    work = []
    for i in g.order:
        s, e = g.row[i], g.row[i + 1]
        cols = g.col[s:e]
        if not g.kind[i]:
            work.append((0, i, itemgetter(*cols), None))
        elif e - s > 1:
            work.append((1, i, itemgetter(*cols), tuple(g.prb[s:e])))
        else:
            work.append((2, i, cols[0], g.prb[s]))
    return work


def sweep_gather(g, tolerance=TOLERANCE):
    """Same arithmetic, but the per-node gather runs in C.

    itemgetter(*cols)(lo) materialises the successor bounds as a tuple with a
    single C call; sum(map(mul, vals, probs)) then accumulates left-to-right
    exactly as sum(lo[s] * p for s, p in succ) did.  Bit-identical."""
    lo, hi, frz = g.lo, g.hi, g.frz
    root = g.root
    work = _views(g)

    it = 0
    while hi[root] - lo[root] > tolerance:
        it += 1
        newly = False
        for op, i, get, probs in work:
            if op == 1:
                a = sum(map(mul, get(lo), probs))
                c = sum(map(mul, get(hi), probs))
            elif op == 2:
                a = lo[get] * probs
                c = hi[get] * probs
            else:
                a = max(get(lo))
                c = max(get(hi))
            if a >= c:
                a = c = (a + c) / 2
                frz[i] = 1
                newly = True
            lo[i] = a
            hi[i] = c
        if newly:
            work = [w for w in work if not frz[w[1]]]
    return (hi[root] + lo[root]) / 2, it


def solve(tolerance=TOLERANCE, flavour='flat'):
    B.getCritDist.cache_clear()
    t0 = time.perf_counter()
    g = build_csr()
    t1 = time.perf_counter()
    if flavour == 'flat':
        r, it = sweep_flat(g, tolerance)
    else:
        r, it = sweep_gather(g, tolerance)
    t2 = time.perf_counter()
    return r, it, t1 - t0, t2 - t1


def run(tolerance=TOLERANCE):
    return solve(tolerance)[0]


if __name__ == '__main__':
    for fl in ('flat', 'gather'):
        r, n, tb, ti = solve(flavour=fl)
        print("%-7s result=%.12f sweeps=%d build=%.3fs iter=%.3fs"
              % (fl, r, n, tb, ti))
