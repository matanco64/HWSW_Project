#import "style.typ": *
#show: report.with("Benchmark Report: nbody",
  "Five bodies, twenty thousand steps, and an interpreter between every calculation")

*A probe is falling toward Neptune, and somebody has to know where it will be in six hours.*
Predicting motion means repeatedly adding up gravitational forces. This benchmark captures
that computational core in miniature: the Sun and four gas giants, ten interacting pairs,
and twenty thousand steps. The physics is compact; in Python, the machinery around each
calculation is not. Our optimization asks how much of that machinery we can remove.

= 1. Workload and result

The Computer Language Benchmarks Game's `nbody` uses symplectic Euler integration under
Newtonian gravity. Each timed iteration evaluates energy, calls `advance(0.01, 20000)`, then
evaluates energy again. The stock kernel uses only the standard library, with no I/O in the
timed region. State consists of five position/velocity/mass records (35 float values);
the ten body pairs are constructed once and reused.

#figure(image("fig/nbody_pairs.svg", width: 90%),
  caption: [Ten fixed pairs × 20,000 steps = 200,000 pair-force evaluations.])

#result-table(columns: (1.7fr, 1fr, 1fr), align: (left, right, right),
  table.header([*Configuration*], [*Mean ± SD*], [*vs stock*]),
  [Stock Python], [231.20 ± 7.85 ms], [1.00×],
  [Optimized Python], [143.13 ± 1.56 ms], [*1.62×*],
)

The optimization reduces runtime by *38.1%*, exceeding the course's 7% requirement.
It specializes the interaction schedule into local-variable arithmetic while preserving
operation order. Final state and energy compare exactly equal to stock after 20,000 steps.
Energy is a useful physical sanity check; componentwise state comparison is the stronger
equivalence check.

#note[*Measurement scope.* Course QEMU/KVM VM, Ubuntu 22.04, release CPython 3.10.12,
pyperformance 1.14.0; 120 measured values per configuration, every timed run pinned to guest
CPU 0, measured from revision 2c8c754 through the documented runner scripts. Source:
`results/vm_canonical_20260910_2c8c754/suite/{baseline,optimized}_nbody.json`, which also record the back end and CPU
affinity (Appendix A7). SD denotes sample standard deviation,
not a confidence interval. Profiling is separate from timing; the shared appendix records
methods and provenance.]

The distributions behind those means are right-skewed and strongly grouped by worker
process. Medians are 228.84 ms and 142.64 ms, with interquartile ranges of 3.09 ms and
0.52 ms, so half of all values sit in a band under 1.4% wide, while a few slow workers push
the stock maximum to 266.97 ms and its SD to 7.85 ms. Almost all of the variance is *between*
workers rather than within them (ICC 0.99 and 0.93) even though every run was pinned to the
same CPU, so the 120 values are effectively about 40 and 42 independent observations;
Appendix A5 gives the full decomposition. The 1.62× ratio is far larger than that
uncertainty, so the conclusion is unaffected -- but the naive standard error would overstate
how much a small difference could be trusted.
#pagebreak()
= 2. Profiling and optimization

Python-frame sampling places almost all benchmark work in `advance()`. The C-level debug-build
profile identifies generic arithmetic dispatch, float allocation and list access as substantial
costs. These debug-build percentages locate costs to investigate; release-build timing
establishes the optimization's benefit.

#result-table(columns: (1.9fr, 1fr, 1fr), align: (left, right, right),
  table.header([*Stock nbody, C-frame profile*], [*Self*], [*Inclusive*]),
  [`_PyEval_EvalFrameDefault`], [42.94%], [99.33%],
  [`binary_op1` (generic arithmetic dispatch)], [5.51%], [20.36%],
  [`float_mul`], [4.23%], [4.23%],
  [`PyFloat_FromDouble`], [4.03%], [5.84%],
  [`float_dealloc`], [3.34%], [3.34%],
  [`list_ass_item`], [2.72%], [2.72%],
  [`PyNumber_AsSsize_t`], [2.29%], [4.99%],
  [Float object handling, all symbols], [*16.30%*], [--],
  [List access and index conversion, all symbols], [*11.95%*], [--],
)

*Self* is time in the function itself; *inclusive* is time in it and everything it calls.
The two grouped rows sum self time over `^(float_|PyFloat_)` and over
`^(list_|listiter_|PyNumber_AsSsize_t|PyLong_AsSsize_t)` respectively.

The named rows are the symbols that carry the self time, which perf records under their
`.lto_priv` names. perf also emits a companion `(inlined)` entry per symbol holding the
inclusive share and no self time -- that is the number the figure below quotes for a
highlighted frame, so 4.00% there and 2.72% here describe the same function under two
different measures. Both the table and the groups are regenerated from
`results/perf_report_nbody_stock.txt` by `report/summarize_profiles.py`, which prints every
contributing symbol; an earlier draft quoted 14.4% for the list group, which that file does
not support.

#figure(image("fig/print_nbody_stock.svg", width: 100%),
  caption: [Full stock C-frame profile (debug CPython), with the same call paths outlined
  and enlarged. All original frames, widths and startup context are retained. Percentages
  describe the selected inclusive call path, not a function's total self time.])

== Specialize the fixed schedule

The original loop revisits the same pairs and masses on every step. At import time, the
optimized version emits an `advance()` function with the pair loop unrolled, coordinates in
Python locals, and masses as literals. It loads state before the step loop and writes it back
afterwards, so energy reporting still observes the original body objects.

This removes list subscripting from the generated step loop and avoids repeated pair
unpacking. List operations remain at function entry and exit, amortized over 20,000 steps.

*Correctness constrains the arithmetic.* The kernel retains `dt * (dsq ** -1.5)` and the
stock pair-update order. A square-root/division replacement changes rounding and is not used
in the exact software tier. The emitter accepts a body list and pair schedule, so the same
transformation extends to larger systems.

#pagebreak()
= 3. Native execution: less work, not higher IPC

The Rust/PyO3 kernel stores state in a `System` object and executes all 20,000 steps through
one `advance(dt, n)` call; both energy evaluations also run in Rust. On the tested VM build,
state and energy also compare exactly equal
to stock. This is evidence for the tested compiler, library and workload, not a portability
guarantee for every floating-point build.

#result-table(columns: (1.7fr, 1fr, 1fr), align: (left, right, right),
  table.header([*Same benchmark file*], [*Mean ± SD*], [*vs Python*]),
  [Python backend], [145.30 ± 4.97 ms], [1.00×],
  [Native backend], [9.530 ± 0.050 ms], [*15.25×*],
)

Both rows come from the same pinned canonical run as the table in Section 1, preserved as
`vm_canonical_20260910_2c8c754/suite/{fallback,native}_nbody.json` under `results/`.
The separate kernel experiment (228.49 → 9.48 ms, 24.1×) compares native execution with
*stock* Python. The table compares it with the already optimized Python implementation.
Both the baseline and timing protocol must be specified when comparing these ratios.

Backend selection is explicit: `HWSW_BACKEND=python|native|auto`. Native mode fails if the
wheel is unavailable; auto mode falls back to Python. Pyperf workers must receive the variable
through `--inherit-environ HWSW_BACKEND`; result metadata identifies what ran.

== Matched-work CPU counters

A separate warm-loop experiment repeats the same timed work 64 times per run on a fixed
guest CPU. The table reports medians of three runs, normalized to one 20,000-step iteration.
Counters exclude initialization and warmup; Appendix A2 documents gating and event validation.

#result-table(columns: (1.8fr, 1fr, 1fr), align: (left, right, right),
  table.header([*Metric per iteration*], [*Python*], [*Native*]),
  [Elapsed time], [141.08 ms], [9.462 ms],
  [Instructions], [1,103.62 M], [41.32 M],
  [Cycles], [336.24 M], [22.55 M],
  [IPC], [3.28], [1.83],
  [Branches], [185.97 M], [3.92 M],
  [Branch misses (rate)], [583,560 (0.314%)], [60 (0.00153%)],
  [Generic cache references], [3,006], [255],
  [Generic cache misses (rate)], [59.6 (2.245%)], [2.5 (1.134%)],
)

*The main gain is 26.7× fewer instructions and 14.9× fewer cycles.* Compiled arithmetic
avoids Python object handling and dispatch, removing most branches too. IPC actually falls:
native execution retires fewer instructions per cycle, but needs far fewer instructions to
finish. Higher IPC is not synonymous with a faster program.

Generic cache misses are sparse in both runs, with fewer references and misses in native
execution. Counts vary: Python records 59–94 misses per iteration and native 2–10 across
the three runs. These small counts do not establish cache latency as the bottleneck.
L1 events are omitted because an earlier capture returned invalid load counts.

#pagebreak()
= 4. What changes when N grows?

#figure(image("fig/print_nbody_opt.svg", width: 100%),
  caption: [Full optimized Python-frame profile with the integration call path enlarged.
  Integration remains the hotspot. Independent normalization does not display the absolute
  runtime reduction from 231 to 143 ms.])

At five bodies, Barnes-Hut is *3.92× slower* than direct force evaluation on the VM.
Tree construction and traversal do not pay off for ten pairs. Development experiments also
found that struct-of-arrays and NumPy lose at this size (`dev/nbody/FINDINGS.md`). FMM was
not benchmarked, so no measured FMM speedup or lower bound is claimed.

The `--bodies N` extension adds deterministic outer orbits while preserving the five-body
default. Source generation grows as O(N²), increasing compilation time and memory use.
The shipped implementation falls back to a rolled loop above 20,000 pairs.
Detailed unrolling and local-slot experiments used *WSL2 / CPython 3.10.21*; their timings
and memory limits are development observations, not VM results.

The VM force-evaluation sweep below includes a rebuilt Barnes-Hut tree at each evaluation
(θ = 0.5, best of seven). It evaluates an extended workload, not the required N = 5 benchmark.

#result-table(columns: (auto, 1fr, 1fr, 1fr, 1fr), align: (right, right, right, right, right),
  table.header([*N*], [*Direct*], [*BH*], [*BH/direct*], [*Median rel. error*]),
  [5], [0.020 ms], [0.077 ms], [3.92×], [0],
  [100], [4.746 ms], [8.410 ms], [1.77×], [1.6e-5],
  [300], [42.977 ms], [42.489 ms], [0.99×], [3.3e-5],
  [800], [313.489 ms], [158.846 ms], [0.51×], [8.7e-5],
  [1,600], [1,254.660 ms], [382.471 ms], [0.30×], [1.8e-4],
)

The crossover is near N = 300 for this distribution. Median relative acceleration error is
not a worst-case or trajectory-error bound. The separate VM native sweep gives 21–22× over
rolled Python from N = 100 to 3,200. Step counts approximately equalize pair-updates, with
integer rounding increasing work at the final row. Both sweeps are in `results/bigN_sweep.txt`.

#pagebreak()
= 5. Hardware acceleration: current design

`grape_pipeline` retains state on the device and executes a complete `advance(dt, n)` request.
Force computation suits a scheduled datapath, while velocity accumulation must respect
dependencies between pairs sharing a body. Steps remain serial.

#figure(image("fig/grape_report.svg", width: 100%),
  caption: [Current datapath and software boundary, summarized from the approved architecture.
  Multiplication and accumulation round separately; there is no FMA unit.])

*Datapath.* Three FP64 add/subtract units, three multipliers, one square-root unit and one
reciprocal unit share a scheduled 290-operation step. The square root uses radix-4 iteration;
the reciprocal uses a ROM seed and refined fixed-point arithmetic. An ordered accumulation
sequencer resolves body-component dependencies before positions are updated and committed.

*Interface.* A 32-bit AXI4-Lite slave exposes FP64 body state and `DT`, 32-bit `NSTEPS`,
pair configuration, control/status, counters and IRQ. Software loads state and parameters,
starts one request, waits, then reads state. There is no per-step DMA or Python call.
The Rust object demonstrates this boundary; it is not a completed hardware driver.

#result-table(columns: (1fr, 2fr),
  table.header([*Evidence / target*], [*Current status*]),
  [Step schedule model], [123 cycles nominal; 127 at modeled latency corners],
  [Clock target], [50 MHz minimum; final timing/PPA not yet established],
  [Conditional execution time], [49.2–50.8 ms for 20,000 steps at 50 MHz, before interface overhead],
  [RTL and verification], [Synthesis and directed bring-up recorded; full coverage, sign-off and integration remain open],
)

At that design point, modeled execution is about 4.6× faster than stock Python and 2.9×
faster than optimized Python, but *slower than the 9.53 ms native implementation*.
More units, a higher achieved clock, or reduced precision require measured area/timing
trade-offs. No measured power advantage is claimed.

The hardware's square-root/reciprocal expression differs from stock `pow`. RTL is checked
against its own arithmetic model. Comparison with stock targets relative energy error ≤ 1e-12
and per-body position/velocity errors ≤ 2e-9 / 5e-11 at completion. These tolerance targets
are distinct from the software tier's observed exact equality.

= 6. Conclusion

Specializing a fixed schedule cuts Python runtime by 38.1% while preserving the tested state
and energy exactly. Native execution removes more interpreter work through the same coarse
interface. The hardware design implements that boundary, but its benefit over native software
depends on achieving a better latency/area point than the current model.

#text(size: 9pt)[*Evidence:* `hw/grape_pipeline/docs/uarch.md`, `prd.md`,
`testplan.md`, and `hw/PROGRESS.md` (status recorded 2026-09-05).
Reproduction and supporting profiles: *report_appendix.pdf*.
Repository: #link("https://github.com/matanco64/HWSW_Project")[HWSW_Project].]
