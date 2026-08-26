"""T4 - the algorithmic / numeric investigation.

Everything in here changes *what sequence of numbers the solver produces*,
which is the crux of the mdp optimisation question.  The benchmark asserts

    abs(result - 0.89873589887) <= 1e-6

and 0.89873589887 is NOT the value of the game.  It is the midpoint of an
interval of width 0.192 that the stock solver happens to be sitting on after
its 111th sweep.  So the oracle pins the *iteration trajectory*, not the
answer.  Any change to the convergence rate moves the result far more than
1e-6 and fails the benchmark's own check.  This module measures that claim
rather than asserting it.

Experiments (run `python t4_algo.py`):

  value        -- the true value of the game, by policy iteration with an
                  exact linear policy-evaluation solve, plus how far it is
                  from the number the benchmark asserts
  tol          -- sweeps-to-tolerance curve for the stock interval iteration
  order        -- Gauss-Seidel (stock order) vs reversed vs Jacobi vs SOR
  churn        -- how many states actually change value per sweep, i.e.
                  whether a dirty-set worklist / prioritised sweeping can
                  ever pay off here
  scc          -- strongly connected components: why the graph is not a DAG
                  and why one backward pass cannot work
"""
import sys
import time

import t2_csr as T2
import t3_intexact as T3

EXPECTED = 0.89873589887
TOLERANCE = 0.192


# ---------------------------------------------------------------- policy it.

def policy_iteration(g, verbose=True):
    """Exact value of the game.

    For a FIXED policy the choice nodes become identities and the whole graph
    is one linear system (I - P) V = b, which we solve directly.  Policy
    improvement then flips choice nodes to their better successor.  This is
    textbook policy iteration; it converges in a handful of rounds instead of
    the interval iteration's thousands.
    """
    import numpy as np

    n = g.n
    row, col, prb, kind, frz = g.row, g.col, g.prb, g.kind, g.frz

    # start from the 'always attack' policy (successor 0 == 'Dig'), which is
    # proper: every play reaches a terminal with probability 1.
    pol = [0] * n
    choice = [i for i in range(n) if not frz[i] and not kind[i]]

    t0 = time.perf_counter()
    rounds = 0
    solves = 0
    while True:
        rounds += 1
        A = np.zeros((n, n))
        b = np.zeros(n)
        for i in range(n):
            A[i, i] = 1.0
            if frz[i]:
                b[i] = g.lo[i]           # terminals: win -> 1.0, loss -> 0.0
            elif kind[i]:
                for j in range(row[i], row[i + 1]):
                    A[i, col[j]] -= prb[j]
            else:
                A[i, col[row[i] + pol[i]]] -= 1.0
        V = np.linalg.solve(A, b)
        solves += 1

        changed = 0
        for i in choice:
            s = row[i]
            best = 0
            bv = V[col[s]]
            for k in range(1, row[i + 1] - s):
                if V[col[s + k]] > bv:
                    bv = V[col[s + k]]
                    best = k
            if best != pol[i]:
                pol[i] = best
                changed += 1
        if verbose:
            print("  round %d: V(root) = %.12f, %d choice nodes flipped"
                  % (rounds, V[g.root], changed))
        if changed == 0:
            break
    dt = time.perf_counter() - t0
    return float(V[g.root]), rounds, solves, dt, pol


def experiment_value():
    print("--- exact value of the game (policy iteration) ---")
    g = T3.build_csr()
    v, rounds, solves, dt, pol = policy_iteration(g)
    print("  V*(root)                    = %.12f" % v)
    print("  benchmark asserts            %.12f" % EXPECTED)
    print("  |V* - asserted|             = %.6f   (oracle tolerance 1e-6)"
          % abs(v - EXPECTED))
    print("  policy-iteration rounds     = %d (%d dense %dx%d solves, %.2fs)"
          % (rounds, solves, g.n, g.n, dt))
    npot = sum(1 for i in range(g.n)
               if not g.frz[i] and not g.kind[i] and pol[i] == 1)
    print("  optimal policy uses Super Potion in %d of %d choice states"
          % (npot, sum(1 for i in range(g.n)
                       if not g.frz[i] and not g.kind[i])))
    print()
    print("  VERDICT: policy iteration computes the value of the MDP in %d"
          % rounds)
    print("  rounds instead of 111 sweeps, but it does NOT compute what the")
    print("  benchmark measures.  The benchmark's answer is a *bracket"
          " midpoint*")
    print("  after a fixed amount of work; the true value is %.4f away, i.e."
          % abs(v - EXPECTED))
    print("  %.0fx the 1e-6 oracle.  Swapping in policy iteration makes"
          % (abs(v - EXPECTED) / 1e-6))
    print("  bench_mdp raise.  It is benchmark replacement, not optimisation.")
    return v


# ------------------------------------------------------------ tolerance curve

def experiment_tol():
    print("--- sweeps to tolerance (stock interval iteration) ---")
    print("%10s %8s %-16s %s" % ("tolerance", "sweeps", "result",
                                 "|result-asserted|"))
    for tol in (0.5, 0.3, 0.25, 0.2, 0.192, 0.19, 0.15, 0.1, 0.05, 0.02):
        g = T3.build_csr()
        t0 = time.perf_counter()
        v, it = T2.sweep_flat(g, tol)
        dt = time.perf_counter() - t0
        print("%10s %8d %.12f  %.6f   (%.2fs)"
              % (tol, it, v, abs(v - EXPECTED), dt))
    print("  -> 0.192 is a hand-tuned knob: it stops the solver at 111"
          " sweeps.")
    print("     The asserted constant is a property of THAT stopping point.")


# ------------------------------------------------------------- order / SOR

def _sweep_variant(g, tolerance, order=None, jacobi=False, omega=1.0,
                   maxit=1500):
    kind, row, col, prb = g.kind, g.row, g.col, g.prb
    lo, hi, frz = g.lo, g.hi, g.frz
    root = g.root
    if order is None:
        order = list(g.order)
    it = 0
    while hi[root] - lo[root] > tolerance and it < maxit:
        it += 1
        if jacobi:
            plo = lo[:]
            phi = hi[:]
        else:
            plo = lo
            phi = hi
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
                    a += plo[k] * p
                    c += phi[k] * p
            else:
                k = col[s]
                a = plo[k]
                c = phi[k]
                for j in range(s + 1, e):
                    k = col[j]
                    if plo[k] > a:
                        a = plo[k]
                    if phi[k] > c:
                        c = phi[k]
            if omega != 1.0:
                a = lo[i] + omega * (a - lo[i])
                c = hi[i] + omega * (c - hi[i])
            if a >= c:
                a = c = (a + c) / 2
                frz[i] = 1
                newly = True
            lo[i] = a
            hi[i] = c
        if newly:
            order = [i for i in order if not frz[i]]
    return (hi[root] + lo[root]) / 2, it, hi[root] - lo[root]


def experiment_order():
    print("--- sweep order / relaxation (tolerance=%s) ---" % TOLERANCE)
    print("%-38s %7s %-16s %-9s %s"
          % ("variant", "sweeps", "result", "width", "oracle"))
    variants = [
        ("stock: Gauss-Seidel, reverse-topo", dict()),
        ("Gauss-Seidel, reversed order", dict(reverse=True)),
        ("Jacobi (same order)", dict(jacobi=True)),
        ("SOR omega=1.2", dict(omega=1.2)),
        ("SOR omega=1.5", dict(omega=1.5)),
        ("SOR omega=1.8", dict(omega=1.8)),
        ("SOR omega=1.95", dict(omega=1.95)),
    ]
    for name, kw in variants:
        g = T3.build_csr()
        order = list(reversed(g.order)) if kw.pop('reverse', False) else None
        t0 = time.perf_counter()
        v, it, w = _sweep_variant(g, TOLERANCE, order=order, **kw)
        dt = time.perf_counter() - t0
        ok = "PASS" if abs(v - EXPECTED) <= 1e-6 else "FAIL 1e-6"
        print("%-38s %7d %.12f  %.7f %-9s (%.2fs)"
              % (name, it, v, w, ok, dt))
    print("  -> the stock order is already the *best possible* Gauss-Seidel")
    print("     order (DFS post-order on the successor graph == reverse")
    print("     topological), so reordering can only make it worse; and any")
    print("     variant that converges faster lands on a different bracket")
    print("     midpoint and fails the benchmark's own assertion.")


# ------------------------------------------------------------------- churn

def experiment_churn():
    print("--- per-sweep churn (can a worklist / prioritised sweeping win?) "
          "---")
    g = T3.build_csr()
    kind, row, col, prb = g.kind, g.row, g.col, g.prb
    lo, hi, frz = g.lo, g.hi, g.frz
    root = g.root
    order = list(g.order)
    it = 0
    tot_visits = 0
    tot_changed = 0
    rows = []
    while hi[root] - lo[root] > TOLERANCE:
        it += 1
        changed = 0
        newly = False
        for i in order:
            s, e = row[i], row[i + 1]
            o0, o1 = lo[i], hi[i]
            if kind[i]:
                a = c = 0.0
                for j in range(s, e):
                    k = col[j]
                    p = prb[j]
                    a += lo[k] * p
                    c += hi[k] * p
            else:
                k = col[s]
                a, c = lo[k], hi[k]
                for j in range(s + 1, e):
                    k = col[j]
                    if lo[k] > a:
                        a = lo[k]
                    if hi[k] > c:
                        c = hi[k]
            if a >= c:
                a = c = (a + c) / 2
                frz[i] = 1
                newly = True
            lo[i] = a
            hi[i] = c
            if a != o0 or c != o1:
                changed += 1
        tot_visits += len(order)
        tot_changed += changed
        rows.append((it, len(order), changed))
        if newly:
            order = [i for i in order if not frz[i]]
    print("  sweeps                          : %d" % it)
    print("  node updates the stock loop runs : %d" % (g.n * it))
    print("  after the active list            : %d" % tot_visits)
    print("  of those, value actually changed : %d (%.2f%%)"
          % (tot_changed, 100.0 * tot_changed / tot_visits))
    print("  last 5 sweeps changed:", [r[2] for r in rows[-5:]],
          "of", rows[-1][1])
    print("  -> a dirty-set worklist would re-queue essentially every node")
    print("     every sweep, so it costs bookkeeping and saves nothing.")
    print("     Prioritised sweeping (Dijkstra-like residual ordering) is")
    print("     strictly worse: it adds a heap on top of the same churn AND")
    print("     changes the update order, which breaks the oracle.")


# --------------------------------------------------------------------- SCC

def experiment_scc():
    print("--- strongly connected components ---")
    g = T3.build_csr()
    n, row, col = g.n, g.row, g.col
    # iterative Tarjan
    index = [-1] * n
    low = [0] * n
    onstk = bytearray(n)
    stk = []
    comp = [-1] * n
    counter = 0
    ncomp = 0
    sizes = []
    for r in range(n):
        if index[r] != -1:
            continue
        work = [(r, row[r])]
        index[r] = low[r] = counter
        counter += 1
        stk.append(r)
        onstk[r] = 1
        while work:
            v, pj = work[-1]
            if pj < row[v + 1]:
                work[-1] = (v, pj + 1)
                w = col[pj]
                if index[w] == -1:
                    index[w] = low[w] = counter
                    counter += 1
                    stk.append(w)
                    onstk[w] = 1
                    work.append((w, row[w]))
                elif onstk[w]:
                    if index[w] < low[v]:
                        low[v] = index[w]
            else:
                work.pop()
                if work:
                    u = work[-1][0]
                    if low[v] < low[u]:
                        low[u] = low[v]
                if low[v] == index[v]:
                    size = 0
                    while True:
                        w = stk.pop()
                        onstk[w] = 0
                        comp[w] = ncomp
                        size += 1
                        if w == v:
                            break
                    sizes.append(size)
                    ncomp += 1
    sizes.sort(reverse=True)
    print("  components: %d   largest: %s" % (ncomp, sizes[:5]))
    print("  nodes in non-trivial (size>1) components: %d of %d"
          % (sum(s for s in sizes if s > 1), n))
    print("  -> Super Potion makes %d states mutually reachable, so there is"
          % sizes[0])
    print("     no backward pass that solves them; that cycle is exactly why")
    print("     the benchmark iterates.  Within one SCC the fixed point is a")
    print("     linear system -- which is what policy iteration solves, and")
    print("     what the oracle forbids us from substituting.")


def experiment_bounds():
    """Where do the 111 sweeps actually go?  Trace both root bounds."""
    print("--- root bracket per sweep ---")
    VSTAR = 0.802753072810           # from experiment_value()
    g = T3.build_csr()
    kind, row, col, prb = g.kind, g.row, g.col, g.prb
    lo, hi, frz = g.lo, g.hi, g.frz
    root = g.root
    order = list(g.order)
    it = 0
    print("%6s %-18s %-18s %-12s %s"
          % ("sweep", "dmin(root)", "dmax(root)", "width", "dmin - V*"))
    while hi[root] - lo[root] > TOLERANCE:
        it += 1
        newly = False
        for i in order:
            s, e = row[i], row[i + 1]
            if kind[i]:
                a = c = 0.0
                for j in range(s, e):
                    k = col[j]
                    p = prb[j]
                    a += lo[k] * p
                    c += hi[k] * p
            else:
                k = col[s]
                a, c = lo[k], hi[k]
                for j in range(s + 1, e):
                    k = col[j]
                    if lo[k] > a:
                        a = lo[k]
                    if hi[k] > c:
                        c = hi[k]
            if a >= c:
                a = c = (a + c) / 2
                frz[i] = 1
                newly = True
            lo[i] = a
            hi[i] = c
        if newly:
            order = [i for i in order if not frz[i]]
        if it <= 10 or it % 20 == 0 or hi[root] - lo[root] <= TOLERANCE:
            print("%6d %.15f  %.15f  %.9f  %+.3e"
                  % (it, lo[root], hi[root], hi[root] - lo[root],
                     lo[root] - VSTAR))
    print("  -> the LOWER bound is converged to the true value V*=%.9f" % VSTAR)
    print("     within ~1e-9 after a couple of dozen sweeps.  Every remaining")
    print("     sweep is spent grinding the OPTIMISTIC bound down, because")
    print("     the optimistic policy is 'heal forever' and the Super-Potion")
    print("     cycle is undiscounted.  111 sweeps buy ~5e-3 of dmax.")


if __name__ == '__main__':
    which = sys.argv[1:] or ['value', 'tol', 'order', 'churn', 'scc',
                             'bounds']
    for w in which:
        globals()['experiment_' + w]()
        print()
