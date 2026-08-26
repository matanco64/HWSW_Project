# mdp - software optimization findings

Benchmark: `pyperformance` 1.14.0 `bm_mdp`, imported byte-identical into
`benchmarks/bm_mdp/run_benchmark.py`.

Everything below was measured. Timings are **provisional** (shared WSL2 desktop, no
CPU isolation, three agents contending during part of the session) and are quoted as
best-of-9 interleaved rounds; the coordinator re-runs the rigorous A/B serially.
**Sweep counts, result values, node/edge counts and bit-exactness results are exact
and machine-independent** - those are the load-bearing evidence here.

Interpreters: `/root/hwsw-env/py310/bin/python` (CPython 3.10.21, stand-in for the
VM's 3.10.12) as primary; CPython 3.12.6 / 3.14.6 on Windows as version-sensitivity
cross-checks.

Files: `t0_stock.py` `t1_micro.py` `t2_csr.py` `t3_intexact.py` `t4_algo.py`
`tanti_numpy.py` (tiers), `bench.py` (interleaved timing harness), `verify.py`
(bit-exactness), `analyze.py` (graph/sweep instrumentation).

---

## 0. What the workload actually is

`Battle().evaluate(0.192)` runs in two phases.

**Phase 1 - graph construction** (`topoSort`, which populates the successor cache).
Enumerates the reachable state graph with exact `fractions.Fraction` damage
distributions.

| quantity | measured |
|---|---|
| nodes | **4823** |
| choice nodes (`max`, out-degree exactly 2) | 1162 |
| chance nodes kind 1 (`_getSuccessorsB`) | 2324, 8232 edges, avg out-deg 3.54 |
| chance nodes kind 2 (`_getSuccessorsC`) | 1335, 11862 edges, avg out-deg 8.89 |
| terminals (`win`, `loss`) | 2 |
| edges | **22418** |
| chance out-degree distribution | 931 nodes have out-degree **1**, 1212 have 2, ... max 22 |
| `getCritDist` calls | **3659**, with only **3 distinct argument tuples** |

The 3 distinct `getCritDist` tuples (x1513, x1513, x633):

```
(11, Fraction(115, 512), 50, 50, 38, 38,  40, True,  2)   # Starmie Water Gun
(11, Fraction(115, 512), 50, 50, 38, 38,  65, True,  2)   # Starmie Bubblebeam
(26, Fraction(65,  512), 43, 39, 44, 44, 100, False, 1)   # Charmeleon Dig
```

Stats never change during a battle - only HP does - so the damage distribution is a
function of three constant argument tuples. 3656 of the 3659 calls are pure waste.

**Phase 2 - interval value iteration.** 111 Gauss-Seidel sweeps over the topological
order, maintaining a `[dmin, dmax]` bracket per state, stopping when the bracket at
the root drops below `tolerance = 0.192`, returning the midpoint.

Per-sweep instrumentation (`analyze.py sweep`, exact):

| | |
|---|---|
| sweeps | **111** |
| node updates the stock loop iterates over | 535 353 (= 4823 x 111) |
| skipped by the `sp in frozen` test | 145 642 |
| actually recomputed | 389 711 |
| ...of which the value actually **changed** | 388 757 = **99.76 %** |
| freezing events | **all 1322 happen in sweep 1**; sweeps 2-111 freeze nothing |
| active nodes, sweeps 2-111 | 3499 (constant) |

**Strongly connected components** (`t4_algo.py scc`): 1826 components, largest 112
(several of size 112), **3024 of 4823 nodes sit in non-trivial SCCs**. Super Potion is
what creates them. This is why the code iterates instead of doing one backward pass.

---

## 1. The algorithmic / numeric question

### 1.1 The decisive fact: the oracle pins the trajectory, not the answer

`bench_mdp` asserts `abs(result - 0.89873589887) <= 1e-6`.

**0.89873589887 is not the value of the game.** It is the *midpoint of a bracket of
width 0.192* that the stock solver happens to be sitting on after its 111th sweep.

Measured by policy iteration with exact linear policy evaluation (`t4_algo.py value`):

```
round 1: V(root) = 0.105370315230, 865 choice nodes flipped
round 2: V(root) = 0.764281347131, 108 choice nodes flipped
round 3: V(root) = 0.801805494277,  54 choice nodes flipped
round 4: V(root) = 0.802676737346,   8 choice nodes flipped
round 5: V(root) = 0.802753072810,   0 choice nodes flipped   <- converged

V*(root)            = 0.802753072810
benchmark asserts     0.898735898870
|V* - asserted|     = 0.095983   = 95 983 x the 1e-6 oracle
5 policy-iteration rounds, 5 dense 4823x4823 solves, 63.2 s
optimal policy uses Super Potion in 1021 of 1162 choice states
```

Cross-validated independently: tracing the root bracket per sweep
(`t4_algo.py bounds`) shows the **lower** bound converging onto exactly that number.

| sweep | dmin(root) | dmax(root) | width | dmin - V* |
|---|---|---|---|---|
| 1 | 0.275289643127 | 0.999984864561 | 0.724695 | -5.28e-01 |
| 10 | 0.785786901111 | 0.999556385264 | 0.213769 | -1.70e-02 |
| 20 | 0.802115437273 | 0.999076361467 | 0.196961 | -6.38e-04 |
| 40 | 0.802737490402 | 0.998117005338 | 0.195380 | -1.56e-05 |
| 60 | 0.802752652613 | 0.997158570424 | 0.194406 | -4.20e-07 |
| 80 | 0.802753061477 | 0.996201055840 | 0.193448 | -1.13e-08 |
| 100 | 0.802753072505 | 0.995244460703 | 0.192491 | -3.06e-10 |
| **111** | **0.802753072768** | 0.994718724972 | 0.191966 | **-4.17e-11** |

Two independent methods agree to 4e-11 on the true answer - and the benchmark's
asserted constant is 0.096 away from it.

**Where the 111 sweeps go:** `dmin` is converged by roughly sweep 30. Sweeps 30-111
grind `dmax` down at ~4.8e-5 per sweep, because the *optimistic* policy is "drink
Super Potion forever" and the potion cycle is undiscounted. The benchmark's tolerance
is a hand-tuned knob sitting on the knee of that curve:

| tolerance | sweeps | result | \|result - asserted\| |
|---|---|---|---|
| 0.5 | 3 | 0.769802753821 | 0.128933 |
| 0.3 | 6 | 0.858266218577 | 0.040470 |
| 0.25 | 8 | 0.881979609938 | 0.016756 |
| 0.2 | 15 | 0.899768809591 | 0.001033 |
| **0.192** | **111** | **0.898735898870** | **0.000000** |
| 0.19 | 153 | 0.897733498229 | 0.001002 |
| 0.15 | 1009 | 0.877738123069 | 0.020998 |
| 0.1 | 2131 | 0.852743956366 | 0.045992 |
| 0.05 | 3378 | 0.827750635494 | 0.070985 |
| 0.02 | 4214 | 0.812747735269 | 0.085988 |

Moving the tolerance by 1 % in either direction moves the answer by ~1000x the oracle.

**Consequence for the whole exercise:** any change that alters the *convergence rate*
changes the answer far beyond 1e-6 and makes `bench_mdp` raise. The only legal
optimizations are ones that produce the **identical float trajectory** faster. mdp is
not a "find a better algorithm" benchmark; it is an "execute this exact fixed-point
iteration with less interpreter overhead" benchmark.

### 1.2 Policy iteration - VERDICT: **benchmark deletion. Do not ship.**

Label: *different computation, wrong output*.

- Genuinely a better algorithm for the underlying problem: **5 improvement rounds**
  versus 111 sweeps, and it produces the exact value rather than a bracket.
- But it computes `V* = 0.802753072810`, and `bench_mdp` demands `0.89873589887 +/-
  1e-6`. It misses by ~96 000x. Shipping it means either the benchmark raises or you
  edit the assertion - which is exactly the "you stopped running the benchmark"
  accusation.
- It is not even fast as implemented here: 5 dense 4823x4823 LU solves took **63.2 s**
  against 2.18 s for the whole stock benchmark. Per-SCC solves would be far faster
  (largest SCC is 112 nodes, so 1826 tiny dense solves) - irrelevant, because the
  output is still the wrong number.
- Honest framing for the talk: *"We implemented policy iteration. It solves the MDP in
  5 rounds instead of 111 sweeps and tells us Charmeleon actually wins 80.3 % of the
  time. It is also 9.6 percentage points away from the number the benchmark asserts,
  because the benchmark's answer is a bracket midpoint, not the win probability. Great
  slide, illegal optimization."*

This is a strong presentation asset precisely *because* we rejected it.

### 1.3 Prioritized sweeping / active-set - partly legitimate, mostly worthless

- **Active list - SHIPPED** (*constant-factor, legitimate*). All 1322 freezes happen in
  sweep 1; from sweep 2 the frozen set is constant at 1324. Stock still pays one
  `sp in frozen` test - a hash of a deeply nested namedtuple - for all 4823 nodes on
  all 111 sweeps. Hoisting frozen nodes out removes **145 642 no-op node visits and
  535 353 deep-tuple hashes**, trajectory unchanged.
- **Dirty-set worklist - REJECTED on measurement.** It *would* be bit-identical
  (skipping a node whose inputs did not change reproduces exactly what recomputing it
  would produce). But **99.76 % of recomputed nodes change value every sweep**, and the
  last five sweeps change 3499 of 3499. The worklist re-queues everything, every
  sweep, and charges bookkeeping for it. Zero upside.
- **True prioritized sweeping (Dijkstra-like residual ordering) - REJECTED as
  illegal.** Adds a heap on top of that same 99.76 % churn *and* changes update order,
  which changes the trajectory, which breaks the oracle (see 1.4).

### 1.4 Gauss-Seidel vs Jacobi vs reordering - stock is already optimal

`topoSort` does DFS post-order on the **successor** graph, so `stateps` lists every
node after its successors. The sweep therefore reads successor values already updated
in the same sweep: it is Gauss-Seidel in the best possible order for this graph.
Measured (`t4_algo.py order`, tolerance 0.192):

| variant | sweeps | result | oracle |
|---|---|---|---|
| **stock: Gauss-Seidel, reverse-topological** | **111** | 0.898735898870 | **PASS** |
| Gauss-Seidel, reversed order | 260 | 0.898744868705 | FAIL |
| Jacobi, same order | 369 | 0.898745194500 | FAIL |

Reordering can only make it worse (2.3x); Jacobi is 3.3x worse. Note both "wrong"
variants land within 1e-5 of the asserted constant and still **fail** the 1e-6 check -
the oracle is tight enough to catch a changed update order, loose enough to tolerate
last-ulp summation differences.

### 1.5 Convergence acceleration (SOR / Anderson) - unsound, not merely inaccurate

Over-relaxation extrapolates past the Bellman backup, so `dmin` can overshoot above
`dmax`. The stock freeze rule `if dmin >= dmax: collapse to midpoint` then fires
spuriously and collapses the graph onto garbage in a single sweep:

| variant | sweeps | result | oracle |
|---|---|---|---|
| SOR w=1.2 | 1 | 1.153184321019 | FAIL |
| SOR w=1.5 | 1 | 25.334640809442 | FAIL |
| SOR w=1.8 | 1 | 1172.286791303901 | FAIL |
| SOR w=1.95 | 1 | 6871.567600276045 | FAIL |

The `[dmin, dmax]` pair is only meaningful as a **true bracket** on V*; any accelerator
that is not itself monotone breaks the bracket and the midpoint answer becomes
meaningless. Anderson acceleration has the same defect for the same reason. Rejected
on soundness, before speed even enters the discussion.

### 1.6 Exact-arithmetic phase - the one genuinely "numeric" win, and it stays exact

Label: *exact algebraic reformulation; legitimate; shipped as T3*.

**(a) Memoize `getCritDist`.** Pure function, 3659 calls, 3 distinct argument tuples.
`functools.lru_cache` turns 3656 of them into dict hits.

**(b) Replace `fractions.Fraction` with fixed-denominator integers.** Every probability
in this benchmark is a rational whose denominator divides a small, statically known
constant:

```
DMG_DEN  = 512 * 39 = 19 968     one attack outcome:
                                 p = basespeed/pdiv, pdiv in {64,512}, clamped at 1
                                 mult = (1-p)/39 and p/39, and DMG_DEN % (pdiv*39) == 0
MULT_DEN = 260                   enemy move mixture: 64/130 -> 128/260,
                                 66/130 -> 132/260 (halves 64/260, 66/260)
DEN      = DMG_DEN * MULT_DEN = 5 191 680 < 2**23    a joint outcome
```

Every numerator that ever appears is below 2**23 - a single-digit CPython int. This
removes the ~677 k `math.gcd` calls, ~382 k `_from_coprime_ints` constructions and
~360 k `Fraction.__add__` allocations the earlier profile attributed to the build.

**It stays exact - proved, not asserted.** `Fraction.__float__` is `numerator /
denominator` on the *reduced* pair, and CPython's `int.__truediv__` is correctly
rounded, so `num / DEN` yields the identical double as `float(Fraction(num, DEN))` for
the same exact rational. `verify.py` checks it the hard way - it rebuilds the graph
both ways and compares **every edge of every node**, successor index and probability,
bit for bit:

```
=== T3 (exact integer arithmetic instead of Fraction) ===
  transition model vs Fraction build: BIT-IDENTICAL (0 nodes differ)
  state vector vs 3.10-stock (naive sum): BIT-IDENTICAL (0/4823 differ), sweeps 111
```

Not "close enough for 1e-6" - the transition model is the same 22 418 doubles.

### 1.7 State-key hashing / integer renumbering - the headline

Label: *pure data-structure win, legitimate; shipped as T2*.

Stock addresses every value by a `statep` tuple containing nested namedtuples
(`halfstate_t` -> `fixeddata_t` -> `stats_t`). **CPython does not cache tuple hashes**,
so every `dmin[sp2]` / `dmax[sp2]` / `successors[sp]` / `sp in frozen` access rehashes
the whole nested structure. Counting the iteration phase:

- 22 418 edges x 111 sweeps x 2 bounds ~= **5.0 M deep-tuple hashes** just to read
  successor bounds
- plus 2 x 389 711 `getSuccessors` calls (stock looks the list up twice per node)
- plus 535 353 `sp in frozen` tests

Renumbering to dense integers after `topoSort` and flattening to CSR
(`kind[] / row[] / col[] / prb[] / lo[] / hi[] / frz[]`) replaces all of that with list
indexing. Measured effect on the iteration phase alone: **6.3x on 3.10**. That is much
larger than the 30.4 % overall the earlier session recorded - that measurement
evidently did not also remove the generator expressions and the double lookup.

Two sweep implementations, both verified bit-identical:

- `sweep_flat` - explicit index loops over the flat arrays. The literal software twin
  of the hardware datapath; this is what T2/T3 ship.
- `sweep_gather` - `itemgetter(*cols)(lo)` to gather in C, then
  `sum(map(mul, vals, probs))`. Same speed within noise on 3.10, slower on 3.12.

### 1.8 A version dependency worth knowing about (and a trap avoided)

**CPython >= 3.12 gives `sum()` Neumaier compensated summation for floats (gh-100425);
3.10 does not.** This benchmark's inner loop is `sum(dmin[s]*p for ...)`, so *stock mdp
itself follows a different float trajectory on 3.10 than on 3.12*. Measured: on 3.12 a
naive-accumulation reference differs from `sum()` in **3612 of 4823** states; on 3.10
it differs in **0**.

Both still give 111 sweeps and pass the 1e-6 oracle, so it does not threaten the
benchmark. But "bit-identical" is version-relative: a CSR sweep that accumulates with
an explicit `a += lo[k]*p` loop is bit-identical to stock **on the VM's 3.10** while
differing in the last ulp on 3.12. `verify.py` therefore checks each tier against the
correct reference for its accumulation style. This is also why the Rust kernel must
accumulate naively left to right - no pairwise summation, no FMA.

### 1.9 Analyzed and rejected: unit-probability chain contraction

931 chance nodes have out-degree 1 with probability exactly 1.0 - pure pass-throughs,
`V[i] = V[j]`. Contracting them would remove 19 % of node updates. Rejected: inside an
SCC the sweep order is not guaranteed to place `j` before `i`, and if a predecessor of
`i` is updated after `j` in the same sweep, contraction changes which iterate it reads
and breaks bit-identity. Upside is ~3 % overall (these are the cheapest nodes) and does
not justify the risk. Recorded so the report can show it was considered.

---

## 2. Ladder

All tiers verified by `verify.py`, which checks the **entire 4823-state float vector**
bit for bit against the stock trajectory - not just the root value the benchmark
checks. Result and sweep columns are exact and machine-independent.

### 2.1 Correctness

| tier | what changed | result | sweeps | vs stock state vector | oracle |
|---|---|---|---|---|---|
| **T0** | stock reference | 0.8987358988699915 | 111 | - | PASS |
| **T1** | `lru_cache(getCritDist)`, active list, single successor lookup, locals | 0.8987358988699915 | 111 | **BIT-IDENTICAL** (0/4823) | PASS |
| **T2g** | + integer renumbering, CSR, C-gather sweep | 0.8987358988699915 | 111 | **BIT-IDENTICAL** (0/4823) | PASS |
| **T2** | + integer renumbering, CSR, flat-array sweep | 0.8987358988699915 | 111 | **BIT-IDENTICAL** (0/4823) | PASS |
| **T3** | + `Fraction` to exact fixed-denominator ints | 0.8987358988699915 | 111 | **BIT-IDENTICAL** (0/4823), transition model bit-identical edge by edge | PASS |
| **T4** | policy iteration (1.2) | 0.802753072810 | 5 rounds | different algorithm | **FAIL** (96 000x over) |
| **T-anti** | numpy `reduceat` vectorized sweep | 0.8987451944998 | **369** | drift, 3516/4823 | **FAIL** |

### 2.2 Timings - PROVISIONAL

Best-of-9 interleaved rounds of a complete `evaluate(0.192)` (`bench.py`). Shared
desktop, no CPU isolation. Ordering is meaningful; absolute numbers are not.

**CPython 3.10.21 (WSL2) - the VM stand-in, primary:**

| tier | best (s) | median | build | iterate | speedup | build x | iter x |
|---|---|---|---|---|---|---|---|
| T0 stock | 2.1781 | 2.2916 | 0.6904 | 1.4859 | 1.00x | 1.00x | 1.00x |
| T1 memoize + active list | 1.5147 | 1.5537 | 0.2892 | 1.2238 | **1.44x** | 2.39x | 1.21x |
| T2g CSR, C-gather | 0.5422 | 0.5848 | 0.3070 | 0.2345 | **4.02x** | 2.25x | 6.34x |
| T2 CSR, flat arrays | 0.5514 | 0.5662 | 0.3149 | 0.2359 | **3.95x** | 2.19x | 6.30x |
| **T3 + exact int build** | **0.3668** | 0.4001 | 0.1247 | 0.2414 | **5.94x** | 5.54x | 6.16x |
| T-anti numpy (Jacobi) | 0.2264 | 0.2355 | 0.1232 | 0.1025 | 9.62x | 5.61x | 14.49x but FAILS |

**CPython 3.12.6 (Windows) - cross-check:**

| tier | best (s) | build | iterate | speedup |
|---|---|---|---|---|
| T0 stock | 1.9496 | 0.4289 | 1.5189 | 1.00x |
| T1 | 1.6187 | 0.1946 | 1.4220 | 1.20x |
| T2g | 0.5657 | 0.2576 | 0.3071 | 3.45x |
| T2 | 0.4801 | 0.2566 | 0.2227 | 4.06x |
| **T3** | **0.3642** | 0.1456 | 0.2179 | **5.35x** |
| T-anti numpy | 0.2511 | 0.1396 | 0.1107 | 7.77x but FAILS |

Direction of the 3.10-vs-3.12 gap is as predicted: T3 is 5.94x on 3.10 and 5.35x on
3.12. 3.12/3.14 adaptive specialization already recovers part of the interpreter
overhead these tiers remove, so **local 3.12 numbers are a conservative lower bound
for the VM**; the 3.10 numbers are the ones to trust.

### 2.3 Phase split

| tier (3.10) | build | iterate | build share |
|---|---|---|---|
| T0 | 0.690 s | 1.486 s | 32 % |
| T1 | 0.289 s | 1.224 s | 19 % |
| T2 | 0.315 s | 0.236 s | 57 % |
| T3 | 0.125 s | 0.241 s | 34 % |

The ladder does what it should: T1/T3 attack the build phase (5.5x total), T2 attacks
the iterate phase (6.3x), and after T3 the two phases are back in balance - which is
exactly the point where handing the iterate phase to Rust becomes the next move.

### 2.4 The numpy anti-result, quantified

The obvious vectorization - `contrib = lo[col] * prb`,
`np.add.reduceat(contrib, row[:-1])` for chance nodes,
`np.maximum.reduceat(lo[col], row[:-1])` for choice nodes - reads the whole `lo` vector
as it stood at the *start* of the sweep. That is **Jacobi**, not Gauss-Seidel.
Measured consequence:

- sweeps 111 to **369** (3.3x), exactly matching the pure-Python Jacobi variant in 1.4
  (same 369 sweeps, same 0.898745194500 - independent confirmation)
- **fails the 1e-6 oracle**
- per sweep it *is* faster: 0.1025 s / 369 = 0.28 ms/sweep against 0.2414 s / 111 =
  2.17 ms/sweep for the pure-Python CSR loop (~7.8x per sweep at this size)

numpy wins on wall clock only by *not doing the benchmark's computation*. Forcing it to
preserve Gauss-Seidel would serialize it node by node, turning all 22 418 edges into
Python-level numpy calls. The cleanest "vectorization is not free - it changes the
recurrence" slide in the project.

---

## 3. Profiling

`perf` / flame graphs are deferred to the VM (`dev/ENVIRONMENT.md` has the working
WSL2 recipe; note `-e cpu-clock` is required, no hardware PMU, and 3.10 has no
`-X perf` trampoline so frames are C-level).

cProfile, CPython 3.10, one complete `evaluate(0.192)`, sorted by tottime.

**T0 stock** - top frames:

| ncalls | tottime | function |
|---|---|---|
| 1 | 0.778 | `solve` (the sweep loop body itself) |
| 2 018 493 | 0.594 | `<genexpr>` - the `dmin[s]*p` generator |
| 2 018 493 | 0.473 | `<genexpr>` - the `dmax[s]*p` generator |
| 360 471 | 0.409 | `fractions.py:_add` |
| 521 458 | 0.367 | builtin `sum` |
| 489 678 | 0.235 | `fractions.py:__new__` |
| 784 243 | 0.227 | `getSuccessors` |
| 378 890 | 0.128 | `fractions.py:forward` (operator dispatch) |
| 312 394 | 0.119 | builtin `max` |
| 3 659 | 0.105 | `getCritDist` |
| 386 946 + 386 946 | 0.159 | the two `max(...)` generators |

Four million generator-expression resumptions, half a million `sum()` calls, 784 k
`getSuccessors` calls and 360 k `Fraction` additions. Every one of those counts is
predicted exactly by the static analysis in section 0.

**T3 optimized** - top frames:

| ncalls | tottime | function |
|---|---|---|
| 1 | 0.442 | `sweep_flat` (all 111 sweeps, inlined) |
| 5 983 | 0.041 | `_applyActionSide1` |
| 54 430 | 0.031 | `applyHPChange` |
| 54 430 | 0.019 | `namedtuple._replace` |
| 1 | 0.014 | `topoSort` |
| 4 648 | 0.013 | `_applyActionPair` |
| 1 | 0.013 | `build_csr` |

Everything below the sweep loop has collapsed by one to two orders of magnitude. No
`Fraction` frame survives, no generator frame survives, no `sum`/`max` frame survives.
What is left is (a) the sweep loop, which is the irreducible 5 M multiply-accumulates,
and (b) `namedtuple._replace` in the build - the natural next target, and the reason
the Rust port would move the *build* phase second rather than first.

(cProfile inflates the interpreted tiers relative to the compiled-extension tiers, so
these numbers are for attribution only, never for the speedup claim.)

---

## 4. Rust / PyO3 design

Crate at `rust/mdp/`. The boundary is deliberately the *same* one the hardware
accelerator uses.

**One FFI call per `evaluate()`.** Python builds the graph - the part that needs
namedtuple state modelling and exact rational arithmetic - and exports the CSR arrays
that `t2_csr.build_csr()` / `t3_intexact.build_csr()` already produce:

| array | type | length | meaning |
|---|---|---|---|
| `kind` | u8 | n = 4823 | 0 = choice (max), 1 = chance (expectation) |
| `row` | i32 | n+1 | CSR row pointers |
| `col` | i32 | nnz = 22418 | successor index |
| `prb` | f64 | nnz | edge probability |
| `lo`, `hi` | f64 | n | the interval, in and out |
| `frz` | u8 | n | frozen flags, in and out |

Marshalling is one pass over ~27 k scalars - microseconds. The kernel then runs all 111
sweeps with **zero** Python interaction and returns `(lo[root], hi[root], sweeps)`.
`CSR.export()` in `t2_csr.py` is exactly that tuple.

**Four non-obvious correctness requirements the kernel must honour:**

1. Accumulate **naively, left to right** (`acc += lo[k] * p`). No pairwise summation,
   no FMA, no fast-math. Section 1.8 shows the trajectory is sensitive to summation
   order; a plain Rust loop matches CPython 3.10 `sum()` exactly.
2. Preserve the edge order the Python `sorted(dist.items(), key=(-p, key))` produced.
   The CSR export bakes it in; the kernel must not reorder.
3. Update **in place, in the given node order** (Gauss-Seidel). Do **not** parallelize
   across nodes - that silently becomes Jacobi and costs 3.3x the sweeps (section 2.4).
   This is the single most important line in the design: the obvious "make it
   parallel" move is precisely the one that breaks the benchmark.
4. Apply the freeze rule `if lo >= hi then lo = hi = (lo+hi)/2; frz = 1` at exactly the
   same point in the update, and drop frozen nodes from the active list at the end of
   the sweep, not mid-sweep.

**Expected gain.** 22 418 edges x 111 sweeps x 2 bounds is about 5.0 M
multiply-accumulates, plus 1162 x 111 x 2 comparisons, over ~300 KB of working set that
fits in L2. That is single-digit milliseconds in Rust against 0.24 s for the T3 Python
sweep and 1.49 s for stock. The iterate phase effectively vanishes and the residual is
the Python build phase (0.125 s at T3), giving a projected end-to-end **~10-15x from
stock**. Porting the build too - exact i64 numerators over the same fixed denominators,
no `num-rational` needed, since section 1.6 shows the denominators are static - is the
follow-on that would take it to ~50x.

**The narrative point for the slide:** the CSR export is not written *for* Rust. It is
written once and consumed by three things - the pure-Python T2/T3 sweep, the Rust
kernel, and the proposed accelerator's DMA descriptors. **The FFI boundary is the
MMIO/DMA interface.** `sweep_flat` in `t2_csr.py` is deliberately written as explicit
index loops rather than idiomatic Python precisely so that it reads as the behavioural
model of the datapath: a MAC pipeline for `kind == 1` rows, a comparator tree for
`kind == 0` rows, freeze logic on the writeback, and a convergence test on the root
interval driving the DONE interrupt. That one function is simultaneously the shipped
Python optimization, the Rust port's specification, and the Verilog testbench's golden
model.

---

## 5. Risk assessment - could a grader call this cheating?

Ranked most to least defensible.

1. **T2 integer renumbering + CSR - extremely defensible.** Every node is still visited
   every sweep, every edge still multiplied and accumulated, in the same order, with
   the same freeze rule. Whole-state-vector bit-identity, same 111 sweeps. This is
   "we changed the data structure, not the computation" in its purest form, and it is
   the single largest contributor to the speedup.
2. **T3 exact-integer arithmetic - extremely defensible.** The transition model is
   proven bit-identical edge by edge (section 1.6). "We replaced a general-purpose
   rational library with the specific fixed-denominator integers this problem actually
   needs" is textbook, and the denominators are demonstrably static. No approximation
   anywhere - this is *not* a float-for-rational substitution.
3. **T1 active list + single successor lookup - extremely defensible.** Removes work
   that provably has no effect (re-testing membership of a set that stops changing
   after sweep 1, and looking up the same list twice).
4. **T1 `lru_cache(getCritDist)` - defensible, but do not lead with it.** Caching a
   pure function is standard and the distributions are still computed. The one arguable
   angle is that a grader could claim the benchmark *intends* to measure that
   recomputation. It contributes only part of T1's 1.44x and none of T2/T3's win, so it
   is not load-bearing - say so explicitly rather than hiding it.
5. **T-anti numpy - would be cheating if shipped, and it fails the oracle anyway.**
   Its 9.6x is *entirely* an artifact of solving a different recurrence in 369 sweeps.
   Ship it as an analyzed negative result.
6. **T4 policy iteration - outright benchmark deletion.** Documented and rejected in
   section 1.2. Presenting it as *rejected*, with the measurement showing why, converts
   the biggest risk in this benchmark into its best slide.

The strongest defence available here is that `verify.py` checks far more than a grader
would: not the one asserted float, but **all 4823 states x 2 bounds, bit for bit, plus
all 22 418 transition probabilities, plus the sweep count**. Stock's own oracle checks
one number to 1e-6. Put that contrast in the report.

---

## 6. Recommendation: keep mdp? - **Yes. Keep it, and make it the lead benchmark.**

**Margin over the required 7 %: enormous and not in doubt.** T3 measures **5.94x on
3.10** - 83 % faster, against a 7 % bar. Even the single most conservative tier (T1
alone, 1.44x) clears the bar by more than 4x. There is no plausible re-measurement
outcome that drops this below 7 %; if two thirds of the measured gain evaporated we
would still be at 2x. And crucially we do not need the risky tiers to clear the bar -
the two *most* defensible tiers (T2 + T3) carry it alone.

**Presentation story: the best in the suite.** The hook - *"we solve a Gen-1 Pokemon
battle exactly, as a Markov decision process"* - lands instantly with a room of ECE
students, and it escalates through four genuinely interesting beats:

1. profile - two clean phases (exact rational graph build, float value iteration),
   with a cProfile table where four million generator frames jump off the slide
2. the data-structure win - *why does hashing a tuple five million times cost 6x?*
   CPython does not cache tuple hashes: a real, teachable fact with a 6.3x attached
3. the exact-arithmetic win - *all of these denominators are known before the program
   runs*, so `Fraction` is doing gcd work that provably cannot change any answer
4. **the twist** - *we implemented the textbook better algorithm, policy iteration. It
   converges in 5 rounds instead of 111 sweeps. It tells us Charmeleon really wins
   80.3 % of the time. And it fails the benchmark - because the benchmark's answer is
   not the win probability, it is a bracket midpoint after a fixed amount of work.*

Beat 4 is a real insight about benchmarking, found by measurement, with a number
attached (96 000x the oracle) and an independent cross-check (the lower bound converges
onto the policy-iteration answer to 4e-11). That is what gets remembered in Q and A.
The numpy anti-result is a second, smaller version of the same lesson. No other
benchmark in the suite offers this.

**Hardware-accelerator story: strong and unusually concrete.** A CSR value-iteration
MAC engine - DMA the six arrays, pipelined multiply-accumulate for `kind == 1` rows,
comparator tree for `kind == 0` rows, freeze logic on writeback, convergence check on
the root interval, DONE interrupt - is a textbook student Verilog design (FSM + BRAM +
one MAC + comparator), and the whole graph is ~300 KB so it fits on-chip. The trade-off
discussion writes itself: MAC width vs area, fixed-point vs FP64 precision against a
1e-6 result check, on-chip BRAM vs streaming, and a hard *no* on node-level parallelism
with a measured 3.3x justification. And the Python CSR export, the Rust FFI boundary
and the accelerator's DMA descriptors are **the same interface** - one artifact, three
consumers, with `sweep_flat` as the per-sweep golden model for the testbench.

**Implementation risk: low.** The ladder is written, verified and measured; the landed
tier is a readable ~120-line diff against stock. The Rust kernel is ~80 lines of
straight-line array code with four documented correctness constraints. The WSL2
environment has Rust 1.98 + maturin 1.15 verified end to end producing cp310
manylinux_2_34 wheels, which the VM's glibc 2.35 accepts. The only genuine subtlety is
the summation-order dependency in section 1.8, now documented and covered by a test.

**The one caveat to state honestly in the report:** mdp's oracle constrains
optimization more tightly than the other benchmarks' do - it pins the iteration
trajectory, not just the answer. That is a feature for defensibility (we can *prove*
bit-identity, which no other benchmark here lets us do) and a constraint on ambition
(no algorithmic speedups are legal). Say it out loud rather than letting a grader find
it.

---

## 7. What was landed

`benchmarks/bm_mdp/run_benchmark.py` ships **T3**: memoized `getCritDist`, exact
fixed-denominator integer arithmetic in place of `fractions.Fraction`, integer state
renumbering after `topoSort`, CSR flat arrays, and the flat-array Gauss-Seidel sweep
with an active list. `[tool.pyperformance] name = "mdp"`, the pyperf `Runner`
structure and the `0.89873589887 +/- 1e-6` assertion are untouched.
