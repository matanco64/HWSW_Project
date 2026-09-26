# Storyboard

Main flow: 26 slides, 1350 s (22:30). Backup: 12 slides, shown only on request.
Stage = footer tracker value. Brief column = the instruction item the slide satisfies
(§1 analysis, §2 pyperformance, §3 flame graph, §4 bottleneck, §5 improvements, §6 results,
§7a HW description, §7b I/O, §7c architecture, §7d HW/SW interface, §7e justification,
§7f block diagram, §7g PPA trade-offs, §10 AI tools).

## Main flow

| # | Claim title (draft) | Owner | s | Stage | Visual | Brief |
|---|---|---|---|---|---|---|
| S01 | Two pure-Python pyperformance workloads, one question: where does the time go, and what would it take to move it to hardware? | M | 90 | Analyze | table: canonical runtimes, both benchmarks, original / optimized / native | §1, §2 |
| S02 | nbody is 5 bodies, 10 pairs and 20,000 steps of pure-Python float arithmetic | M | 45 | Analyze | `nbody_pairs.png` | §1 |
| S03 | 97.7% of samples sit in advance(); list indexing and float boxing dominate the C frames | M | 60 | Profile | `print_nbody_stock.png` | §3, §4 |
| S04 | Specializing advance() to the fixed pair list removes the list traffic: 231 → 143 ms, 1.62x, bit-identical state | M | 60 | Optimize | `print_nbody_opt.png` | §5, §6 |
| S05 | Struct-of-arrays and NumPy lose at N=5; only leaving Python wins: the Rust tier runs in 9.53 ms | M | 60 | Optimize | table: tiers with denominators | §5, §6 |
| S06 | Native runs 26.7x fewer instructions while IPC drops from 3.28 to 1.83: the win is instruction count, not the pipeline | M | 45 | Optimize | table: counters | §6 |
| S07 | advance() is 95% of the remaining time, so the whole step goes on-chip after one doorbell | Y | 45 | Accelerate | `grape_report.png` | §7e, §7d |
| S08 | grape_pipeline computes full IEEE FP64 in the benchmark's own operation order, with 3 adders and 3 multipliers chosen by a cycle model | Y | 60 | Accelerate | `grape_block_diagram.png` | §7a, §7b, §7c, §7f |
| S09 | K1 is 124 cycles per step against a budget of 128, found only after the full-shape test exposed 162 | Y | 45 | Accelerate | table: 1-wide vs 3-wide (cycles, area) | §7c, §7g |
| S10 | Post-CTS timing gives 19.46 MHz against a 50 MHz target; the accumulate picker set the clock and a parallel-prefix rewrite bought 1.75x | Y | 45 | Trade-offs | table: grape PPA | §7g |
| S11 | At 19.46 MHz grape ties optimized Python and is about 15x slower than Rust | Y | 45 | Trade-offs | table: Python opt / grape projected / Rust | §7e, §7g |
| S12 | What would beat Rust: the clock it takes, a wider unit mix, and a Rust host around the same hardware | Y | 30 | Trade-offs | table: projection scenarios | §7g |
| S13 | pyflate is bzip2 decompression in pure Python: Huffman decode, move-to-front, run-length, inverse BWT | M | 45 | Analyze | `pyflate_stages.png` | §1 |
| S14 | A canonical Huffman code is decoded by comparing the next bits against one threshold per length | M | 30 | Analyze | `huffman_tree.png` | §1 |
| S15 | 40% of the original profile is Huffman symbol decode, 13% move-to-front, and a quarter is the bit reader | M | 60 | Profile | `print_pyflate_stock.png` | §3, §4 |
| S16 | Three optimizations, each measured by reverting it: table lookup, regex RLE4, counting-sort BWT take 1,123 ms to 281 ms, 4.00x | M | 75 | Optimize | table: ablation | §5, §6 |
| S17 | After optimization inverse BWT is 80% of what remains; a Rust kernel for symbol decode reaches 170 ms, 6.61x end to end | M | 90 | Optimize | `print_pyflate_opt.png` | §5, §6 |
| S18 | Huffman decode is 40% of the original run, a 1.67x ceiling alone, so we chain it with move-to-front on one AXI stream | Y | 45 | Accelerate | `decode_report.png` | §7e, §7d, §7f |
| S19 | huffman_engine decodes one symbol per cycle: a barrel shifter, 20 parallel comparators, and six preloaded table sets so a table switch costs zero cycles | Y | 60 | Accelerate | `huffman_block_diagram.png` | §7a, §7b, §7c |
| S20 | mtf_cam is a 256-entry shift-register list read by rank; width 8 sits at the knee of the area/cycle sweep | Y | 45 | Accelerate | table: W-sweep | §7c, §7g |
| S21 | The chain reproduces the benchmark output byte-exact: 336,184 bytes in 159,303 cycles, with and without back-pressure | Y | 45 | Accelerate | `chain_cosim.gif` (clip) | §7d |
| S22 | At 37.5 MHz the chain is 28x faster than the Python loop and 1.3x slower than the Rust kernel; end to end it is a 6.6x tie because inverse BWT sets the floor | Y | 45 | Trade-offs | table: hardware stage vs Python loop vs Rust; end-to-end | §7e |
| S23 | All three modules meet their cycle KPIs and miss 50 MHz; huffman_engine's area is 95% tables in flip-flops, so SRAM would roughly halve it | Y | 60 | Trade-offs | table: cross-module PPA | §7g |
| S24 | We ran a ten-stage flow with four human checkpoints: agents pre-reviewed, humans decided | Y | 30 | Trade-offs | `hw_flow.png` | §10 |
| S25 | What the evidence does and does not say: post-CTS timing, one extrapolated clock, unmeasured interface time, un-re-timed commits | Y | 30 | Trade-offs | table: claim vs evidence level | §7e, §7g |
| S26 | What we learned: measure the KPI on the full-shape workload early, and the next experiment is a native inverse BWT and a timing confirmation run | M+Y | 60 | Trade-offs | table: three lessons, two next steps | §6, §7 |

Seconds: 90+45+60+60+60+45+45+60+45+45+45+30+45+30+60+75+90+45+60+45+45+45+60+30+30+60 = **1350**.

## Backup slides (on request)

| # | Claim title (draft) | Owner | Visual | Answers |
|---|---|---|---|---|
| B01 | grape's step is a fixed 290-operation graph scheduled onto 3 adders and 3 multipliers | Y | grape datapath/FSM render from uarch.md | architecture depth |
| B02 | The 162-cycle miss hid behind a 2-pair smoke test; the full-shape test at sign-off found it | Y | table: stage-by-stage K1 | "what did verification find?" |
| B03 | Unit-mix sweep: 2+2 → 133 cycles, 3+3 → 123/127, 3+4 → 117; 3+3 is the last point under 128 | Y | table | grape trade-off |
| B04 | huffman_engine storage: flip-flop tables 1.634 mm² as built, SRAM ~0.75 mm² projected, 2 table sets breaks K1 | Y | table + RTL-review bug list | area, "what bugs?" |
| B05 | mtf_cam in full: block diagram, K3 1.0686 vs 1.063 model, formal depth 6 general / 24 fill-abstracted, unbounded at 16 entries | Y | `mtf_block_diagram.png` | mtf detail, formal |
| B06 | Verification evidence per module: tests, line/toggle/branch coverage, formal, both simulators | Y | table | "what is verified?" |
| B07 | Speedup at two altitudes agrees: 25x on a 13.4% slice is 1.148x; two profilers give f = 0.496 vs 0.40 | Y | table | Amdahl, profiler denominators |
| B08 | HW/SW interface: AXI-Lite registers, AXI-Stream data, driver model with 0 register-map diffs, co-simulated against the RTL | Y | register-map excerpt | interface, drivers, DMA |
| B09 | Cross-module PPA in full: cells, area by flow, Fmax, power with its caveat, tests | Y | table | any PPA question |
| B10 | How we used AI: a stage-gated flow, prompt.txt as the log, and the decisions humans made | Y+M | table: decision → who | §10, "you vs the agent" |
| B11 | Measurement method: pyperf route, workers, what ± means, and which commits were not re-timed | M | table | statistics, timed ≠ submitted |
| B12 | Larger N: Barnes-Hut crosses over far above the benchmark's N=5; grape scales with the pair count | M | table/plot | scaling |

## Brief coverage check

§1 S02 S13 S14 · §2 S01 · §3 S03 S15 · §4 S03 S15 · §5 S04 S05 S16 S17 · §6 S04 S05 S06 S16 S17 S26 ·
§7a S08 S19 · §7b S08 S19 · §7c S08 S09 S19 S20 · §7d S07 S18 S21 · §7e S07 S11 S18 S22 S25 ·
§7f S08 S18 · §7g S09 S10 S11 S12 S20 S23 S25 · §10 S24. Projection slide: S12. Every row has an owner.
