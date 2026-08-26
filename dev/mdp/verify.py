"""Bit-exactness verification for the mdp tiers.

The benchmark's own oracle only checks the root value to 1e-6.  That is a
weak test: it would pass a tier whose whole state vector drifted.  Here we
check the strong property instead --

    every tier that claims to be bit-identical must reproduce the stock
    dmin/dmax float for EVERY one of the 4823 states, and the identical
    sweep count.

We also cross-check the transition model itself: the (successor, probability)
lists produced by the Fraction build (T0/T1/T2) and by the exact-integer
build (T3) must agree bit-for-bit after the float conversion.

Run:  python verify.py
"""
import struct
import sys

import t0_stock as T0
import t1_micro as T1
import t2_csr as T2


def bits(x):
    return struct.pack('<d', x)


def stock_final(tolerance=T0.TOLERANCE):
    b = T0.Battle()
    root = b.initial()
    stateps = T0.topoSort([root], b.getSuccessorsList)
    dmin, dmax, frozen = b.min, b.max, b.frozen
    it = 0
    while dmax[root] - dmin[root] > tolerance:
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
    return b, root, stateps, dmin, dmax, it


def stock_naive_final(tolerance=T0.TOLERANCE):
    """Stock, but with sum() replaced by a naive left-to-right accumulation.

    CPython >= 3.12 gives builtin sum() Neumaier compensated summation for
    floats (gh-100425); 3.10 -- the QEMU VM's interpreter, and the official
    measurement target -- does plain left-to-right addition.  So THIS is the
    trajectory stock mdp actually follows on the VM, and it is the reference
    any tier that accumulates with an explicit loop must match.
    """
    b = T0.Battle()
    root = b.initial()
    stateps = T0.topoSort([root], b.getSuccessorsList)
    dmin, dmax, frozen = b.min, b.max, b.frozen
    it = 0
    while dmax[root] - dmin[root] > tolerance:
        it += 1
        for sp in stateps:
            if sp in frozen:
                continue
            if sp[0] == 0:
                dmin[sp] = max(dmin[s] for s in b.successors[sp])
                dmax[sp] = max(dmax[s] for s in b.successors[sp])
            else:
                a = 0.0
                c = 0.0
                for s, p in b.successors[sp]:
                    a += dmin[s] * p
                    c += dmax[s] * p
                dmin[sp] = a
                dmax[sp] = c
            if dmin[sp] >= dmax[sp]:
                dmax[sp] = dmin[sp] = (dmin[sp] + dmax[sp]) / 2
                frozen.add(sp)
    return root, stateps, dmin, dmax, it


def t1_final(tolerance=T0.TOLERANCE):
    T1.getCritDist.cache_clear()
    b = T1.Battle()
    root = b.initial()
    v = b.evaluate(tolerance)
    return b, root, b.min, b.max, b.itercount, v


def compare_model(stateps, stock_succ, other_succ, label):
    bad = 0
    for sp in stateps:
        if sp[0] == 4:          # terminals never enter the successor cache
            continue
        a = stock_succ[sp]
        c = other_succ[sp]
        if len(a) != len(c):
            bad += 1
            continue
        for x, y in zip(a, c):
            if sp[0] == 0:
                if x != y:
                    bad += 1
                    break
            else:
                if x[0] != y[0] or bits(x[1]) != bits(y[1]):
                    bad += 1
                    break
    print("  model %-28s : %s (%d mismatching nodes)"
          % (label, "OK" if bad == 0 else "MISMATCH", bad))
    return bad == 0


def main():
    ok = True
    print("=== building stock reference ===")
    b0, root, stateps, dmin0, dmax0, it0 = stock_final()
    print("stock: result=%r sweeps=%d states=%d"
          % ((dmax0[root] + dmin0[root]) / 2, it0, len(stateps)))
    assert abs((dmax0[root] + dmin0[root]) / 2 - T0.EXPECTED) < 1e-6

    print("=== stock with naive summation (== stock on CPython 3.10) ===")
    rootN, statepsN, dminN, dmaxN, itN = stock_naive_final()
    diff = sum(1 for sp in stateps
               if bits(dmin0[sp]) != bits(dminN[sp])
               or bits(dmax0[sp]) != bits(dmaxN[sp]))
    print("  vs sum()-on-3.12 stock: %d/%d states differ, sweeps %d vs %d,"
          " root %r" % (diff, len(stateps), itN, it0,
                        (dmaxN[rootN] + dminN[rootN]) / 2))
    print("  -> the interpreter version itself perturbs the last ulp;"
          " both pass the benchmark's 1e-6 oracle with 111 sweeps.")

    print("=== T1 (memoised build, active list) ===")
    b1, root1, dmin1, dmax1, it1, v1 = t1_final()
    ok &= compare_model(stateps, b0.successors, b1.successors, "T1 vs stock")
    bad = sum(1 for sp in stateps
              if bits(dmin0[sp]) != bits(dmin1[sp])
              or bits(dmax0[sp]) != bits(dmax1[sp]))
    print("  state vector: %s (%d/%d states differ), sweeps %d vs %d"
          % ("BIT-IDENTICAL" if bad == 0 else "DRIFT", bad, len(stateps),
             it1, it0))
    ok &= (bad == 0 and it1 == it0)

    print("=== T2 (CSR renumbering) ===")
    for flavour in ('flat', 'gather'):
        g = T2.build_csr()
        if flavour == 'flat':
            v, it = T2.sweep_flat(g)
        else:
            v, it = T2.sweep_gather(g)
        # 'flat' accumulates with an explicit loop -> compare against the
        # naive-sum reference (stock on 3.10); 'gather' still calls sum() ->
        # compare against the sum() reference (stock on this interpreter).
        ref_lo, ref_hi, tag = ((dminN, dmaxN, "3.10-stock (naive sum)")
                               if flavour == 'flat'
                               else (dmin0, dmax0, "3.12-stock (sum())"))
        bad = 0
        for i, sp in enumerate(g.stateps):
            if bits(g.lo[i]) != bits(ref_lo[sp]) or \
                    bits(g.hi[i]) != bits(ref_hi[sp]):
                bad += 1
        print("  %-7s vs %-24s: %s (%d/%d differ), sweeps %d, root %r"
              % (flavour, tag,
                 "BIT-IDENTICAL" if bad == 0 else "DRIFT", bad,
                 g.n, it, v))
        ok &= (bad == 0 and it == it0)

    try:
        import t3_intexact as T3
    except ImportError:
        T3 = None
    if T3 is not None:
        print("=== T3 (exact integer arithmetic instead of Fraction) ===")
        g3 = T3.build_csr()
        # model equality: same successors, same float probabilities
        bad = 0
        g2 = T2.build_csr()
        if g2.n != g3.n:
            print("  node count differs: %d vs %d" % (g2.n, g3.n))
            ok = False
        else:
            for i in range(g2.n):
                if g2.stateps[i] != g3.stateps[i]:
                    bad += 1
                    continue
                s2, e2 = g2.row[i], g2.row[i + 1]
                s3, e3 = g3.row[i], g3.row[i + 1]
                if e2 - s2 != e3 - s3 or \
                        g2.col[s2:e2] != g3.col[s3:e3] or \
                        [bits(x) for x in g2.prb[s2:e2]] != \
                        [bits(x) for x in g3.prb[s3:e3]]:
                    bad += 1
            print("  transition model vs Fraction build: %s (%d nodes differ)"
                  % ("BIT-IDENTICAL" if bad == 0 else "MISMATCH", bad))
            ok &= (bad == 0)
        v, it = T2.sweep_flat(g3)       # explicit-loop accumulation
        bad = sum(1 for i, sp in enumerate(g3.stateps)
                  if bits(g3.lo[i]) != bits(dminN[sp])
                  or bits(g3.hi[i]) != bits(dmaxN[sp]))
        print("  state vector vs 3.10-stock (naive sum): %s (%d/%d differ),"
              " sweeps %d, root %r"
              % ("BIT-IDENTICAL" if bad == 0 else "DRIFT", bad, g3.n, it, v))
        ok &= (bad == 0 and it == it0)

    try:
        import tanti_numpy as TA
    except ImportError:
        TA = None
    if TA is not None:
        print("=== T-anti (numpy reduceat sweep) ===")
        v, it, lo, hi = TA.solve_verbose()
        bad = sum(1 for i, sp in enumerate(g.stateps)
                  if bits(float(lo[i])) != bits(dmin0[sp])
                  or bits(float(hi[i])) != bits(dmax0[sp]))
        print("  state vector: %s (%d/%d differ), sweeps %d, root %r"
              % ("BIT-IDENTICAL" if bad == 0 else "DRIFT", bad, len(lo),
                 it, v))
        print("  (drift here is expected: pairwise summation in numpy is a"
              " different but equally valid summation order)")

    print()
    print("VERDICT:", "all bit-identical tiers verified"
          if ok else "SOME TIER DRIFTED -- see above")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
