"""Algorithmic instrumentation of the stock mdp value iteration.

Answers, with numbers, the questions the FINDINGS report needs:

  * graph shape (nodes by kind, edges, out-degree)
  * how the frozen set grows sweep-by-sweep  -> is an active list worth it?
  * how many nodes actually *change* value per sweep -> is a dirty-set
    worklist (which is bit-identical to the stock trajectory) worth it?
  * what the TRUE fixed point is, versus the benchmark's asserted
    0.89873589887 -> decides whether policy iteration is legal at all
  * sweeps-to-tolerance under alternative sweep orders (Gauss-Seidel
    forward / reversed / Jacobi) and under SOR over-relaxation

Run:  python analyze.py
"""
import sys
from collections import defaultdict

import t0_stock as S


def build():
    b = S.Battle()
    root = b.initial()
    stateps = S.topoSort([root], b.getSuccessorsList)
    return b, root, stateps


def graph_shape():
    b, root, stateps = build()
    kinds = defaultdict(int)
    edges = 0
    deg = defaultdict(int)
    for sp in stateps:
        kinds[sp[0]] += 1
        succ = b.successors.get(sp, [])
        edges += len(succ)
        deg[sp[0]] += len(succ)
    print("--- graph shape ---")
    print("nodes total        : %d" % len(stateps))
    for k in sorted(kinds):
        name = {0: 'choice(max)', 1: 'chance-B', 2: 'chance-C',
                4: 'terminal'}[k]
        d = (deg[k] / kinds[k]) if kinds[k] else 0
        print("  kind %d %-12s: %5d nodes, %6d edges, avg out-deg %.2f"
              % (k, name, kinds[k], deg[k], d))
    print("edges total        : %d" % edges)
    print("chance nodes       : %d" % (kinds[1] + kinds[2]))
    print("distinct getCritDist arg tuples seen: see critdist_calls()")
    return b, root, stateps


def critdist_calls():
    orig = S.getCritDist
    seen = defaultdict(int)

    def wrapper(*a):
        seen[a] += 1
        return orig(*a)
    S.getCritDist = wrapper
    try:
        b, root, stateps = build()
    finally:
        S.getCritDist = orig
    print("--- getCritDist ---")
    print("calls: %d   distinct arg tuples: %d"
          % (sum(seen.values()), len(seen)))
    for k, v in sorted(seen.items(), key=lambda t: -t[1]):
        print("   x%-6d %s" % (v, k))


def sweep_profile(tolerance=S.TOLERANCE, limit=None):
    """Stock trajectory, instrumented per sweep."""
    b, root, stateps = build()
    dmin, dmax, frozen = b.min, b.max, b.frozen
    n = len(stateps)
    rows = []
    it = 0
    while dmax[root] - dmin[root] > tolerance:
        it += 1
        changed = 0
        visited = 0
        newfrozen = 0
        for sp in stateps:
            if sp in frozen:
                continue
            visited += 1
            o0, o1 = dmin[sp], dmax[sp]
            if sp[0] == 0:
                dmin[sp] = max(dmin[s] for s in b.successors[sp])
                dmax[sp] = max(dmax[s] for s in b.successors[sp])
            else:
                dmin[sp] = sum(dmin[s] * p for s, p in b.successors[sp])
                dmax[sp] = sum(dmax[s] * p for s, p in b.successors[sp])
            if dmin[sp] >= dmax[sp]:
                dmax[sp] = dmin[sp] = (dmin[sp] + dmax[sp]) / 2
                frozen.add(sp)
                newfrozen += 1
            if dmin[sp] != o0 or dmax[sp] != o1:
                changed += 1
        rows.append((it, visited, changed, newfrozen, len(frozen),
                     dmax[root] - dmin[root]))
        if limit and it >= limit:
            break
    print("--- sweep profile (tolerance=%s, %d nodes) ---" % (tolerance, n))
    print("sweep  visited  changed  newfrozen  frozen   width@root")
    for r in rows:
        if r[0] <= 12 or r[0] % 10 == 0 or r[0] >= len(rows) - 2:
            print("%5d  %7d  %7d  %9d  %6d   %.6f" % r)
    tot_visited = sum(r[1] for r in rows)
    tot_changed = sum(r[2] for r in rows)
    print("total node-updates executed by stock : %d" % (n * len(rows)))
    print("  of which skipped by 'sp in frozen' : %d"
          % (n * len(rows) - tot_visited))
    print("  actually recomputed                : %d" % tot_visited)
    print("  of those, value actually changed   : %d (%.1f%%)"
          % (tot_changed, 100.0 * tot_changed / max(tot_visited, 1)))
    print("result = %.12f  sweeps = %d"
          % ((dmax[root] + dmin[root]) / 2, len(rows)))
    return rows


def true_fixed_point(tolerance=1e-12, maxsweeps=100000):
    """Run the SAME interval iteration to a far tighter tolerance."""
    b, root, stateps = build()
    dmin, dmax, frozen = b.min, b.max, b.frozen
    it = 0
    while dmax[root] - dmin[root] > tolerance and it < maxsweeps:
        it += 1
        for sp in stateps:
            if sp in frozen:
                continue
            if sp[0] == 0:
                dmin[sp] = max(dmin[s] for s in b.successors[sp])
                dmax[sp] = max(dmax[s] for s in b.successors[sp])
            else:
                dmin[sp] = sum(dmin[s] * p for s, p in b.successors[sp])
                dmax[sp] = sum(dmax[s] * p for s, p in b.successors[sp])
            if dmin[sp] >= dmax[sp]:
                dmax[sp] = dmin[sp] = (dmin[sp] + dmax[sp]) / 2
                frozen.add(sp)
    v = (dmax[root] + dmin[root]) / 2
    print("--- true fixed point ---")
    print("tolerance %g reached after %d sweeps" % (tolerance, it))
    print("  dmin=%.15f dmax=%.15f mid=%.15f" % (dmin[root], dmax[root], v))
    print("  benchmark asserts       %.15f" % S.EXPECTED)
    print("  |true - asserted| = %.3e   (assertion tolerance 1e-6)"
          % abs(v - S.EXPECTED))
    return v


def order_experiment(tolerance=S.TOLERANCE):
    """Sweeps-to-tolerance for alternative update orders."""
    print("--- sweep-order experiment (tolerance=%s) ---" % tolerance)
    b0, root, stateps = build()
    succ = dict(b0.successors)
    n = len(stateps)

    def run(order, jacobi=False, omega=1.0, maxit=20000):
        dmin = defaultdict(float)
        dmax = defaultdict(lambda: 1.0)
        frozen = set()
        win, loss = (4, True), (4, False)
        dmax[loss] = 0.0
        dmin[win] = 1.0
        frozen.update([win, loss])
        it = 0
        while dmax[root] - dmin[root] > tolerance and it < maxit:
            it += 1
            if jacobi:
                pmin = dict(dmin)
                pmax = dict(dmax)
            else:
                pmin = dmin
                pmax = dmax
            for sp in order:
                if sp in frozen:
                    continue
                if sp[0] == 0:
                    a = max(pmin[s] for s in succ[sp])
                    c = max(pmax[s] for s in succ[sp])
                else:
                    a = sum(pmin[s] * p for s, p in succ[sp])
                    c = sum(pmax[s] * p for s, p in succ[sp])
                if omega != 1.0:
                    a = dmin[sp] + omega * (a - dmin[sp])
                    c = dmax[sp] + omega * (c - dmax[sp])
                dmin[sp], dmax[sp] = a, c
                if dmin[sp] >= dmax[sp]:
                    dmax[sp] = dmin[sp] = (dmin[sp] + dmax[sp]) / 2
                    frozen.add(sp)
        return it, (dmax[root] + dmin[root]) / 2, dmax[root] - dmin[root]

    variants = [
        ("stock order (GS, reverse-topo)", stateps, False, 1.0),
        ("reversed order (GS)", list(reversed(stateps)), False, 1.0),
        ("Jacobi, stock order", stateps, True, 1.0),
        ("SOR omega=1.2, stock order", stateps, False, 1.2),
        ("SOR omega=1.5, stock order", stateps, False, 1.5),
        ("SOR omega=1.8, stock order", stateps, False, 1.8),
    ]
    print("%-34s %7s  %-18s %s" % ("variant", "sweeps", "result", "width"))
    for name, order, jac, om in variants:
        it, v, w = run(order, jac, om)
        flag = "" if abs(v - S.EXPECTED) <= 1e-6 else "   <-- FAILS 1e-6 CHECK"
        print("%-34s %7d  %.12f  %.6f%s" % (name, it, v, w, flag))


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if what in ('all', 'shape'):
        graph_shape()
        print()
    if what in ('all', 'crit'):
        critdist_calls()
        print()
    if what in ('all', 'sweep'):
        sweep_profile()
        print()
    if what in ('all', 'true'):
        true_fixed_point()
        print()
    if what in ('all', 'order'):
        order_experiment()
