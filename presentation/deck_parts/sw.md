# Deck spec, software slides (owner M)

Drafted 2026-09-26 from the shipped reports. Format: `presentation/STRATEGY.md` "Spec format".
Every number is cited to `file:line`; `tools/presentation/check_numbers.py` verifies the quotes.

## S01 · Two pure-Python pyperformance workloads, one question: where does the time go, and what would it take to move it to hardware?
- owner: M
- status: DRAFT
- stage: Analyze
- seconds: 90
- visual: table

table:
| Tier | nbody | pyflate |
|---|---|---|
| Original Python (pyperformance) | 231.20 ms, 1.00x | 1,123.49 ms, 1.00x |
| Optimized Python (pyperformance) | 143.13 ms, 1.62x | 281.16 ms, 4.00x |
| Python + Rust (direct pyperf) | 9.530 ms, 24.26x vs original | 170.01 ms, 6.61x vs original |

notes:
Both workloads ship in pyperformance and are pure Python: nbody integrates five bodies for 20,000 steps, pyflate decompresses a 67,562-byte bzip2 file into 399,360 bytes. The course question is where the time goes and what it would take to move that work into hardware. This table is the whole software result, measured on the course VM with 120 pyperf values per configuration, pinned to one guest CPU. Two routes produced it, with different denominators. Original versus optimized ran through pyperformance: 231.20 to 143.13 ms for nbody, 1.62x, and 1,123.49 to 281.16 ms for pyflate, 4.00x. The Rust tiers ran under direct pyperf against the same file's Python back end, so nbody's kernel ratio of 15.25x sits on a 145.30 ms denominator; against the original it is 24.26x. pyflate's Rust decoder reaches 170.01 ms, 6.61x. Every later slide names its denominator.

sources:
- 231.20 ± 7.85 ms → report_nbody.txt:160
- 1.00× → report_nbody.txt:160
- 143.13 ± 1.56 ms → report_nbody.txt:161
- 1.62× → report_nbody.txt:161
- 9.530 ± 0.050 ms → report_nbody.txt:189
- 15.25× → report_nbody.txt:189
- native is 24.26× → report_nbody.txt:191
- 145.30 ± 4.97 ms → report_nbody.txt:188
- Both use direct pyperf; the original-vs-optimized comparison above uses pyperformance → report_nbody.txt:190-191
- 120 measured values per configuration → report_nbody.txt:168
- 1,123.49 ± 10.99 ms → report_pyflate.txt:48
- 281.16 ± 3.05 ms → report_pyflate.txt:49
- 4.00× → report_pyflate.txt:49
- 170.01 ± 2.30 ms → report_pyflate.txt:50
- 6.61× → report_pyflate.txt:50
- 67,562 bytes to 399,360 bytes → report_pyflate.txt:16
- 20,000 steps → report_nbody.txt:33

## S02 · nbody is 5 bodies, 10 pairs and 20,000 steps of pure-Python float arithmetic
- owner: M
- status: DRAFT
- stage: Analyze
- seconds: 45
- visual: assets/nbody_pairs.png

notes:
The state is the Sun and four gas giants: 35 Python floats in nested lists, a position, a velocity and a mass per body. pairs is a list of ten tuples aliasing those same lists, built once. One timed iteration evaluates the energy, calls advance(0.01, 20000), and evaluates the energy again. Every step visits the same ten pairs, forms dx, dy and dz, computes mag = dt * (dsq ** -1.5) and updates both bodies' velocities in place. Ten pairs times 20,000 steps is 200,000 pair-force evaluations, and between every one of them sits the interpreter. The physics is compact; the machinery around each calculation is what we go looking for.

sources:
- 5, 10 and 31 bodies → report_nbody.txt:183
- 10 pairs → report_nbody.txt:24
- Ten fixed pairs × 20,000 steps = 200,000 pair-force evaluations → report_nbody.txt:33
- 35 Python floats → report_nbody.txt:20
- advance(0.01, 20000) → report_nbody.txt:15
- dt * (dsq ** -1.5) → report_nbody.txt:147

## S03 · 97.7% of samples sit in advance(); list indexing and float boxing dominate the C frames
- owner: M
- status: DRAFT
- stage: Profile
- seconds: 60
- visual: assets/print_nbody_stock.png

notes:
Two profilers, two views. py-spy on release CPython puts 97.7% of 310 samples in advance(); everything else is start-up and imports. perf at 999 Hz on the debug build shows what the interpreter does inside it: one tower under _PyEval_EvalFrameDefault at 99.31% inclusive, with binary_op1, the generic arithmetic dispatch, at 20.07%, float object handling at 16.25% of self time and list access and index conversion at 11.26%. There is no second hotspot. The list traffic is the part pure Python can remove: the per-pair unpacking and the read-modify-write of each velocity list. The float boxing it cannot remove, because every operation still allocates a Python float. Debug-build percentages locate the costs; release-build timing establishes the benefit.

sources:
- advance holds 97.7% of samples before (310 samples) → report_nbody.txt:116
- 999 Hz cpu-clock → report_nbody.txt:47
- _PyEval_EvalFrameDefault (99.31% inclusive) with binary_op1 (20.07%) → report_nbody.txt:114-115
- 16.25% → report_nbody.txt:58
- 11.26% → report_nbody.txt:59
- These debug-build percentages locate costs to investigate; release-build timing establishes the optimization’s benefit → report_nbody.txt:48-49

## S04 · Specializing advance() to the fixed pair list removes the list traffic: 231.20 → 143.13 ms, 1.62x, bit-identical state
- owner: M
- status: DRAFT
- stage: Optimize
- seconds: 60
- visual: assets/print_nbody_opt.png

notes:
At import time we emit an advance() with the pair loop unrolled, coordinates in locals and masses as literals; state is loaded before the step loop and written back afterwards, so energy still observes the original body objects. The arithmetic is untouched: mag = dt * (dsq ** -1.5) in the same order, so final state and energy compare exactly equal after 20,000 steps, not merely within a tolerance. Under pyperformance the run goes from 231.20 ± 7.85 to 143.13 ± 1.56 ms, 1.62x, 38.1% less time; the 88.1 ms reduction is about 70 times the clustered standard error. The optimized profile confirms the mechanism: list access and index conversion fall from 11.26% to 0.06% of self time, float handling does not fall, and advance() still holds 91.4% of 210 samples. That residue is what the native tier removes.

sources:
- 231.20 ± 7.85 ms → report_nbody.txt:160
- 143.13 ± 1.56 ms → report_nbody.txt:161
- 1.62× → report_nbody.txt:161
- reduces runtime by 38.1% → report_nbody.txt:162
- the 88.1 ms reduction is about 70 times the combined clustered standard error → report_nbody.txt:178-179
- fall from 11.26% to 0.06% → report_nbody.txt:65
- 91.4% after (210 samples) → report_nbody.txt:116
- dt * (dsq ** -1.5) → report_nbody.txt:147
- 20,000 steps → report_nbody.txt:33

## S05 · Struct-of-arrays and NumPy lose at N = 5; only leaving Python wins: the Rust tier runs in 9.530 ms
- owner: M
- status: DRAFT
- stage: Optimize
- seconds: 60
- visual: table

table:
| Variant | Result | Denominator | Evidence |
|---|---|---|---|
| Struct-of-arrays (development) | 0.88x | original's speed | development host, not the VM |
| NumPy (development) | 0.35–0.46x | original's speed | development host, not the VM |
| Barnes-Hut at N = 5 | 3.92x slower (0.077 vs 0.020 ms) | direct summation | VM force sweep |
| Native Rust, 9.530 ms | 15.25x | optimized Python under direct pyperf, 145.30 ms | VM canonical run |
| Native Rust, 9.530 ms | 24.26x | original under pyperformance, 231.20 ms | VM canonical run |

notes:
Before leaving Python we tried the obvious alternatives, and at ten pairs they lose. A struct-of-arrays layout runs at 0.88x of the original's speed and NumPy at 0.35–0.46x: array setup and per-call overhead exceed the work. Barnes-Hut is 3.92x slower at N = 5 in the VM force sweep, 0.077 against 0.020 ms; it only crosses over near N = 300, which is a backup slide. What wins is leaving the interpreter. The Rust/PyO3 System runs all 20,000 steps and both energy evaluations in one call, 9.530 ± 0.050 ms, bit-identical in state and energy at 5, 10 and 31 bodies. Watch the denominators: 15.25x is against the same file's Python back end under direct pyperf, 145.30 ms; against the pyperformance original of 231.20 ms it is 24.26x. The two ratios must not be multiplied.

sources:
- 0.88× and 0.35–0.46× → report_nbody.txt:223-224
- 3.92× slower → report_nbody.txt:222
- 0.020 ms 0.077 ms 3.92× → report_nbody.txt:232
- near N = 300 → report_nbody.txt:237
- 9.530 ± 0.050 ms → report_nbody.txt:189
- 15.25× → report_nbody.txt:189
- 145.30 ± 4.97 ms → report_nbody.txt:188
- native is 24.26× → report_nbody.txt:191
- Different Python denominators prevent multiplying the two reported ratios → report_nbody.txt:192
- 231.20 ± 7.85 ms → report_nbody.txt:160
- 5, 10 and 31 bodies → report_nbody.txt:183
- 20,000 steps → report_nbody.txt:33

## S06 · Native runs 26.7x fewer instructions while IPC drops from 3.28 to 1.83: the win is instruction count, not the pipeline
- owner: M
- status: DRAFT
- stage: Optimize
- seconds: 45
- visual: table

table:
| Per iteration | Optimized Python | Native Rust | Ratio |
|---|---|---|---|
| Elapsed time | 141.08 ms | 9.462 ms | |
| Instructions | 1,103.62 M | 41.32 M | 26.7x fewer |
| Cycles | 336.24 M | 22.55 M | 14.9x fewer |
| IPC | 3.28 | 1.83 | lower |
| Branches | 185.97 M | 3.92 M | |

notes:
This is a separate pinned warm-loop experiment, 64 iterations per run, medians of three runs, user-mode counters only. Native retires 26.7x fewer instructions and 14.9x fewer cycles, yet its IPC falls from 3.28 to 1.83. That is not a contradiction: runtime is cycles over clock, and IPC counts retired instructions, not useful force updates. Interpreter bookkeeping pipelines beautifully and is still work. Cache misses are 59.6 against 2.5 per iteration, far too few to matter. So nbody's cost was instruction count from the interpreter, not the memory system and not the pipeline, which is the fact the hardware half has to live with: there is no memory stall for an accelerator to hide.

sources:
- 141.08 ms 9.462 ms → report_nbody.txt:207
- 1,103.62 M 41.32 M → report_nbody.txt:208
- 336.24 M 22.55 M → report_nbody.txt:209
- 3.28 1.83 → report_nbody.txt:210
- 185.97 M 3.92 M → report_nbody.txt:211
- Native needs 26.7× fewer instructions and 14.9× fewer cycles → report_nbody.txt:215
- repeats the work 64 times per run → report_nbody.txt:195
- 59.6 (2.245%) 2.5 (1.134%) → report_nbody.txt:214

## S13 · pyflate is bzip2 decompression in pure Python: Huffman decode, move-to-front, run-length, inverse BWT
- owner: M
- status: DRAFT
- stage: Analyze
- seconds: 45
- visual: assets/pyflate_stages.png

notes:
Despite its name, the measured fixture is bzip2, not DEFLATE: interpreter.tar.bz2 expands from 67,562 bytes to 399,360 bytes, and the MD5 check sits outside the timer. One block, six Huffman tables, 148,271 symbols, with a table switch every 50 symbols. The symbol loop, which is the bit reader, Huffman decode, move-to-front and RUNA/RUNB expansion, produces the 336,184-byte L-vector, the last column of the BWT matrix. Inverse BWT and RLE4, where four equal bytes and a count k stand for 4 + k copies, produce the output. Only the standard library is used. Keep this boundary in mind: the Rust kernel and both accelerators take exactly the symbol loop and leave the rest in Python.

sources:
- 67,562 bytes to 399,360 bytes → report_pyflate.txt:16
- One block, six Huffman tables, 148,271 symbols. The decoder switches tables every 50 symbols → report_pyflate.txt:26
- a 336,184-byte L-vector → report_pyflate.txt:28
- 4 + k copies → report_pyflate.txt:30

## S14 · A canonical Huffman code is decoded by comparing the next bits against one threshold per length
- owner: M
- status: DRAFT
- stage: Analyze
- seconds: 30
- visual: assets/huffman_tree.png

notes:
With code lengths [2,2,2,3,3] the canonical codes are 00, 01, 10 for a, b, c and 110, 111 for d, e: codes of one length are consecutive integers, so each length has a limit and a base. Decode 01110: peek 01, emit b, consume two bits. Peek 11, above the length-2 range, so extend to 110 = 6, at or below limit[3] = 7; base[3] = 3, so perm[3] = d. Nothing is scanned. The original matcher visited about 5.0 entries per symbol out of 258, which is why the table alone was not the whole win.

sources:
- code lengths [2,2,2,3,3] → report_pyflate.txt:244
- On input 01110, peek 01, output b and consume two bits; 110 remains → report_pyflate.txt:246
- Now code 6 lies at or below limit[3] = 7; base[3] = 3 → report_pyflate.txt:247
- e = 111 → report_pyflate.txt:238
- mean scan length 5.0 entries → report_pyflate.txt:85
- table capacity of 258 → report_pyflate.txt:84

## S15 · 40.86% of the original samples are Huffman symbol decode, 13.44% move-to-front, and about a quarter is the bit reader
- owner: M
- status: DRAFT
- stage: Profile
- seconds: 60
- visual: assets/print_pyflate_stock.png

notes:
Two profilers answer two questions. perf on the debug build says the interpreter sits in _PyEval_EvalFrameDefault at 99.50% inclusive, but it cannot name a Python function. py-spy on release CPython can, from 372 samples: find_next_symbol, the Huffman matcher, is 40.86% inclusive; move_to_front 13.44%; the bit-reader functions snoopbits, readbits and _mask are 9.41%, 9.95% and 5.91% of self time, together about a quarter; bwt_reverse is 14.52% inclusive. The surprise is that the matcher visits only 5.0 entries on average out of 258, so a lookup table cannot be the whole answer. The C-frame view explains the rest: a quarter of the time allocates and frees objects, a per-byte int and a list slice per symbol, and 9.45% is call machinery. These are sparse profiles: a 1% cell is one to four samples.

sources:
- _PyEval_EvalFrameDefault 99.50% inclusive → report_pyflate.txt:78
- 372 samples → report_pyflate.txt:87
- find_next_symbol (run_benchmark.py) 40.86% 12.63% → report_pyflate.txt:91
- move_to_front (run_benchmark.py) 13.44% 13.44% → report_pyflate.txt:90
- readbits (run_benchmark.py) 13.44% 9.95% → report_pyflate.txt:92
- snoopbits (run_benchmark.py) 16.13% 9.41% → report_pyflate.txt:93
- bwt_reverse (run_benchmark.py) 14.52% 8.33% → report_pyflate.txt:94
- _mask (run_benchmark.py) 5.91% 5.91% → report_pyflate.txt:96
- mean scan length 5.0 entries → report_pyflate.txt:85
- table capacity of 258 → report_pyflate.txt:84
- spends a quarter of its time allocating and freeing → report_pyflate.txt:146
- 9.45% → report_pyflate.txt:144
- a 1% cell is one to four samples → report_pyflate.txt:123

## S16 · Three optimizations, each measured by reverting it, take pyflate from 1,123.49 ms to 281.16 ms, 4.00x
- owner: M
- status: DRAFT
- stage: Optimize
- seconds: 75
- visual: table

table:
| Reverted from the shipped decoder (T3) | VM trial 1 | VM trial 2 |
|---|---|---|
| None (full T3 runtime) | 271.2 ms | 273.9 ms |
| Regex-assisted RLE4 | +100.6 ms | +98.7 ms |
| Primary Huffman lookup | +52.6 ms | +49.4 ms |
| Counting-sort BWT | +20.8 ms | +17.2 ms |
| All reverted (T1 only) | +393.6 ms | +397.2 ms |

notes:
Three changes shipped on top of the per-byte fixes: a flat primary lookup table for Huffman codes with a canonical fallback, regex-assisted RLE4 so the run scan happens in C, and counting-sort construction of the BWT traversal table. To attribute the gain we revert one change at a time and time best-of-seven interleaved decompressions on the VM; the two trials agree within 4 ms on every row. RLE4 is worth about 100 ms, the lookup about 50 ms, the BWT sort about 20 ms. Costs need not add, and the development interpreter ranked them the other way round, so measure on the platform you report. End to end under pyperformance: 1,123.49 ± 10.99 to 281.16 ± 3.05 ms, 4.00x, 75.0% less time, byte-exact against bz2.decompress. The ablation drives the module directly, so its 271.2 ms is not 281.16 ms.

sources:
- None (full T3 runtime) 271.2 ms 273.9 ms → report_pyflate.txt:164
- Regex-assisted RLE4 +100.6 ms +98.7 ms → report_pyflate.txt:165
- Primary Huffman lookup +52.6 ms +49.4 ms → report_pyflate.txt:166
- Counting-sort BWT +20.8 ms +17.2 ms → report_pyflate.txt:167
- All reverted (T1 only) +393.6 ms +397.2 ms → report_pyflate.txt:168
- best of seven → report_pyflate.txt:177
- worth about 100 ms and the primary Huffman lookup about 50 ms → report_pyflate.txt:182
- about 20 ms – and the two trials agree within 4 ms on every row → report_pyflate.txt:183
- 1,123.49 ± 10.99 ms → report_pyflate.txt:48
- 281.16 ± 3.05 ms → report_pyflate.txt:49
- 4.00× → report_pyflate.txt:49
- The Python tier alone cuts 75.0% → README.md:46

## S17 · After optimization inverse BWT is about 80% of what remains; a Rust kernel for symbol decode reaches 170.01 ms, 6.61x end to end
- owner: M
- status: DRAFT
- stage: Optimize
- seconds: 90
- visual: assets/print_pyflate_opt.png

notes:
After the Python work the profile changes shape. From 122 samples, _decode_symbols_python, the loop that replaced the matcher, is 32.79% self; inverse BWT is 38.52% inclusive and rle4_expand 5.74%. The Rust/PyO3 BlockDecoder takes that symbol loop in one call per block; headers, inverse BWT, RLE4 and MD5 stay in Python. Under direct pyperf that is 283.88 ± 3.34 to 170.01 ± 2.30 ms, 1.67x; against the original, 6.61x and 84.9% less time. The kernel itself takes 3.304 ms per decode where the Python loop took about 117 ms. What remains is inverse BWT: 137.7 ms for the whole transform, about 80% of the remaining time; the traversal alone is 47.8 ms, never add the two. Caveat: a 32.79% share would cap the gain at 1.49x, below the measured 1.67x, so 122 samples locate work but do not calibrate Amdahl.

sources:
- 122 samples → report_pyflate.txt:187
- _decode_symbols_python (run_benchmark.py) 32.79% 32.79% → report_pyflate.txt:189
- bwt_transform (run_benchmark.py) 25.41% 25.41% → report_pyflate.txt:190
- bwt_reverse (run_benchmark.py) 38.52% 13.11% → report_pyflate.txt:191
- rle4_expand (run_benchmark.py) 5.74% 5.74% → report_pyflate.txt:192
- 283.88 ± 3.34 ms → report_pyflate.txt:272
- 170.01 ± 2.30 ms 1.67× → report_pyflate.txt:273
- 6.61× → report_pyflate.txt:50
- an 84.9% runtime reduction → report_pyflate.txt:51
- reports 3.304 ms per → report_pyflate.txt:450
- ≈ 117 ms → report_pyflate.txt:461
- inverse BWT (137.7 ms, about 80%) sets the floor → report_pyflate.txt:477
- the traversal alone measured 47.8 ms against 137.7 ms → report_pyflate.txt:488
- 1.49× gain, below the measured 1.67× → report_pyflate.txt:315

## S26 · What we learned: measure the KPI on the full-shape workload early, and the next experiment is a native inverse BWT and a timing confirmation run
- owner: M+Y
- status: DRAFT
- stage: Trade-offs
- seconds: 60
- visual: table

table:
| Lesson or next step | Where it came from |
|---|---|
| Lesson: measure the KPI on the full-shape workload at bring-up | grape read 162 cycles per step at sign-off; the fix landed at 124 |
| Lesson: removing the interpreter and building a fast datapath are different problems | software took almost all of nbody's gain; the accelerator ties optimized Python |
| Lesson: the platform you report on decides the ranking | the pyflate ablation ordered its three changes one way on the dev machine, the other on the VM |
| Next: a native inverse BWT with an isolated timer and a working-set sweep | 137.7 ms is the floor for both the Rust and the hardware route |
| Next: matched phase timing and a routed timing run | the residuals are assumptions; the clocks are post-CTS estimates |

notes:
Three things we would tell ourselves at the start. First, measure the KPI on the full-shape workload at bring-up: grape read 162 cycles per step at sign-off after every earlier gate was green, because the smoke test used two pairs; the fix landed at 124. Second, removing interpreter overhead and building a fast physical datapath are different problems: software captured almost all of nbody's gain, and the accelerator ties optimized Python. Third, the platform you report on decides the ranking: the pyflate ablation ordered its three changes differently on the development machine and on the VM. Two next experiments: a native inverse BWT with an isolated timer and a working-set sweep, because its 137.7 ms is the floor for both routes; and matched phase timing plus a routed timing run, replacing assumed residuals, post-CTS clocks and the unmeasured interface time.

sources:
- K1 measured 162 cycles/step at sign-off after → hw/docs/lessons.md:212
- landed K1 at 124 → hw/docs/lessons.md:216-217
- measure the KPI on the full-shape workload (all pairs) at bring-up → hw/docs/lessons.md:217-218
- removing interpreter overhead and building a fast physical datapath are different problems → report/defense_guide.md:318-319
- level with the optimized Python tier → report_nbody.txt:384-385
- The development run on 3.12 had ranked BWT first and the Huffman table last, so the ordering depends on the interpreter and platform → report_pyflate.txt:183-185
- inverse BWT (137.7 ms, about 80%) sets the floor for both the native and the hardware route → report_pyflate.txt:477
- A native port and working-set sweep would test whether memory latency then becomes limiting → report_pyflate.txt:324
- Matched phase timing, whole native BWT, physical timing follow-up → report/defense_guide.md:30
- residual is an assumption, not a matched phase measurement → report_nbody.txt:366

## B11 · Every headline is 120 pyperf values on the course VM, and the ± is spread, not a confidence interval
- owner: M
- status: DRAFT
- stage: Optimize
- visual: table
- answers: Q16, Q17, G10

table:
| Item | What it is | Value |
|---|---|---|
| Route A: pyperformance run, rigorous | original vs optimized, same benchmark name | 231.20 → 143.13 ms; 1,123.49 → 281.16 ms |
| Route B: direct pyperf | Python back end vs Rust of the same file, HWSW_BACKEND the only change | 145.30 → 9.530 ms; 283.88 → 170.01 ms |
| Values per JSON | 40 worker processes, three values each | 120 values, pinned to guest CPU 0 |
| ± in every table | sample standard deviation, not a confidence interval | effective n 40.2 and 41.8 for nbody original and optimized |
| Timed revision | 2c8c754, the canonical run | later commits pass the same oracles but were not re-timed |
| Hash names under results/ | pre-rewrite ids, kept as the historical record | 2c8c754 is 69b6bd5 after the rewrite |

notes:
Every headline came from the course VM, Ubuntu 22.04, release CPython, pyperf in rigorous mode, every timed run pinned to guest CPU 0, from one canonical run of revision 2c8c754. Two routes. Original versus optimized goes through pyperformance, which builds its own environment and therefore cannot see our wheel; Python back end versus Rust runs the same benchmark file directly under pyperf with only HWSW_BACKEND changed, and native mode fails rather than falls back. Each JSON holds 120 values, 40 worker processes times three values, and the ± is the sample standard deviation across them, not a confidence interval. Values from one worker are correlated: the intraclass correlation is 0.994 for the nbody original, so the effective sample size is about 40.2 and 41.8 for nbody's original and optimized runs. The reductions are still tens of standard errors. Commits after the timed revision were not re-timed: nbody removed a dead store from the generated advance() and widened the optional-import fallback; pyflate trimmed comments, moved the BWT histogram to collections.Counter and lowered the Rust code-length cap from 23 to 20. All pass the same exactness oracles, and results/vm_verify_20260921_f407567 re-ran the correctness checks on the VM at the submitted revision. Directory names under results/ keep the pre-rewrite commit ids: 2c8c754 is 69b6bd5 after the history rewrite, and the mapping is in docs/history-rewrite.md.

sources:
- Ubuntu 22.04 → report_nbody.txt:167
- 120 measured values per configuration (40 value-bearing worker → report_nbody.txt:168
- 231.20 143.13 1.62× → report_appendix.txt:241
- 145.30 9.530 15.25× → report_appendix.txt:242
- 1,123.49 281.16 4.00× → report_appendix.txt:243
- 283.88 170.01 1.67× → report_appendix.txt:244
- baseline_nbody 7.899 0.602 0.994 → report_appendix.txt:185
- 40.2 and 41.8 for → report_appendix.txt:194
- mean ± SD describes the observed mean and spread; it does not require symmetry or independence and is not a confidence interval → report_appendix.txt:157-158
- A later commit removed a dead store from the generated advance() and widened the optional-import fallback → report_nbody.txt:172-173
- Later commits trimmed comments, moved the BWT histogram to collections.Counter and lowered the Rust code-length cap from 23 to 20; they pass the same byte-exact checks but were not re-timed → report_pyflate.txt:68-70
- records all eleven on the same VM at the → report_pyflate.txt:285
- which builds its own venv that has no extension wheel in it → README.md:187-188
- The IDs refer to the → docs/history-rewrite.md:28
- the canonical timing run | `2c8c754` | `69b6bd5` → docs/history-rewrite.md:32

## B12 · Barnes-Hut crosses over near N = 300, far above the benchmark's N = 5; grape's cost per pair falls with the pair count
- owner: M
- status: DRAFT
- stage: Trade-offs
- visual: table
- answers: Q7, Q3

table:
| N | Direct | Barnes-Hut | BH / direct |
|---|---|---|---|
| 5 | 0.020 ms | 0.077 ms | 3.92x |
| 100 | 4.746 ms | 8.410 ms | 1.77x |
| 300 | 42.977 ms | 42.489 ms | 0.99x |
| 800 | 313.489 ms | 158.846 ms | 0.51x |
| 1,600 | 1,254.660 ms | 382.471 ms | 0.30x |

notes:
Section 5 of the nbody report extends the workload beyond the required N = 5. It is a pure-Python force-evaluation sweep on the VM with the Barnes-Hut tree rebuilt at each evaluation, θ = 0.5, best of seven; it is not the full integration benchmark. At five bodies the tree costs 3.92x more than direct summation; the crossover is near N = 300 for this distribution of near-coplanar circular orbits, and the median acceleration error is not a worst-case or trajectory bound. Native Rust stays 21–22x over rolled Python from N = 100 to 3,200. The specialized generator grows as O(N²) in source size and falls back to the rolled pair loop above 20,000 pairs. On the hardware side, grape is latency-bound at N = 5: 12.3 cycles per pair in the model, 12.4 measured, falling to about 4.4 cycles per pair at N = 100 as the pipelined units fill; but above N ≈ 300 the software competitor becomes Barnes-Hut rather than direct summation, so the comparison has to change too.

sources:
- 5 0.020 ms 0.077 ms 3.92× → report_nbody.txt:232
- 100 4.746 ms 8.410 ms 1.77× → report_nbody.txt:233
- 300 42.977 ms 42.489 ms 0.99× → report_nbody.txt:234
- 800 313.489 ms 158.846 ms 0.51× → report_nbody.txt:235
- 1,600 1,254.660 ms 382.471 ms 0.30× → report_nbody.txt:236
- θ = 0.5, best of seven → report_nbody.txt:229-230
- The crossover is near N = 300 for this distribution (near-coplanar circular orbits → report_nbody.txt:237
- 21–22× over rolled Python at N = 100–3,200 → report_nbody.txt:238-239
- falls back to the ordinary (rolled) pair loop above 20,000 → report_nbody.txt:225
- the step costs 12.3 cycles per pair in the model (12.4 measured) → report_nbody.txt:398-399
- about 4.4 cycles per pair → report_nbody.txt:400
- above N ≈ 300 the software competitor becomes Barnes-Hut → report_nbody.txt:414
