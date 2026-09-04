#!/usr/bin/env python3
"""Cycle-accurate schedule model for the grape_pipeline step (uArch §7; review R2/R3/R6).

Greedy in-order list scheduler. Every op is one Python-visible binary64 rounding (PRD-F2: no
fusion — the accumulate consumes pre-rounded force terms with plain add/sub). Unit classes:
ADD (sub/add), MUL, SQRT (iterative pipelined, II=2), RCP (dedicated engine, II=2). Per-
(body,component) velocity writes are chained in strict pair order; per-pair op dependencies as in
golden/emulation.py. Prints the step cycle count for an inventory sweep.

    python3 hw/grape_pipeline/docs/schedule_model.py
"""
import itertools

PAIRS = [(i, j) for i in range(4) for j in range(i + 1, 5)]  # benchmark pair order (combinations)
ADD_L, MUL_L = 3, 3
SQRT_L, SQRT_II = 30, 2
RCP_L, RCP_II = 22, 2
COMMIT, FSM = 2, 4


def build_ops():
    ops = []          # (id, unit, deps, chain_key or None)
    def op(unit, deps, chain=None):
        ops.append({"u": unit, "d": list(deps), "c": chain, "t": None})
        return len(ops) - 1
    vchain = {}       # (body, comp) -> last op id (order enforced)
    for (bi, bj) in PAIRS:
        sub = [op("ADD", []) for _ in range(3)]                      # dx dy dz
        sq = [op("MUL", [sub[c]]) for c in range(3)]
        a1 = op("ADD", [sq[0], sq[1]])
        dsq = op("ADD", [a1, sq[2]])
        s = op("SQRT", [dsq])
        d3 = op("MUL", [dsq, s])
        rcp = op("RCP", [d3])
        mag = op("MUL", [rcp])
        b1m = op("MUL", [mag]); b2m = op("MUL", [mag])
        f_i = [op("MUL", [sub[c], b2m]) for c in range(3)]           # dx_c * b2m
        f_j = [op("MUL", [sub[c], b1m]) for c in range(3)]           # dx_c * b1m
        for c in range(3):                                           # v_i.c -= f_i[c] (Python order: v1 then v2)
            prev = vchain.get((bi, c))
            vchain[(bi, c)] = op("ADD", [f_i[c]] + ([prev] if prev is not None else []), (bi, c))
        for c in range(3):
            prev = vchain.get((bj, c))
            vchain[(bj, c)] = op("ADD", [f_j[c]] + ([prev] if prev is not None else []), (bj, c))
    integ = []
    for b in range(5):
        for c in range(3):
            m = op("MUL", [vchain[(b, c)]])                          # dt * v.c (dep: final v)
            integ.append(op("ADD", [m]))                             # r.c += ...
    return ops


def schedule(n_add, n_mul):
    ops = build_ops()
    lat = {"ADD": ADD_L, "MUL": MUL_L, "SQRT": SQRT_L, "RCP": RCP_L}
    cap = {"ADD": n_add, "MUL": n_mul, "SQRT": 1, "RCP": 1}
    ii_block = {"SQRT": 0, "RCP": 0}                                 # next cycle the II-limited unit is free
    done = [None] * len(ops)
    t = 0
    pending = set(range(len(ops)))
    chain_issued = {}                                                # chain key -> last issued op index (in-order per chain)
    while pending:
        used = {k: 0 for k in cap}
        for i in sorted(pending):
            o = ops[i]
            u = o["u"]
            if used[u] >= cap[u]:
                continue
            if u in ii_block and t < ii_block[u]:
                continue
            if any(done[d] is None or done[d] > t for d in o["d"]):
                continue
            if o["c"] is not None:                                   # strict per-chain order
                li = chain_issued.get(o["c"], -1)
                if any(j in pending and j < i and ops[j]["c"] == o["c"] for j in range(li + 1, i)):
                    continue
            done[i] = t + lat[u]
            used[u] += 1
            if u in ii_block:
                ii_block[u] = t + (SQRT_II if u == "SQRT" else RCP_II)
            if o["c"] is not None:
                chain_issued[o["c"]] = i
            pending.discard(i)
        t += 1
        if t > 2000:
            raise RuntimeError("no progress")
    return max(d for d in done) + COMMIT + FSM


if __name__ == "__main__":
    import sys
    g = globals()
    for arg in sys.argv[1:]:                       # e.g. MUL_L=4 SQRT_L=32
        k, v = arg.split("=")
        g[k] = int(v)
    for tag, (sq, rc) in (("nominal", (SQRT_L, RCP_L)), ("worst corner", (SQRT_L + 2, RCP_L + 2))):
        g["SQRT_L"], g["RCP_L"] = sq, rc
        print(f"{tag}: add {ADD_L}, mul {MUL_L}, sqrt {sq} (II={SQRT_II}), rcp {rc} (II={RCP_II}); commit+fsm {COMMIT + FSM}")
        for n_add, n_mul in itertools.product((2, 3), (2, 3, 4)):
            c = schedule(n_add, n_mul)
            print(f"  {n_add} add, {n_mul} mul: {c} cycles/step  ({'PASS' if c <= 128 else 'fail'})  benchmark {20000*c/1e6:.2f} M cycles")
        g["SQRT_L"], g["RCP_L"] = sq, rc
