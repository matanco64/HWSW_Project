# Deck part: nbody hardware, process and limits (owner Y)

Slides S07–S12, S24, S25 (main flow) and B01, B02, B03, B06, B07, B10 (backup), in storyboard
order. Format per `presentation/STRATEGY.md` "Spec format"; derived numbers come from
`presentation/derivations.md`.

## S07 · advance() is 95% of the remaining time, so the whole step goes on-chip after one doorbell
- owner: Y
- status: DRAFT
- stage: Accelerate
- seconds: 45
- visual: assets/grape_report.png
- exempt: 5, 10

notes:
Amdahl first, hardware second. The profile says 95% of the original run is inside advance(), so f = 0.95 and the ceiling for any accelerator is 20x; at the 50 MHz design target the model gives 3.78x, which is why the PRD asked for at least 4x. The boundary follows from the loop shape: 20,000 serial steps over five bodies and ten pairs. If the host called the device once per step, the register traffic would dwarf the arithmetic, so software loads the body state and the pair list, rings one doorbell, and reads the state back after all 20,000 steps. That costs about 150 AXI-Lite transactions per run, under 0.03% of the compute. ADR-0001 therefore chose MMIO only: no DMA, no stream ports, because a few hundred bytes per invocation do not justify a DMA engine and its verification.

sources:
- 95 % of it in advance → hw/grape_pipeline/docs/integration.md:132
- `f` = 0.95 → hw/docs/hardware_report.md:167
- 1/(1−f) = 20× → hw/grape_pipeline/docs/integration.md:91
- t_hw = 49.6 ms → **3.78×** at f = 0.95 → hw/docs/hardware_report.md:171
- ≥ 4 → hw/grape_pipeline/docs/prd.md:32
- design target **50 MHz** → hw/docs/hardware_report.md:121
- body state stays on-chip for all 20,000 steps after one doorbell → hw/docs/hardware_report.md:110
- 5 bodies and up to 10 pairs → hw/grape_pipeline/docs/prd.md:57
- ≈ 150 AXI-Lite transactions per → hw/docs/hardware_report.md:153
- < 0.03 % of compute → hw/docs/hardware_report.md:155
- MMIO only (ADR-0001): no DMA, no streams → hw/grape_pipeline/docs/mas.md:111
- `grape_pipeline` needs only AXI-Lite (~340 B in, ~260 B out per → hw/docs/adr/0001-bus-family.md:9

## S08 · grape_pipeline computes full IEEE FP64 in the benchmark's own operation order, with 3 adders and 3 multipliers chosen by a cycle model
- owner: Y
- status: DRAFT
- stage: Accelerate
- seconds: 60
- visual: assets/grape_block_diagram.png
- exempt: 4, 5, 10, 15

notes:
Inputs and outputs: a 32-bit AXI4-Lite slave with a 12-bit address inside a 4 KB window, plus one interrupt. Through that window software writes FP64 body state as word pairs, DT, a 32-bit NSTEPS, and the pair list; it reads back state, counters and status. The register map is 15 rows. Inside, the datapath is our own FP64 units: three 3-stage adders, three 3-stage multipliers, one radix-4 SRT square root of about 30 cycles and one Newton reciprocal of about 22 cycles. Deliberately no FMA: the Python trajectory rounds after every multiply and every add, and fusing them would break bit-exactness against the emulation model. A step is a fixed 290-operation graph; the cycle model list-scheduled it onto candidate unit mixes and 3 add plus 3 mul was the smallest mix under the 128-cycle budget. Clock target 50 MHz.

sources:
- 32-bit AXI4-Lite slave exposing FP64 (binary64) body state → hw/docs/hardware_report.md:119
- `s_axi_awaddr` | in | 12 → hw/grape_pipeline/docs/mas.md:22
- slave window of 4 KB → hw/grape_pipeline/docs/mas.md:11
- `NSTEPS` (32-bit) → hw/docs/hardware_report.md:120
- 15 register rows → hw/grape_pipeline/docs/integration.md:15
- 3-stage, IEEE binary64 RNE → hw/grape_pipeline/docs/uarch.md:20
- 30 ± 2 cycles, **II = 2** → hw/grape_pipeline/docs/uarch.md:22
- **22 ± 2 cycles** → hw/grape_pipeline/docs/uarch.md:23
- three FP64 add/sub, three multipliers, one sqrt (radix-4 SRT) → hw/docs/hardware_report.md:135
- There is no FMA — multiply and accumulate round separately → hw/docs/hardware_report.md:139
- **290-operation step** → hw/docs/hardware_report.md:137
- 3 add, 3 mul (chosen)** | **123** | **127 ✓** → hw/grape_pipeline/docs/uarch.md:164
- **≤ 128** → hw/grape_pipeline/docs/prd.md:30
- design target **50 MHz** → hw/docs/hardware_report.md:121
- performed in exactly the → hw/docs/adr/0002-grape-fp64-datapath-and-tolerance-oracle.md:10

## S09 · K1 is 124 cycles per step against a budget of 128, found only after the full-shape test exposed 162
- owner: Y
- status: DRAFT
- stage: Accelerate
- seconds: 45
- visual: table
- exempt: 1, 2, 3, 10

table:
| Design point | Cells (Yosys) | Area | K1 cycles/step | Verdict |
|---|---|---|---|---|
| 1-wide accumulate, 1-port RF | 393,367 | 2.938 mm² | 162 | fails K1 ≤ 128 |
| 3-wide accumulate, 3-port RF | 584,454 | 4.075 mm² | 124 | chosen: +38.7% area, −23.5% cycles |

notes:
The uArch model predicted 123 cycles per step, and the bring-up smoke test measured 126, so every gate was green until sign-off. The sign-off test runs the real workload, all ten pairs for 20,000 steps, and there K1 was 162: the smoke test used only two pairs, a shape in which the static schedule hides the accumulate phase, and the RTL had implemented the ordered velocity accumulate as single-issue. Widening it to three ops per cycle, with a per-lane integrate and a 3-port body register file, brought K1 to 124, inside the model's 123 to 127 window. Both design points are fully synthesized, so the trade-off is measured: 38.7% more area for 23.5% fewer cycles. Renegotiating K1 to 162 was offered and declined at the sign-off checkpoint.

sources:
- 393,367 | 2.938 | **162.0** → hw/grape_pipeline/docs/ppa.md:37
- 584,454 | 4.075 | **124.0** → hw/grape_pipeline/docs/ppa.md:38
- **4.075 mm²** | **124** | **chosen** (+38.7 % area, −23.5 % cycles) → hw/docs/hardware_report.md:217
- **≤ 128** → hw/grape_pipeline/docs/prd.md:30
- 20,000 steps → hw/docs/hardware_report.md:110
- K1 measured 162 cycles/step at sign-off → hw/docs/lessons.md:212
- smoke (126) used NPAIRS=2 → hw/docs/lessons.md:213
- the model's 123 assumed uArch §3.3's "everything else overlaps" → hw/docs/lessons.md:214
- 124 — inside the model's 123..127 window → hw/docs/lessons.md:217
- renegotiating K1 to 162) was declined at the → hw/grape_pipeline/docs/ppa.md:41
- 3 add, 3 mul (chosen)** | **123** | **127 ✓** → hw/grape_pipeline/docs/uarch.md:164

## S10 · Post-CTS timing gives 19.46 MHz against a 50 MHz target; the accumulate picker set the clock and a parallel-prefix rewrite bought 1.75x
- owner: Y
- status: DRAFT
- stage: Trade-offs
- seconds: 45
- visual: table
- exempt: 3

table:
| Metric | Value | Evidence level |
|---|---|---|
| Cells / area, plain Yosys | 584,454 / 4.075 mm² | synthesis before the final picker rewrite |
| Cells / area, OpenLane recipe, final RTL | 446,932 / 4.66 mm² | different recipe, not comparable with the row above |
| Fmax, post-CTS STA | 11.15 → 19.46 MHz (1.75x), bit-exact | extrapolated from a 150 ns run with 98.6 ns slack |
| Power | ≈ 19.2 mW | tool estimate, default activity, indicative only |
| Clock target | 50 MHz, missed 2.6x | next limiter: integrate-multiplier operand path |

notes:
The area figures come from two synthesis recipes: plain Yosys on the netlist before the final rewrite, and OpenLane's own synthesis of the final RTL; they are not comparable with each other. The clock story is the interesting one. The first post-CTS run gave 11.15 MHz, and the critical path was the 3-wide accumulate issue picker, a 60-deep combinational scan. Rewriting the two prefix operations as balanced trees removed that path without adding a cycle: 19.46 MHz, 1.75x, K1 still 124, every output bit-exact. That number is an extrapolation: the run was constrained at 150 ns and back-computes 51.38 ns from 98.6 ns of slack, and unlike the other two modules grape has no confirmation run near the result. The 50 MHz target is missed 2.6x; the new limiter is the integrate-multiplier operand path.

sources:
- **4.075 mm² / 584,454 cells** → hw/docs/hardware_report.md:212
- **446,932 cells / 4.66 mm²** → hw/docs/hardware_report.md:212
- The two recipes are not comparable with each other → hw/docs/hardware_report.md:212
- Fmax 11.15 → 19.46 MHz (1.75×); worst-path delay 89.68 → 51.38 ns → hw/grape_pipeline/docs/ppa.md:123
- K1 = 124 unchanged → hw/grape_pipeline/docs/ppa.md:124
- Power **≈ 19.2 mW** post-CTS tool estimate → hw/docs/hardware_report.md:219
- default switching activity at the 150 ns run constraint → hw/docs/hardware_report.md:220
- design target **50 MHz** → hw/docs/hardware_report.md:121
- 50 MHz target (~2.6×) → hw/grape_pipeline/docs/ppa.md:126-127
- run constrained at 150 ns with 98.6 ns of slack → hw/docs/hardware_report.md:126
- **grape has none.** → hw/docs/hardware_report.md:129
- ~60-iteration in-order → hw/grape_pipeline/docs/ppa.md:93

## S11 · At 19.46 MHz grape ties optimized Python and is about 15x slower than Rust
- owner: Y
- status: DRAFT
- stage: Trade-offs
- seconds: 45
- visual: table
- exempt: 5

table:
| Tier | Time / run | vs original | Evidence |
|---|---|---|---|
| Original Python | 231.20 ms | 1.00x | measured, course VM |
| Optimized Python | 143.13 ms | 1.62x | measured, course VM |
| grape @ 19.46 MHz | ≈ 139 ms = 127.4 ms compute + 11.6 ms residual | ≈ 1.66x | projected |
| Native Rust | 9.530 ms | 24.26x | measured, course VM |

notes:
This is the honest result. Compute is 2.48 million measured RTL cycles divided by the 19.46 MHz post-CTS clock, 127.4 ms. We add an assumed 5% Python residual for the harness and the two energy evaluations, 11.6 ms; nobody has measured that residual, and no software has ever called this hardware, so the interface time is unmeasured and can only make the row slower. The projection lands at about 139 ms: 1.66x over the original, a tie with optimized Python at 1.03x, and about 15x slower than the 9.53 ms Rust tier. Per step that is 124 cycles or 6.4 µs against 0.48 µs natively. The cause is the clock, not the interface; the residual alone already exceeds the whole Rust run.

sources:
- | Original Python | 231.20 ms | 1.00× | → hw/docs/hardware_report.md:180
- | Optimized Python | 143.13 ms | 1.62× | → hw/docs/hardware_report.md:181
- | Native Rust | 9.53 ms | 24.26× | → hw/docs/hardware_report.md:182
- 9.530 ± 0.050 ms → report_nbody.txt:189
- **≈ 139 ms** | **≈ 1.66×** → hw/docs/hardware_report.md:183
- t_hw = 127.4 ms → **≈ 1.66×** → hw/docs/hardware_report.md:172
- 2,480,000 cycles/invocation → hw/docs/hardware_report.md:168
- 2.48 Mcycles → report/defense_guide.md:46
- Achievable **≈ 19.46 MHz** → hw/docs/hardware_report.md:122
- level with optimized Python (1.03×) and ≈ 15× slower than native Rust → hw/docs/hardware_report.md:186
- Per step: 124 cycles = 6.4 µs at 19.46 MHz vs 0.48 µs natively → hw/docs/hardware_report.md:187
- the 11.6 ms Python residual alone already exceeds Rust's 9.53 ms → hw/docs/hardware_report.md:188
- assumes a 5 % Python residual → hw/docs/hardware_report.md:475
- DMA/host-interface cost is **not measured** → hw/docs/hardware_report.md:473

## S12 · What would beat Rust: the clock it takes, a wider unit mix, and a Rust host around the same hardware
- owner: Y
- status: DRAFT
- stage: Trade-offs
- seconds: 30
- visual: table
- exempt: 3, 4, 5, 6, 12, 24

table:
| Projection (not a measurement) | Compute time | vs Rust 9.530 ms | What it assumes |
|---|---|---|---|
| Clock at which grape compute alone matches Rust | 2.48 Mcycles / 9.530 ms ≈ 260 MHz | parity | 13.4x the post-CTS clock; zero residual |
| grape at the 50 MHz target | 49.6 ms (+11.6 ms residual = 61.16 ms, 3.78x vs original) | 6.42x slower | timing closure we did not reach |
| 3 add + 4 mul, schedule model | 117 cycles/step → 120.2 ms at 19.46 MHz | 12.6x slower | model only; needs 245 MHz for parity |
| Rust host + same hardware at 19.46 MHz | 127.4 + 0.48 ms = 127.9 ms | 13.4x slower | residual scales to 5% of the Rust run |
| N = 100 with 24 add + 24 mul + 2 sqrt + 2 rcp | 0.029 µs/pair at 19.46 MHz | 1.6x faster | clock survives 8x wider issue; SRAM state |

notes:
Everything on this slide is a projection from the schedule model and the report's numbers; derivations.md holds the arithmetic. Clock: the datapath alone matches Rust at about 260 MHz, 13.4 times what post-CTS timing supports; at the 50 MHz target the system would still be 6.42x slower. Width: a fourth multiplier saves 6 cycles per step in the model, 123 to 117, because at N = 5 one pair's 80-cycle chain bounds the step. Host: swapping Python for Rust around the same device trims the residual from 11.6 ms to about 0.48 ms, an 8% change. Only more bodies change the verdict: at N = 100 the model needs 24 adders and 24 multipliers to run 1.6x faster than native, assuming the clock survives the wider issue logic, which our own 1-wide versus 3-wide data says it does not.

sources:
- Result: 260.2 MHz, i.e. about 260 MHz → presentation/derivations.md:20
- 13.4× the 19.46 MHz post-CTS clock → presentation/derivations.md:23
- Rust needs ≈ 260 MHz → hw/docs/hardware_report.md:188
- 2,480,000 cycles/invocation → hw/docs/hardware_report.md:168
- 2.48 Mcycles → report/defense_guide.md:46
- 9.530 ± 0.050 ms → report_nbody.txt:189
- t_hw = 49.6 ms compute → presentation/derivations.md:29
- T_new = 11.56 + 49.6 = 61.16 ms → S = 3.78× → presentation/derivations.md:30
- vs Rust: 61.16 / 9.530 = 6.42× slower → presentation/derivations.md:31
- 3 add, 4 mul: 117 cycles/step → presentation/derivations.md:45
- 3 add, 3 mul: 123 cycles/step → presentation/derivations.md:44
- At 19.46 MHz: 2,340,000 / 19.46 MHz = 120.2 ms compute → presentation/derivations.md:57
- 245.5 MHz, about 245 MHz → presentation/derivations.md:59
- 12.6× slower than Rust → presentation/derivations.md:59
- 0.05 × 9.530 = 0.48 ms → presentation/derivations.md:64
- Rust host + grape @ 19.46 MHz: 0.48 + 127.4 = 127.9 ms; 13.4× slower → presentation/derivations.md:69
- removes 11.1 ms (11.56 − 0.48), an 8 % change → presentation/derivations.md:72
- 11.6 ms Python residual → hw/docs/hardware_report.md:188
- 24 add + 24 mul + 2 sqrt + 2 rcp at N = 100: 0.56 cycles/pair = 0.029 µs/pair → presentation/derivations.md:97
- 1.6× faster → hw/docs/hardware_report.md:197
- one pair's chain is ≈ 80 cycles → hw/docs/hardware_report.md:193
- 5 % Python residual → hw/docs/hardware_report.md:176
- 50 MHz → hw/docs/hardware_report.md:121

## S24 · We ran a ten-stage flow with four human checkpoints: agents pre-reviewed, humans decided
- owner: Y
- status: DRAFT
- stage: Trade-offs
- seconds: 30
- visual: assets/hw_flow.png
- exempt: 3, 4, 10

notes:
The picture is the flow every module went through: PRD, architecture spec, micro-architecture, RTL, then verification in four stages, PPA and integration, ten stages in all. Each stage has an exit gate with recorded evidence; across three modules that is 136 gate criteria in the status file. Four of the gates are human checkpoints: PRD, MAS, uArch and DV sign-off. Before each checkpoint an agent pre-reviewed the artifact and wrote a findings table; counting the rows of those tables gives about 350 findings, 126 of them rated must, all resolved before the gate closed. The division of labour was fixed: agents draft and pre-review, the human reads the findings and approves or sends it back. The K1 decision on the previous slides is one such checkpoint.

sources:
- 136 gate criteria (3 modules × 10 stages, 30 gates) → presentation/derivations.md:102
- PRD, MAS, uArch, DV sign-off → hw/FLOW.md:23
- 354 table rows → presentation/derivations.md:104
- about 350 review findings → presentation/derivations.md:104
- 126 must → presentation/derivations.md:104
- Agent pre-review (`hw-review`) run before every checkpoint → hw/FLOW.md:24
- PRD → MAS → uArch → RTL → DV[testplan → bring-up → coverage closure → sign-off] → PPA → HW/SW integration → hw/FLOW.md:3

## S25 · What the evidence does and does not say: post-CTS timing, one extrapolated clock, unmeasured interface time, un-re-timed commits
- owner: Y
- status: DRAFT
- stage: Trade-offs
- seconds: 30
- visual: table
- exempt: 5

table:
| Claim on these slides | What the evidence is | What it is not |
|---|---|---|
| Fmax of all three modules | post-CTS static timing, placed clock tree | routed GDS or silicon |
| grape 19.46 MHz | 2.9x extrapolation from a met 150 ns run | a confirmation run near 51 ns |
| End-to-end speedups | RTL cycles / STA clock + a 5% residual assumption | a measured interface or DMA time |
| grape 4.075 mm², ≈ 19.2 mW | Yosys area before the final rewrite; default-activity power | comparable with the OpenLane area or across modules |
| Software timings | one canonical VM run of one revision | re-timed after the last commits |
| Native bit-identity | checked on the tested configurations | a guarantee for other builds |

notes:
Every hardware frequency here is a post-CTS static-timing estimate: cells and clock tree placed, signal wires not routed, no silicon. grape's 19.46 MHz is the weakest number in the deck, back-computed from a run constrained at 150 ns, a 2.9x extrapolation with no confirmation run. Every end-to-end speedup is a projection: measured RTL cycles over that clock, plus a 5% Python residual we assumed rather than measured, and no interface or DMA time at all. The grape area predates the final picker rewrite; the OpenLane area of the final RTL uses a different recipe. Power figures use default switching activity at three different clocks, so they are indicative and not comparable. On the software side, later commits pass the exactness oracle but were not re-timed.

sources:
- **All three Fmax numbers are post-CTS STA** → hw/docs/hardware_report.md:460
- None completed routed GDS sign-off (no die shot) → hw/docs/hardware_report.md:461
- a 2.9× extrapolation → hw/docs/hardware_report.md:126
- run constrained at 150 ns → hw/docs/hardware_report.md:126
- A run near 51 ns would → hw/docs/hardware_report.md:129
- **grape has none.** → hw/docs/hardware_report.md:129
- Achievable **≈ 19.46 MHz** → hw/docs/hardware_report.md:122
- DMA/host-interface cost is **not measured** → hw/docs/hardware_report.md:473
- assumes a 5 % Python residual → hw/docs/hardware_report.md:475
- **4.075 mm² / 584,454 cells** (plain Yosys, synthesized before the final issue-selection rewrite → hw/docs/hardware_report.md:212
- Power **≈ 19.2 mW** post-CTS tool estimate → hw/docs/hardware_report.md:219
- use default activity at three different run clocks → hw/docs/hardware_report.md:469
- exactness oracle but were not re-timed → report_nbody.txt:174
- bit-identical in state and energy after 20,000 steps → report_nbody.txt:183

## B01 · grape's step is a fixed 290-operation graph scheduled onto 3 adders and 3 multipliers
- owner: Y
- status: DRAFT
- stage: Accelerate
- visual: assets/grape_uarch.png
- answers: Q19, architecture depth
- exempt: 2, 3, 4, 6, 8, 10

notes:
Datapath: pair i issues at cycle 2i into the shared units. Per pair, the front end subtracts the three coordinates, squares and sums them, takes the square root, multiplies to d3, takes the reciprocal, then forms the magnitude and the six force terms; every one of those is a Python-visible binary64 rounding held in its own register. Per step that is 125 adds, 145 multiplies, 10 square roots and 10 reciprocals, 290 operations, which a greedy list scheduler places on the units as a static reservation table checked by an SVA assertion. Control: the step FSM is IDLE, LATCH, RUN, COMMIT, DONE or ABORT; RUN ends when all 290 ops have retired and ABORT is sampled only at COMMIT. The accumulate sequencer keeps a 5-by-3 busy scoreboard per body component so velocity updates on one lane stay in program order. Timing budget: each pipeline stage was estimated at 8 ns or less against the 20 ns period, which is why the 50 MHz target looked comfortable on paper; the picker path that later set the clock was not in that table.

sources:
- pair i issues at cycle 2i → hw/grape_pipeline/docs/uarch.md:32
- 125 ADD, 145 MUL, 10 SQRT → hw/grape_pipeline/docs/uarch.md:157
- 290-op graph → hw/grape_pipeline/docs/uarch.md:155
- RUN --> COMMIT: all 290 step ops retired → hw/grape_pipeline/docs/uarch.md:64
- ABORT is sampled only in COMMIT → hw/grape_pipeline/docs/uarch.md:78
- A 5 × 3 → hw/grape_pipeline/docs/uarch.md:93
- Every stage ≤ 8 ns < 20 ns budget ⇒ 50 MHz comfortable → hw/grape_pipeline/docs/uarch.md:148
- Every Python-visible intermediate is a rounded binary64 value in its own pipeline register → hw/grape_pipeline/docs/uarch.md:126
- checked by an SVA assertion → hw/grape_pipeline/docs/uarch.md:172

## B02 · The 162-cycle miss hid behind a 2-pair smoke test; the full-shape test at sign-off found it
- owner: Y
- status: DRAFT
- stage: Accelerate
- visual: table
- answers: Q21, what did verification find
- exempt: 2, 10

table:
| Stage | Workload | K1 cycles/step | Result |
|---|---|---|---|
| uArch schedule model | 290-op graph, nominal / worst corner | 123 / 127 | within 128 |
| DV bring-up smoke | 2 pairs, 2 steps | 126 | within 128, gate green |
| DV sign-off, full benchmark | 10 pairs, 20,000 steps | 162 | fails 128 |
| After 3-wide accumulate + per-lane integrate | 10 pairs, 20,000 steps | 124 | passes; smoke fell to 111 |

notes:
The model said 123, the smoke test said 126, and both were honest; the smoke shape simply could not show the problem. With two pairs the static force schedule dominates and the accumulate phase is hidden; with ten pairs the single-issue accumulate and the globally gated integrate serialized, and the real benchmark measured 162. The fix, widening the accumulate to three issues per cycle and letting each lane integrate as soon as its own chain retires, landed at 124, and the same smoke test then read 111. The lesson written into the flow: measure the KPI on the full-shape workload at bring-up, not only on the tiny smoke; the gap was visible one stage earlier to anyone who ran ten pairs. The huffman module paid that rule back on its first full-shape run.

sources:
- 3 add, 3 mul (chosen)** | **123** | **127 ✓** → hw/grape_pipeline/docs/uarch.md:164
- 290-op graph → hw/grape_pipeline/docs/uarch.md:155
- **≤ 128** → hw/grape_pipeline/docs/prd.md:30
- 126.0 / 34.7 figures → hw/grape_pipeline/docs/review_bringup.md:58
- NPAIRS=2/NSTEPS=2 → hw/grape_pipeline/docs/review_bringup.md:53
- K1 measured 162 cycles/step at sign-off → hw/docs/lessons.md:212
- smoke (126) used NPAIRS=2 → hw/docs/lessons.md:213
- 124 — inside the model's 123..127 window → hw/docs/lessons.md:217
- full-shape workload (all pairs) at bring-up → hw/docs/lessons.md:218
- 20,000 steps → hw/docs/hardware_report.md:110
- 5 bodies and up to 10 pairs → hw/grape_pipeline/docs/prd.md:57
- smoke K1 → hw/grape_pipeline/docs/review_signoff.md:172
- 126 -> 111 → hw/grape_pipeline/docs/review_signoff.md:173
- paid for itself in one stage → hw/docs/lessons.md:344

## B03 · Unit-mix sweep: 2+2 → 133 cycles, 3+3 → 123/127, 3+4 → 117; 3+3 is the last point under 128
- owner: Y
- status: DRAFT
- stage: Accelerate
- visual: table
- answers: Q21, grape trade-off
- exempt: 2, 3, 4, 6, 10

table:
| Inventory | Step cycles, nominal (sqrt 30 / rcp 22) | Worst corner (32 / 24) | Verdict |
|---|---|---|---|
| 2 add, 2 mul | 133 | 137 | issue-bandwidth bound: 145 mul-ops per step |
| 2 add, 3 mul | 125 | 129 | fails the worst corner by 1 cycle |
| 3 add, 3 mul | 123 | 127 | chosen: last point under 128 at both corners |
| 3 add, 4 mul | 117 | 121 | 6 cycles for a fourth multiplier |

notes:
The sweep is simulated, not estimated: schedule_model.py builds the 290-operation step and list-schedules it onto each inventory, with the unit latencies at nominal and at a two-cycle-slower corner for sqrt and reciprocal. Two multipliers cannot carry 145 mul-ops per step, so both 2-mul points sit at 133. Two adders with three multipliers make the nominal budget at 125 but miss the worst corner by one cycle, so the ADR rejected it. Three of each gives 123 and 127, the last mix that passes at both corners, and it is what the RTL implements. A fourth multiplier buys 6 cycles because at N = 5 the step is latency-bound by one pair's chain; the stretch goal of 64 cycles was declared unreachable at issue interval 2 and not pursued. The output of the model, rerun for this deck, is copied into derivations.md.

sources:
- | 2 add, 2 mul | 133 | → hw/grape_pipeline/docs/uarch.md:162
- | 2 add, 3 mul | 125 | 129 ✗ | → hw/grape_pipeline/docs/uarch.md:163
- 3 add, 3 mul (chosen)** | **123** | **127 ✓** → hw/grape_pipeline/docs/uarch.md:164
- | 3 add, 4 mul | 117 | → hw/grape_pipeline/docs/uarch.md:165
- 2 add, 2 mul: 137 cycles/step → presentation/derivations.md:47
- 3 add, 4 mul: 121 cycles/step → presentation/derivations.md:52
- 125 ADD, 145 MUL, 10 SQRT → hw/grape_pipeline/docs/uarch.md:157
- 290-op graph → hw/grape_pipeline/docs/uarch.md:155
- **≤ 128** → hw/grape_pipeline/docs/prd.md:30
- (2 add/3 mul = 125/129 — rejected, 1 cycle over at the corner → hw/docs/adr/0007-grape-own-fp64-datapath.md:21
- The PRD stretch (≤ 64) is → hw/grape_pipeline/docs/uarch.md:170
- one pair's chain is ≈ 80 cycles → hw/docs/hardware_report.md:193

## B06 · Verification evidence per module: tests, line/toggle/branch coverage, formal, both simulators
- owner: Y
- status: DRAFT
- stage: Accelerate
- visual: table
- answers: Q22, what is verified
- exempt: 3, 4, 5, 7, 9, 16, 17

table:
| Evidence | grape_pipeline | huffman_engine | mtf_cam |
|---|---|---|---|
| Directed + random tests, Verilator and Icarus | 9/9 | 17/17 | 16/16 |
| Line / toggle coverage | 91.7% / 96.0% (all signals) | 90.4% / 90.3% (control subset) | 92.0% / 93.8% (control subset) |
| Branch coverage; functional bins hit | 94.8%; 59 | 91.7%; 34 | 96.8%; 129 |
| Golden equivalence on the real input | 20,000 steps, 0 mismatches | 148,271 beats trace-exact | 336,184 bytes byte-exact |
| Formal (SymbiYosys) | FSM arcs, BMC depth 40 + cover | 4 tasks: ctrl arcs, skid, aligner cap | 7 tasks; unbounded at 16 entries, bounded at 256 |

notes:
Every module runs its full directed plus constrained-random suite on Verilator and again on Icarus, the 4-state simulator that shows X after reset. The scoreboard oracle is the benchmark's own Python code, and each module is checked on the real benchmark input end to end: grape bit-exact over 20,000 steps, huffman trace-exact over 148,271 beats, mtf byte-exact over 336,184 bytes, and the huffman-to-mtf chain is co-simulated as well. Coverage carries a caveat: huffman and mtf toggle coverage is measured over the control-signal subset, because wide data buses whose upper bits the benchmark cannot toggle are waived with the width sweep as evidence; grape's is over all signals. Formal covers control properties only: grape's FSM arcs at BMC depth 40, huffman's four tasks, and mtf's list invariants, unbounded at 16 entries but only bounded at the production 256.

sources:
- | Directed + random tests | 9/9 | 17/17 | 16/16 | → hw/docs/hardware_report.md:446
- | Line / toggle coverage | 91.7 % / 96.0 % | 90.4 % / 90.3 %† | 92.0 % / 93.8 %† | → hw/docs/hardware_report.md:447
- coverage: 94.8 % / 91.7 % / 96.8 % → hw/docs/hardware_report.md:457
- (59 / 34 / 129 functional bins, all hit) → hw/docs/hardware_report.md:458
- **control-signal subset** (signals ≤ 4 bits → hw/docs/hardware_report.md:454
- grape's is over all signals → hw/docs/hardware_report.md:456
- cross-checked 4-state on Icarus → hw/docs/hardware_report.md:47
- 20,000 steps → hw/docs/hardware_report.md:110
- **0 mismatches** → hw/grape_pipeline/docs/ppa.md:108
- huffman trace-exact 148,271 beats; mtf byte-exact 336,184 B → hw/docs/hardware_report.md:390
- PASS at BMC depth 40 → hw/grape_pipeline/docs/testplan.md:123
- formal (4/4) → hw/huffman_engine/docs/review_signoff.md:34
- proven **unbounded @ N_LIST=16** → hw/docs/hardware_report.md:483
- **N_LIST=256** the general check (`bmc`) is bounded to **depth 6** → hw/docs/hardware_report.md:484
- All seven tasks → hw/docs/hardware_report.md:487

## B07 · Speedup at two altitudes agrees: 25x on a 13.4% slice is 1.148x; two profilers give f = 0.496 vs 0.40
- owner: Y
- status: DRAFT
- stage: Trade-offs
- visual: table
- answers: G4, Amdahl, profiler denominators
- exempt: 2

table:
| Question | Numbers | Reading |
|---|---|---|
| mtf stage alone vs whole benchmark | 80.4 ms / 3.169 ms = 25.4x at 50 MHz; 1/((1−0.1344)+0.1344/25) = 1.148x | same result at two altitudes |
| huffman f from cProfile (PRD) | f = 0.496 → 1/(1−0.496) = 1.98x | per-call overhead inflates tiny bit-reader calls |
| huffman f from VM py-spy (report) | f = 0.40 → 1/(1−0.40) = 1.67x | sampled; the one the reports use |
| mtf standalone ceiling | f = 0.1344 → 1.16x | why it is chained, not standalone |
| Chain, measured at the Rust boundary | ≈ 28x over the Python loop, ≈ 1.3x slower than Rust, ≈ 6.6x end to end | the figure the reports quote |

notes:
Two questions the reviewers asked. First, how can a stage be 25x faster while the benchmark barely moves? Because the move-to-front stage is 13.44% of the original run: a 25x stage speedup on that slice gives 1.148x by Amdahl, and both numbers describe the same result, one at stage altitude and one at benchmark altitude. Second, why did the huffman fraction change? The PRD sized the module from a local cProfile run, f = 0.496, a 1.98x ceiling; cProfile's per-call overhead inflates the many tiny bit-reader calls. The sampled py-spy profile on the course VM gives 0.40 and a 1.67x ceiling, and that is the denominator the reports use. Neither standalone figure is a report claim; the reports quote the chain measured at the Rust boundary.

sources:
- stage speedup = 80.4 / 3.169 = → hw/mtf_cam/docs/integration.md:127
- **25.4×** → hw/mtf_cam/docs/integration.md:128
- a ~25× stage speedup on a 13.44 % slice → hw/mtf_cam/docs/integration.md:131
- `1/((1 − 0.1344) + 0.1344/25) = ` **1.148×** → hw/mtf_cam/docs/integration.md:132
- f = 0.496, 12.0 % decode + 37.6 % bit reader → hw/docs/hardware_report.md:261
- cProfile fraction gave 1.98× → hw/docs/hardware_report.md:269
- `f` ≈ **0.40** → hw/docs/hardware_report.md:258
- that stage is only 13.4 % of the → hw/mtf_cam/docs/integration.md:134
- 1/(1 − 0.40) = 1.67× → hw/docs/hardware_report.md:267
- `f` = **0.1344** → hw/docs/hardware_report.md:331
- Standalone Amdahl ceiling at f = 0.1344: 1.16× → hw/docs/hardware_report.md:335
- ≈ 28× faster and runs ≈ 1.3× slower than the Rust kernel → hw/docs/hardware_report.md:338
- end to end ≈ 6.6× vs the original → hw/docs/hardware_report.md:339
- 50 MHz → hw/docs/hardware_report.md:121

## B10 · How we used AI: a stage-gated flow, prompt.txt as the log, and the decisions humans made
- owner: Y+M
- status: DRAFT
- stage: Trade-offs
- visual: table
- answers: G11, what did you decide versus the agent
- exempt: 3, 4, 10

table:
| Decision | Options came from | Decided by | Where recorded |
|---|---|---|---|
| FP64 in the benchmark's order, no FMA | agent research + uArch review finding R1 | Yuval, ADR-0002 / ADR-0007, uArch checkpoint | hw/docs/adr, review_uarch.md |
| 3 add + 3 mul unit mix | agent schedule-model sweep | Yuval at the uArch checkpoint | uarch.md §7 |
| Boundary: whole advance() on-chip, MMIO only | PRD grilling interview | Yuval at the PRD and MAS checkpoints | prd.md §4, ADR-0001 |
| Keep K1 ≤ 128 rather than renegotiate to 162 | agent offered both at sign-off | Yuval at the DV sign-off checkpoint | ppa.md |
| Accept the 50 MHz miss and report 19.46 MHz with caveats | PPA stage | Yuval | ppa.md §7 framing |
| Retire the MDP benchmark | scope review | Matan | CLOSEOUT.md |

notes:
The agent, Claude Code, drafted RTL, testbenches, flow documents and report text; every prompt is in prompt.txt, hand-written at first and auto-logged by a hook afterwards, 220 dated entries over the project. What kept it honest was the flow: ten stages with gates, four of them human checkpoints, and an agent pre-review before each checkpoint whose findings table the human read before approving. Yuval directed the hardware flow and reviewed each gate; Matan designed and measured the software ladder and ran the course-VM measurements. The table lists the decisions a grader may ask about and who made them. The pattern is the same each time: the agent produced options and evidence, the human chose, and the choice is written in an ADR, a checkpoint approval or a close-out record.

sources:
- 220 dated entries → presentation/derivations.md:105
- Claude Code (Anthropic) throughout → README.md:22
- auto-logged by a hook → README.md:23
- Yuval Kogan directed the hardware flow → README.md:24
- Matan Cohen → README.md:25
- PRD, MAS, uArch, DV sign-off → hw/FLOW.md:23
- Agent pre-review (`hw-review`) run before every checkpoint → hw/FLOW.md:24
- **no FMA units**: force terms rounded by MUL → hw/grape_pipeline/docs/review_uarch.md:9
- **no FMA units at all** → hw/docs/adr/0007-grape-own-fp64-datapath.md:15
- Status: **approved** 2026-09-04 (uArch checkpoint) → hw/grape_pipeline/docs/uarch.md:3
- Status: **approved** 2026-08-28 (PRD checkpoint) → hw/grape_pipeline/docs/prd.md:3
- renegotiating K1 to 162) was declined at the → hw/grape_pipeline/docs/ppa.md:41
- **≤ 128** → hw/grape_pipeline/docs/prd.md:30
- Achievable **≈ 19.46 MHz** → hw/docs/hardware_report.md:122
- design target **50 MHz** → hw/docs/hardware_report.md:121
- Why no MDP? [M] — retired to focus the two-benchmark scope → report/CLOSEOUT.md:214
