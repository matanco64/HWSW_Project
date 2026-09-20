# HWSW project defense guide

Prepared 2026-09-15 from the current reports and recorded repository evidence.
This is rehearsal material, not a record of new VM benchmarks or RTL/physical runs.

## The story in 45 seconds

“We studied two Python workloads with very different structures. Nbody repeatedly
executes ten fixed body interactions, so specializing its schedule reduced Python
runtime by 38.1%. Pyflate decodes a bzip2 block through several transformations;
optimizing the whole pipeline gave 4.00x, and moving symbol decoding into Rust gave
6.61x over original. Correctness checks constrain both transformations. Our hardware
implements the same offload boundaries and is verified bit- and byte-exactly, but it
does not beat native Rust: clock frequency, area, residual software and communication
matter, not simulation cycles alone.
The project demonstrates both where offload helps and where its costs limit it.”

## A 23-minute presentation route

| Time | Explain | Show |
|---|---|---|
| 0:00–1:30 | Workloads, assignment and central question | One table of canonical runtimes; name each baseline. |
| 1:30–5:00 | Nbody state, ten pairs, profiling and specialization | Actual before/after excerpt, exactness contract. |
| 5:00–7:00 | Native nbody and scaling | Instructions versus IPC; Barnes–Hut crossover caveat. |
| 7:00–11:30 | Bzip2 pipeline and transformations | Huffman 01110 example, banana pointer table, reversed MTF. |
| 11:30–14:00 | Pyflate ablation, native boundary and residual | VM ablation and canonical Python/native comparison. |
| 14:00–18:00 | Nbody HDL architecture and physical cost | Pair dependency diagram, 124 cycles, area trade-off, 19.46 MHz estimate. |
| 18:00–21:00 | Huffman/MTF hardware and interface | AXI diagram, separate evidence levels, software residual and DMA assumptions. |
| 21:00–22:00 | Demonstrate correctness | Run the short checked examples; show prepared VM/RTL logs if asked. |
| 22:00–23:00 | Conclusions and next experiment | Matched phase timing, whole native BWT, physical timing follow-up. |

For 20 minutes, shorten the large-N discussion and show only the Huffman worked
example live. For 25 minutes, add the MTF width/area study and a timing sensitivity
calculation. Leave the required 5–10 minute discussion outside this presentation time.

## Numbers to know, with the denominator attached

| Comparison | Before → after | Result |
|---|---|---|
| Nbody original → optimized Python, pyperformance route | 231.20 → 143.13 ms | 1.62x, 38.1% less time |
| Nbody optimized Python → Rust, direct pyperf route | 145.30 → 9.530 ms | 15.25x |
| Pyflate original → optimized Python | 1123.49 → 281.16 ms | 4.00x |
| Pyflate optimized Python → Python + Rust extension, direct pyperf route | 283.88 → 170.01 ms | 1.67x |
| Pyflate original → Python + Rust extension | 1123.49 → 170.01 ms | 6.61x, 84.9% less time |
| Nbody RTL simulation | 124 cycles/step × 20,000 | 2.48 million cycles |
| Nbody compute projection | 2.48 Mcycles / 19.46 MHz | 127.4 ms, before residual and interface |
| Huffman module simulation | 149,276 cycles / 148,271 symbols | 1.0068 cycles/symbol |
| MTF module simulation | 158,441 cycles / 148,271 symbols | 1.0686 cycles/symbol |
| Huffman + MTF chain simulation | 159,303 cycles, 336,184 bytes byte-exact | ≈ 4.24 ms at the shared 37.6 MHz clock |
| Post-CTS timing estimates | grape 19.46, Huffman 39.9, MTF 37.6 MHz | none has met the 50 MHz target |
| Nbody hardware projection | 127.4 ms compute + 11.6 ms residual | ≈ 139 ms: 1.66x vs original, ≈ 15x slower than Rust |

Sources: [canonical suite](../results/vm_canonical_20260910_2c8c754/suite/),
[grape PPA](../hw/grape_pipeline/docs/ppa.md),
[Huffman integration](../hw/huffman_engine/docs/integration.md),
[MTF integration](../hw/mtf_cam/docs/integration.md).

## Likely questions and answers

### 1. What does nbody actually time?

**Short answer:** Energy, 20,000 integration steps with dt=0.01, then energy again.
There are five bodies and ten unordered pairs, or 200,000 pair-force evaluations.

**If pressed:** Position, velocity and mass give 35 float state values. We use the
same arithmetic order as original. This is a small direct Newtonian-gravity benchmark,
not a validated spacecraft-navigation application; the opening story is motivation.

**Evidence:** [benchmark](../benchmarks/bm_nbody/run_benchmark.py),
[original oracle](../dev/nbody/t0_stock.py).

### 2. Why is unrolling faster if the arithmetic is unchanged?

**Short answer:** It removes repeated pair unpacking, list access and velocity
list updates from the step loop, while keeping state in local variables.

**If pressed:** The function is generated once for the fixed schedule. Positions
and velocities are loaded before all steps and written back afterward. Masses are
literals. Local Python arithmetic still creates/manages Python floats; this is why
native execution can remove far more work. Import-time generation is outside the
steady-state benchmark and can be expensive at large N.

**Evidence:** `_advance_source` in the benchmark; run `python3 report/verify_examples.py`.

### 3. Is specialization cheating or just hard-coding the answer?

**Short answer:** It hard-codes the interaction schedule, not the trajectory or
answer. Every force calculation still runs for the supplied dt and step count.

**If pressed:** The emitter accepts a body list and pair schedule and is checked
at multiple N. State is mutable. Capturing masses/schedule assumes they remain fixed
for that generated function; changing them requires regeneration. Above 20,000
pairs, the shipped implementation switches to a rolled loop to limit code growth.
The report should claim benchmark specialization, not universal Python acceleration.

**Evidence:** `_advance_source`, `_build_advance`, `_configure` in the benchmark;
[verification](../dev/nbody/verify.py).

### 4. Why not replace pow with sqrt and division?

**Short answer:** Equal real-number formulas need not produce equal FP64 results.
The exact software tier preserves `dt * (dsq ** -1.5)` and the original update order.

**If pressed:** Sqrt/multiply/reciprocal rounds at different operations; FMA also
changes rounding. Software equality is observed on the tested build, not promised
for every compiler or math library. Hardware has a distinct arithmetic model and
original-relative tolerance contract. Passing one contract does not establish another.

**Evidence:** [hardware arithmetic model](../hw/grape_pipeline/golden/emulation.py),
[FP64 decision](../hw/docs/adr/0002-grape-fp64-datapath-and-tolerance-oracle.md).

### 5. Is equal energy enough to prove correctness?

**Short answer:** No. Different states can have the same scalar energy.
We compare every state component as well as energy.

**If pressed:** Energy is a physical sanity check; state equality is stronger for
software equivalence. Even numerical `==` and bitwise equality differ for signed
zero. The hardware is checked against its own arithmetic oracle and separately
against original tolerances. Neither finite tests nor bounded proofs establish all
possible inputs automatically.

**Evidence:** [Python checker](../dev/nbody/verify.py),
[native checker](../dev/nbody/rs_check.py), [hardware testplan](../hw/grape_pipeline/docs/testplan.md).

### 6. Why does native nbody have lower IPC but run faster?

**Short answer:** It executes much less work: instructions fall about 26.7x and
cycles about 14.9x, even though IPC falls from 3.28 to 1.83.

**If pressed:** IPC counts retired machine instructions per cycle, not useful force
updates per cycle. Runtime depends on total cycles and clock, not IPC alone. A
stream of interpreter bookkeeping may retire efficiently and still be expensive.
These are matched warm-loop counter runs, separate from the canonical timing suite.

**Evidence:** [counter summary](../results/vm_release_20260907/counters/), Appendix A2.

### 7. Why not use Barnes–Hut or NumPy?

**Short answer:** At five bodies their setup and traversal/vectorization overhead
are too large. Barnes–Hut is 3.92x slower in the measured five-body force experiment.

**If pressed:** The reported Barnes–Hut crossover is near N=300 for the chosen body
distribution, theta=0.5 and best-of-seven protocol. It is a force-evaluation sweep,
not the default full integration benchmark. Median acceleration error does not
bound the worst body or long-term trajectory error. FMM was not benchmarked.

**Evidence:** [large-N sweep](../results/bigN_sweep.txt), [development findings](../dev/nbody/FINDINGS.md).

### 8. Isn't pyflate a DEFLATE benchmark?

**Short answer:** The code supports formats, but our measured fixture is bzip2.
It expands 67,562 compressed bytes into 399,360 output bytes.

**If pressed:** One block, six Huffman tables and 148,271 symbols yield a 336,184-byte
L-vector. Inverse BWT and final RLE4 produce the final output. Those are different
sizes and boundaries. The MD5 check is outside the benchmark timer.

**Evidence:** [benchmark](../benchmarks/bm_pyflate/run_benchmark.py), report Section 1.

### 9. Walk me through the Huffman lookup without reading the code.

**Short answer:** With a two-bit illustrative primary, 01 directly gives b and
consumes two bits. Next 11 indicates a longer code; extending to 110 gives d.

**If pressed:** Lengths [2,2,2,3,3] produce codes 00,01,10,110,111. At length 3,
limit=7 and base=3; code 6 selects perm[3]. A primary table entry stores both symbol
and actual consumed length. Duplicating a short code over all suffixes must not
consume those suffix bits. The shipped primary defaults to 11 bits, capped by max
length; the two-bit example intentionally forces a fallback.

**Evidence:** `build_huffman_table`, `_decode_symbols_python`; checked example script.

### 10. Why did you optimize more than Huffman matching?

**Short answer:** The matcher scanned about five entries on average, not all 258.
Bit handling, output construction, MTF, BWT and RLE also cost substantial time.

**If pressed:** On the VM, reverting regex-assisted RLE4 adds about 100 ms, primary
Huffman lookup about 50 ms, and counting-sort BWT about 20 ms to T3. These are
one-at-a-time reversions measured best of seven in interleaved trials. They do not
add up to a clean decomposition because the changes interact. The development
interpreter ranked them differently, showing why final-platform measurements matter.

**Evidence:** [ablation driver](../dev/pyflate/ablate.py),
[VM trial directory](../results/vm_rerun_20260910_3697a63/).

### 11. What does counting-sort BWT construction save?

**Short answer:** We only need bucket starts and stable original indices, so a
byte histogram and prefix sums replace sorting and repeated bucket searches.

**If pressed:** For banana, a:3,b:1,n:2 give starts 0,3,4 and T=[1,3,5,0,2,4].
This is O(n+256) construction, not the entire inverse BWT. The traversal still
follows a dependent index chain and handles output bytes. Earlier phase timings
are 137.7 ms for whole inverse BWT and 47.8 ms for traversal alone; never add them.

**Evidence:** `bwt_transform`, `bwt_reverse`, [phase capture](../results/pyflate_phase_cpi.txt).

### 12. Why reverse the MTF list?

**Short answer:** It puts the frequent front near Python's efficient append/pop
end, so selecting rank k shifts k entries rather than rebuilding the alphabet.

**If pressed:** Logical [a,b,c,d], rank 2 becomes [c,a,b,d]. Physical [d,c,b,a]
uses pop(-3) then append(c), producing [d,b,a,c]. The non-run decoded symbol r is
rank+1. RUNA/RUNB have separate meanings and are not ordinary rank updates. In
hardware, the block named CAM performs rank-indexed lookup and parallel shifting;
its name does not mean the decoder searches for a byte by content.

**Evidence:** `_decode_symbols_python`, [MTF architecture](../hw/mtf_cam/docs/uarch.md).

### 13. Exactly what crosses the Python/Rust boundary?

**Short answer:** Nbody moves the entire integration loop into a native System;
pyflate moves bit reading, Huffman, MTF and RUNA/RUNB into one call per block.

**If pressed:** Pyflate returns the L-vector and ending bit position. Headers,
inverse BWT and final RLE4 remain Python. Returning correct bytes with an incorrect
bit position can corrupt the next block, so both are checked. Nbody's native path
also evaluates energy in Rust, while the hardware proposal retains it in software;
include that residual when comparing end-to-end time.

**Evidence:** [Rust nbody](../rust/nbody/README.md), [Rust pyflate](../rust/pyflate/README.md),
[pyflate checker](../dev/pyflate/rs_check.py).

### 14. Why not simply call bz2.decompress?

**Short answer:** The assignment allows efficient libraries, so that would be a
valid comparison, but our path exposes which transformations and boundaries help.
We use bz2.decompress as an output oracle.

**If pressed:** We have not presented a measured libbz2 performance comparison in
these reports. Do not claim our implementation beats the standard native library.
Such a comparison would help assess practical deployment choices, using the same
input, timer boundary and correctness check.

**Evidence:** pyflate benchmark and checker; project instructions Sections 5–6.

### 15. Can the profile explain the 1.67x native speedup?

**Short answer:** Not quantitatively by itself. Its 32.79% decoder share would
limit ideal acceleration to 1.49x under the unchanged-residual model.

**If pressed:** A measured 1.67x requires at least 1-1/1.67=40.1% removable work,
and more for a finite-speed kernel. The graph is a separate, sparse sampling run,
not a matched phase-timing decomposition. We keep the validated end-to-end result
and explicitly identify the attribution gap. Next, measure that exact boundary
and residual on one build with matched setup and timer scopes.

**Evidence:** canonical fallback/native JSONs, [function shares](../results/profile_functions.txt).

### 16. Are 120 timing values independent? Is mean ± SD a confidence interval?

**Short answer:** No on both counts. They come from 40 worker processes, three
values each; mean ± SD describes observed spread.

**If pressed:** A random-effects decomposition estimates within- and between-worker
variance. The design effect 1+(3-1)*ICC adjusts the mean's SE under that model. For
original and optimized nbody the implied effective sample size is about 40–42, not
120. This assumes independent workers and does not remove VM drift. Compare runtime
differences with uncertainties in time, or derive uncertainty for a ratio; don't
compare a dimensionless speedup directly with an SE in milliseconds.

**Evidence:** [distribution tool](summarize_distribution.py), Appendix A5.

### 17. How do you know “native” didn't silently fall back to Python?

**Short answer:** We request the backend explicitly, forward that request to
workers, fail if native is unavailable, and record what actually ran.

**If pressed:** Each native JSON records the extension hash, matched to the wheel
built in that run. The build script installs the exact newly built wheel instead
of a similarly named old binary. A dispatch check counts zero native calls in
Python mode and one per block in native/auto mode for the benchmark input.

**Evidence:** [wheel builder](../tools/build_wheel.sh),
[dispatch check](check_pyflate_backend.py), canonical suite metadata and protocol logs.

### 18. Can your cache counters prove that BWT is memory-bound?

**Short answer:** No. Aggregate cache references/misses do not identify a specific
stage, cache level, latency or stall time.

**If pressed:** The earlier phase timer excludes setup but its perf wrapper counts
the whole process. The newer matched counters gate after setup, yet cover complete
benchmark iterations. Nbody's miss counts are extremely small. L1 load counts were
invalid and omitted. A native BWT implementation with an isolated timer and a
working-set sweep is needed before claiming memory latency is the limiter.

**Evidence:** [counter collector](measure_native_counters.py), Appendix A2/A3.

### 19. Why can't all ten nbody pair updates happen simultaneously?

**Short answer:** Force terms can overlap, but pairs sharing a body also share
velocity state. The same component needs ordered accumulation.

**If pressed:** Pair (0,1) produces u0a from u0; pair (0,2) must consume u0a. Using
old u0 twice loses one contribution. Regrouping the sum changes rounding. Other
body-component lanes can proceed independently. More issue width needs ports,
forwarding and selection logic, which costs area and can lengthen critical paths.

**Evidence:** [dependency figure](fig/pair_dependency.svg),
[grape architecture](../hw/grape_pipeline/docs/uarch.md), `rtl/grape_accum.sv`.

### 20. Does the hardware beat Rust? If not, why build it?

**Short answer:** No, on both benchmarks. Nbody hardware projects to about 139 ms per
run at the 19.46 MHz clock that static timing supports: 1.66x over the original,
level with the optimized Python, about 15x slower than the 9.53 ms native Rust tier.
The pyflate chain takes about 4.24 ms for the stage Rust does in 3.30 ms, and ties
the delivered 170 ms path end to end.

**If pressed:** Nbody compute is 2.48 Mcycles / 19.46 MHz = 127.4 ms, plus the
11.6 ms Python residual (5% of the original), which alone exceeds Rust's 9.53 ms.
At the 50 MHz design target it would be about 61 ms (3.78x), still about 6x slower
than Rust; the datapath would need about 260 MHz to match. The course asks for a
complete, reasoned HDL design, not a winning chip. The outcome shows that removing
interpreter overhead and building a fast physical datapath are different problems.
The schedule model projects native-class throughput only at large N with four to
eight times the arithmetic units. No energy advantage has been demonstrated.

**Evidence:** nbody report Section 5 "Does the hardware win?", pyflate report
Section 5, [grape PPA](../hw/grape_pipeline/docs/ppa.md).

### 21. What did the area/timing trade-off teach you?

**Short answer:** Three-wide accumulation reduced cycles from 162 to 124, at a
38.7% mapped-area increase. But its issue-selection logic became a timing problem.

**If pressed:** Rewriting the picker as balanced prefix trees removed a long
sequential combinational scan without adding pipeline cycles. Post-CTS estimates
improved from 11.15 to 19.46 MHz (1.75x), bit-exact, same 124 cycles. The
2.938/4.075 mm² comparison is two plain-Yosys design points made before that
rewrite. Under the OpenLane synthesis recipe, which is not comparable with plain
Yosys, the final netlist is 446,932 cells / 4.66 mm² (5.65 mm² after buffering and
clock tree) against 4.92 mm² before the rewrite, so the rewrite made the design 5%
smaller as well as faster. Each result must retain its revision, recipe and stage.

**Evidence:** grape `docs/ppa.md`; `hw/grape_pipeline/synth/evidence/area_openlane.txt`.

### 22. What exactly is verified in hardware?

**Short answer:** Module regressions check functionality and interfaces against
golden models, including full benchmark inputs, directed/random tests and recorded
coverage. The two pyflate modules are also simulated together as one chain. Some
control properties have formal checks.

**If pressed:** Recorded regressions are grape 9/9, Huffman 17/17, MTF 16/16 and
the chain 2/2. The chain (`hw/pyflate_accel`) is byte-exact over all 336,184
L-vector bytes of the real benchmark block, with and without random back-pressure,
in 159,303 cycles. Coverage exclusions matter; 90% control coverage is not
exhaustive datapath coverage. The three MTF list invariants are proven unbounded by
induction at 16 entries; at the production 256 entries the general check is bounded
to depth 6, and a fill-abstracted run (valid filled list, 8 live entries) shows 24
consecutive moves preserve the permutation. What is not established: a run of
Python attached to hardware, so CPU/DMA interface time is unmeasured.

**Evidence:** each module's `docs/testplan.md`, `docs/review_signoff.md`,
`docs/coverage_waivers.md`; `hw/mtf_cam/synth/formal.sby`; `hw/pyflate_accel/README.md`.

### 23. Are 19.46 MHz, 39.9 MHz and 37.6 MHz measured frequencies?

**Short answer:** They are derived from static timing reports, not measured on
silicon and not final routed sign-off. All three are post-CTS.

**If pressed:** Post-CTS means cells and the clock tree are placed but signal wires
are not routed. Each figure is 1/(clock constraint minus worst setup slack) at the
typical corner, read from the setup (max) report: grape 150 ns with +98.62 ns slack;
Huffman 40 ns with +14.94 ns slack, confirmed by a tighter 27 ns run that meets
timing and gives 39.5 MHz; MTF missed its 20 ns constraint by 6.60 ns, so
1/26.6 ns. Routing can change the results; preliminary timing is not a guaranteed
bound. All have a 50 MHz target and none has demonstrated it.

**Evidence:** module `docs/ppa.md`; the small report files are preserved under each
module's `synth/evidence/` (`ws.max.rpt`, `power.rpt`, worst path). The full
OpenLane run folders are gitignored; have them available if staff want to inspect.

### 24. Does 13.7 mW establish an energy advantage? Will SRAM fix the area?

**Short answer:** Neither conclusion is established. The power figures use default
tool switching activity, and Huffman's SRAM alternative has not been implemented.

**If pressed:** The estimates are about 19 mW (grape, at its 150 ns constraint),
about 283 mW (Huffman, 40 ns) and about 13.7 mW (MTF, 20 ns). Each belongs to its
own run constraint, so they are not comparable with each other, are not workload
power and cannot be paired with a different frequency as measured energy. System
energy includes CPU, DMA and memory. Huffman's projected 0.75 mm² is remaining
standard cells plus two SRAM macros, whose area is additional. Access latency,
ports and integration must be checked before claiming unchanged throughput or a
total below 1 mm².

**Evidence:** Huffman PPA Section 2; MTF PPA Section 3.2.

### 25. Why doesn't a near-one-symbol-per-cycle decoder imply huge total speedup?

**Short answer:** Most of the gain disappears behind surviving software and
communication. Only the replaced stage's time can be removed.

**If pressed:** The report uses T_new = T_sw - T_stage + T_hw + T_if. The replaced
stage is about 117 ms in the optimized Python loop (derived: 283.88 - 170.01 +
3.30 ms) and 3.30 ms in the Rust kernel. The chain needs 159,303 cycles: about
4.24 ms at the shared 37.6 MHz clock, 3.19 ms at 50 MHz. That is about 28x faster
than the Python loop and about 1.3x slower than Rust. End to end it projects to
about 171 ms, a tie with the delivered 170.01 ms path (6.6x over the original),
because inverse BWT (137.7 ms, about 80% of what remains) sets the floor for both
routes. T_if is not measured, and adding it can only make the hardware rows slower.

**Evidence:** pyflate report Section 5 "Does the hardware win?", Appendix A3.

### 26. How does the Huffman/MTF chain connect to software?

**Short answer:** CPU parses headers and configures both modules over AXI4-Lite;
streams carry bits and selectors to Huffman, symbols stay on chip, and platform DMA
returns L-vector bytes from the MTF packer. Python finishes inverse BWT and RLE4.

**If pressed:** Both modules are single-clock and the chain uses one shared clock,
37.6 MHz set by MTF, so there is no clock-domain crossing; the two estimates are 6%
apart, so an asynchronous FIFO would add area and verification for no benefit. The
link is a valid/ready stream, one symbol per beat. MTF needs 1.0686 cycles/symbol
against Huffman's 1.0068, so it back-pressures the decoder and the chain runs at
MTF's rate: 159,303 cycles, 0.5% above MTF's standalone 158,441. Software starts
the consumer before the producer and handles output capacity, completion and error
propagation. DMA setup, buffer copies and cache maintenance need platform
measurements. The 32-bit control bus and 64-bit default MTF output data bus serve
different purposes.

**Evidence:** [decode diagram](fig/decode_report.svg), module `docs/mas.md`,
integration docs, `hw/pyflate_accel/README.md`.

## Demonstrations and evidence lookup

### Short demonstration: standard Python only

From the repository root:

```sh
python3 report/verify_examples.py
python3 report/check_figures.py
python3 report/check_txt_tables.py
```

The first command checks the printed Huffman, BWT, MTF, RLE4 and nbody examples
against shipped functions. It does not claim the full workload or HDL passed again.
The other commands verify report geometry preservation and text-table associations.

### Prepared course VM demonstration

Run only in the documented environment with dependencies and freshly built matching
native extensions. Do this before presentation day and save the output:

```sh
./tools/check_all.sh --require-native
python3 report/check_pyflate_backend.py .
suite=results/vm_canonical_20260910_2c8c754/suite
python3 -m pyperf compare_to "$suite/baseline_nbody.json" \
    "$suite/optimized_nbody.json"
python3 -m pyperf compare_to "$suite/fallback_pyflate.json" \
    "$suite/native_pyflate.json"
```

The full checker can take time and its current number of checks may differ from an
older recorded run. Show actual output rather than memorizing a pass count. The
compare commands inspect saved results; they do not benchmark the current machine.
Hardware simulations require the toolchain described in `hw/FLOW.md`; use module
Makefiles and prepared logs rather than launching synthesis during the presentation.

## Final rehearsal checklist

- Explain each worked example from the input, without looking at its final answer.
- Name the baseline, timer scope and platform whenever quoting a speedup.
- Point to one oracle/checker for each correctness claim.
- Explain one rejected optimization and one hardware trade-off.
- Distinguish measured elapsed time, RTL cycles, model cycles, STA and default-activity power.
- Be ready to say “that remains unmeasured,” followed by the experiment that would resolve it.
- Open the exact evidence files before presenting; do not depend on a remote session to find them.
