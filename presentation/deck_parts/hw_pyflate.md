# pyflate hardware slides (S18–S23, B04, B05, B08, B09)

Owner Y. Spec format per `presentation/STRATEGY.md`; storyboard order. Merged into `deck.md` by the deck owner.

## S18 · Huffman decode is a 0.40 fraction of the original run, a 1.67× ceiling alone, so we chain it with move-to-front on one AXI stream
- owner: Y
- status: DRAFT
- stage: Accelerate
- seconds: 45
- visual: assets/decode_report.png

notes:
On the VM py-spy profile, Huffman symbol decode plus its bit reader is f = 0.40 of the 1,123.49 ms original, so even an infinitely fast decoder caps at 1/(1 − 0.40) = 1.67×. Move-to-front is another 0.1344 and consumes exactly the decoder's 148,271 output symbols, so the two are chained on chip; that covers about half the run on this profile (the module doc's ≈ 0.63 and ≈ 2.7× ceiling summed the older cProfile Huffman share of 49.6 %). Who does what: the CPU parses each block header, writes the 6 × 147 code lengths and the used-byte map over AXI4-Lite, starts both modules, then runs inverse BWT, RLE4 and MD5. The hardware builds its tables, decodes, and hands each symbol to mtf_cam as one 32-bit AXI-Stream beat, value in TDATA[8:0], type in [11:9] (ADR-0006); platform DMA returns the L-vector.

sources:
- 1/(1 − 0.40) = 1.67× → hw/docs/hardware_report.md:267
- 1,123.49 ms → hw/docs/hardware_report.md:257
- f ≈ 0.40 → hw/docs/hardware_report.md:258
- 0.1344 → hw/docs/hardware_report.md:331
- 148,271 link beats → hw/docs/hardware_report.md:396
- f ≈ 0.63 → hw/mtf_cam/docs/integration.md:138
- ≈ 2.7× → hw/mtf_cam/docs/integration.md:138
- 49.6 % → hw/mtf_cam/docs/integration.md:137
- 6 × 147 code lengths → hw/docs/adr/0003-huffman-engine-architecture-and-hw-sw-boundary.md:15
- headers parsed in software → hw/docs/adr/0003-huffman-engine-architecture-and-hw-sw-boundary.md:4
- TDATA[8:0] → hw/docs/adr/0006-symbol-stream-beat-encoding.md:7
- parses the header, writes the code lengths → report_pyflate.txt:335
- inverse BWT, RLE4 and MD5 → report_pyflate.txt:334

## S19 · huffman_engine decodes one symbol per cycle: a barrel shifter, 20 parallel comparators, and six preloaded table sets so a table switch costs zero cycles
- owner: Y
- status: DRAFT
- stage: Accelerate
- seconds: 60
- visual: assets/huffman_block_diagram.png

notes:
The only serial dependency is the recurrence: where symbol N+1 starts depends on symbol N's length. So that loop is one cycle: barrel-shift the 64-bit window, compare it against the first-code threshold of all 20 lengths in parallel, priority-encode the shortest match, consume; symbol-table lookup and beat emission pipeline behind the loop. bzip2 switches tables every 50 symbols, so six table register sets are preloaded and the switch is 0-cycle (ADR-0008). Inputs: a 32-bit compressed stream and an 8-bit selector stream; output: 32-bit beats with a 9-bit symbol; target 50 MHz. On the real block: 149,276 cycles for 148,271 symbols, K1 = 1.0068 against a budget of 1.10. The first full-shape run showed 1.5068, an almost-full gate that ignored the same-cycle pop, fixed in one line; un-gating DEFLATE at coverage then exposed an extra-bit-count latching bug the unit tests never reached.

sources:
- 20 parallel `first_code[len]` compares → hw/docs/adr/0008-huffman-decode-loop.md:12
- 64-bit shift buffer + barrel shifter → hw/docs/adr/0008-huffman-decode-loop.md:17
- 0-cycle switch → hw/docs/hardware_report.md:247
- 50 symbols → hw/docs/hardware_report.md:247
- 32-bit compressed stream + 8-bit selector stream → hw/docs/hardware_report.md:236
- 9-bit symbol → hw/docs/hardware_report.md:237
- 50 MHz → hw/docs/hardware_report.md:239
- 149,276 cycles for 148,271 symbols → hw/docs/hardware_report.md:265
- K1 = 1.0068 → hw/docs/hardware_report.md:265
- ≤ 1.10 → hw/huffman_engine/docs/prd.md:49
- K1 = 1.5068 vs model 1.0068 → hw/docs/lessons.md:345
- One-line fix → hw/docs/lessons.md:347
- extra-bit COUNTS → hw/docs/lessons.md:372

## S20 · mtf_cam is a 256-entry shift-register list read by rank; width 8 sits at the knee of the area/cycle sweep
- owner: Y
- status: DRAFT
- stage: Accelerate
- seconds: 45
- visual: table

table:
| W (output bytes/beat) | Area | K3 model (cyc/sym) | K3 ≤ 1.10 | Verdict |
|---|---:|---:|---|---|
| 4 | 0.182 mm² | 1.175 | fails | rejected |
| 8 | 0.187 mm² | 1.063 | meets | chosen: the knee |
| 16 | 0.208 mm² | 1.023 | meets | +10.9 % area for 3.8 % fewer cycles, not needed |

notes:
Each bzip2 symbol is a rank into a 256-entry list of recently used bytes: emit that byte and move it to the front. Hardware: a 256 × 8 shift register with a 256:1 read mux; every entry is writable each cycle, so the move takes one cycle and needs no RAM (the "CAM" is the list; nothing is content-searched). Run groups expand through a W-byte packer; W is the knob: W = 4 breaks the K3 ≤ 1.10 KPI, W = 16 costs 10.9 % more area for 3.8 % fewer cycles, so W = 8 is the knee; the list is 68 % of the 0.187 mm². Measured: 158,441 cycles, K3 = 1.0686 against the 1.063 model. The uArch review caught that the cycle model enqueues two items in one cycle, so the item FIFO needed a 2-wide write port; with one port K3 lands near 1.30.

sources:
- 256-entry move-to-front list → hw/docs/hardware_report.md:302
- 0.182 | 1.175 | fails K3 ≤ 1.10 → hw/docs/hardware_report.md:355
- 0.187 → hw/docs/hardware_report.md:356
- 1.063 → hw/docs/hardware_report.md:356
- 0.208 | 1.023 | +10.9 % area for 3.9 % throughput (3.8 % fewer cycles) → hw/docs/hardware_report.md:357
- 68 % → hw/docs/hardware_report.md:350
- 158,441 cycles → hw/docs/hardware_report.md:332
- 1.0686 measured on the DUT → hw/docs/hardware_report.md:322
- TWO items in one → hw/docs/lessons.md:444
- K3 lands ~1.30 → hw/docs/lessons.md:446
- 2-wide write port → hw/mtf_cam/docs/uarch.md:71

## S21 · The chain reproduces the benchmark output byte-exact: 336,184 bytes in 159,303 cycles, with and without back-pressure
- owner: Y
- status: DRAFT
- stage: Accelerate
- seconds: 45
- visual: assets/chain_cosim.gif

notes:
The clip is `make -C hw/pyflate_accel sim`: Verilator builds a logic-free wrapper that wires huffman_engine's output stream straight into mtf_cam's input, the cocotb test programs both modules, doorbells mtf_cam first, streams the real benchmark block and compares the L-vector with the golden model; it runs in ~30 s and ends 2/2 PASS. Both runs are byte-exact over 336,184 bytes: 159,303 cycles with an always-ready sink, 189,448 under 50 % random output back-pressure. That is 0.54 % above the standalone mtf projection; the difference is the decoder's table-build start-up. The link statistics say who sets the pace: the decoder was stalled by mtf_cam on 10,013 cycles while mtf_cam starved on only 873, so the chain runs at mtf's 1.0686 cycles per symbol, not the decoder's 1.0068. One shared clock, no clock-domain crossing; the rate difference is absorbed by tready back-pressure.

sources:
- byte-exact over 336,184 bytes → hw/docs/hardware_report.md:394
- 159,303 cycles → hw/docs/hardware_report.md:395
- 50 % random output → hw/docs/hardware_report.md:394
- 0.54 % above the standalone → hw/docs/hardware_report.md:395
- 10,013 cycles, mtf starved on 873 → hw/docs/hardware_report.md:396-397
- 1.0068 vs 1.0686 → hw/docs/hardware_report.md:387
- 189,448 under → hw/pyflate_accel/README.md:15
- ~30 s → hw/pyflate_accel/README.md:6
- 2/2 PASS → hw/docs/hardware_report.md:393
- doorbells mtf_cam first → hw/pyflate_accel/README.md:9
- logic-free wrapper → hw/pyflate_accel/README.md:2

## S22 · At 37.5 MHz the chain is 28× faster than the Python loop and 1.3× slower than the Rust kernel; end to end it is a 6.6× tie because inverse BWT sets the floor
- owner: Y
- status: DRAFT
- stage: Trade-offs
- seconds: 45
- visual: table

table:
| Stage implementation | Stage time | End-to-end path | End-to-end time | vs original |
|---|---:|---|---:|---:|
| — | — | Original Python | 1,123.49 ms | 1.00× |
| Optimized Python loop | ≈ 117 ms (derived) | Optimized Python | 281.16 ms | 4.00× |
| Rust kernel | 3.30 ms (measured) | Python + Rust kernel | 170.01 ms | 6.61× |
| HW chain @ 37.5 MHz, 159,303 cycles | ≈ 4.25 ms (projected) | Python + HW chain @ 37.5 MHz | ≈ 171 ms | ≈ 6.6× |
| HW chain @ 50 MHz target | ≈ 3.19 ms (projected) | Python + HW chain @ 50 MHz | ≈ 170 ms | ≈ 6.6× |

notes:
Same boundary as the Rust kernel: 148,271 symbols in, 336,184 bytes out. Hardware time is measured chain cycles over the post-CTS clock, 159,303 cycles at 37.5 MHz ≈ 4.25 ms; Rust's 3.30 ms is a phase-isolated VM measurement; the ≈ 117 ms Python loop is derived (283.88 − 170.01 + 3.30). So the chain replaces the interpreter loop ≈ 28× faster but is ≈ 1.3× slower than Rust at the achievable clock, parity at 50 MHz. End to end it lands at ≈ 171 ms, a tie with the delivered 170.01 ms: off the interpreter this stage is ≈ 2 % of what remains, and inverse BWT at 137.7 ms (≈ 80 %) sets the floor for both routes. Not in these rows: DMA and host-interface time T_if is unmeasured and can only add; the per-block bus cost is modelled at ≈ 628 cycles, streams overlapped by DMA.

sources:
- 37.5 MHz (mtf-limited) → hw/docs/hardware_report.md:386
- ≈ 28× over the Python loop, ≈ 1.3× slower than the Rust kernel → hw/docs/hardware_report.md:411
- end to end ≈ 6.6× → hw/docs/hardware_report.md:339
- 1,123.49 ms | 1.00× → hw/docs/hardware_report.md:406
- ≈ 117 ms → hw/docs/hardware_report.md:406
- 281.16 ms | 4.00× → hw/docs/hardware_report.md:407
- 3.30 ms → hw/docs/hardware_report.md:407
- 170.01 ms | 6.61× → hw/docs/hardware_report.md:408
- 159,303 cyc, measured) | ≈ 4.25 ms → hw/docs/hardware_report.md:408
- HW chain @ 50 MHz | ≈ 3.19 ms → hw/docs/hardware_report.md:409
- ≈ 171 / 170 ms → hw/docs/hardware_report.md:409
- 148,271 symbols → 336,184 bytes → hw/docs/hardware_report.md:399
- 283.88 − 170.01 + 3.30 ms → report_pyflate.txt:461
- ≈ 2 % of what remains → hw/docs/hardware_report.md:413
- 137.7 ms, ≈ 80 % → hw/docs/hardware_report.md:413
- not measured → hw/docs/hardware_report.md:473
- ≈ 628 bus cyc/block, DMA overlapped → hw/huffman_engine/docs/integration.md:68

## S23 · All three modules meet their cycle KPIs and miss 50 MHz; huffman_engine's area is 95 % tables in flip-flops, so SRAM would roughly halve it
- owner: Y
- status: DRAFT
- stage: Trade-offs
- seconds: 60
- visual: table

table:
| Metric | grape_pipeline | huffman_engine | mtf_cam |
|---|---:|---:|---:|
| Cells / area, plain Yosys sky130 | 584,454 / 4.075 mm² | 151,058 / 1.634 mm² | 18,814 / 0.187 mm² |
| Cycle KPI, measured vs bound | 124 /step ≤ 128 | 1.0068 /sym ≤ 1.10 | 1.0686 /sym ≤ 1.10 |
| Fmax, post-CTS STA (target 50 MHz) | 19.46 MHz | 39.9 MHz | 37.5 MHz |
| Power, default activity, indicative | ≈ 19.2 mW @ 150 ns | ≈ 283 mW @ 40 ns | ≈ 10.2 mW @ 27 ns |
| Directed + random tests | 9/9 | 17/17 | 16/16 |

notes:
Three modules at one evidence stage: every Fmax is post-CTS static timing from a run that met its constraint. Each module meets its cycle KPI: grape 124 cycles per step against 128, huffman 1.0068 per symbol against 1.10, mtf 1.0686 against 1.10. Each misses the 50 MHz target: 19.46, 39.9 and 37.5 MHz. huffman's 1.634 mm² misses the 1.0 mm² soft ceiling by 1.63×, a storage miss: symbol table and length window are ≈ 34 kbit of flip-flops, 95 % of the area, the decode cascade 1.3 %; SRAM macros project ≈ 0.75 mm² of standard cells, not synthesized in our flow. Power is a tool estimate at default activity on three different clocks: indicative, not comparable. One correction on record: huffman was first published at 25.1 MHz because a script read hold slack as setup; the setup report gives 39.9 MHz.

sources:
- 95 % of area → hw/docs/hardware_report.md:283
- miss 50 MHz post-CTS → hw/docs/hardware_report.md:491
- 584,454 ‡ | 151,058 | 18,814 → hw/docs/hardware_report.md:438
- 4.075 mm² ‡ | 1.634 mm² | 0.187 mm² → hw/docs/hardware_report.md:439
- 124 /step | 1.0068 /sym | 1.0686 /sym → hw/docs/hardware_report.md:442
- ≤ 128 → hw/grape_pipeline/docs/prd.md:30
- ≤ 1.10 → hw/huffman_engine/docs/prd.md:49
- fails K3 ≤ 1.10 → hw/docs/hardware_report.md:355
- 19.46 MHz | 39.9 MHz | 37.5 MHz → hw/docs/hardware_report.md:443
- 19.2 mW @ 150 ns, 283 mW @ 40 ns, 10.2 mW @ 27 ns → hw/docs/hardware_report.md:462-463
- 9/9 | 17/17 | 16/16 → hw/docs/hardware_report.md:446
- 1.0 mm² missed by 1.63× → hw/docs/hardware_report.md:284
- ~34 kbit of flops → hw/docs/hardware_report.md:285
- only 1.3 % → hw/docs/hardware_report.md:284
- ~0.75 mm² → hw/docs/hardware_report.md:286
- 25.1 MHz published, real value 39.9 MHz → hw/docs/lessons.md:587
- read setup slack from `max.rpt` → hw/docs/lessons.md:593

## B04 · huffman_engine's area is storage: 1.634 mm² as built in flip-flops, ≈ 0.75 mm² projected with SRAM macros, and two table sets would save area but break K1
- owner: Y
- status: DRAFT
- stage: Trade-offs
- visual: table
- answers: Q24, Q22

table:
| Design point | Area | K1 cyc/sym | 1.0 mm² soft ceiling | Verdict |
|---|---:|---:|---|---|
| As built: flop symtab + 6 table register sets | 1.634 mm² (measured) | 1.0068 | miss (1.63×) | signed off, 0-cycle switch |
| Symtab 17.3 kbit + length window 8.6 kbit in SRAM macros | ≈ 0.75 mm² std cells + 2 macros (projected) | 1.0068 | meets | not synthesized: no SRAM compiler in the open sky130 HD flow |
| 2 table register sets, re-derive on each switch | ≈ 1.53 mm² (projected) | > 1.1 | miss | rejected: breaks K1 and the 0-cycle switch |

| RTL-review must | Symptom | Fix |
|---|---|---|
| R1 output-skid overflow | three cycles of back-pressure silently drop a symbol beat | issue gate counts the in-flight C1 beat |
| R2 PREP exit misses the build_done pulse | BUSY forever, no error; the real multi-block flow hangs by block 2–3 | build_done became a level |
| R3 symbol 0 issues before the first selector pop | silent bzip2 corruption from a stale table selector | sel_stall holds C0 until the first selector applies |

notes:
The decode datapath is 1.3 % of the design and carries no sequential area; huff_tables plus huff_regs are 95 %. That is the whole area story, so the only real lever is where the tables live. As built they are flip-flops, which is why the 1.0 mm² soft ceiling is missed by 1.63×. Moving the two large single-port arrays into SRAM macros projects ≈ 0.75 mm² of standard cells plus two macros, but no SRAM compiler exists in our open sky130 flow, so it is a projection. Cutting the six table sets to two would save only ≈ 0.1 mm² and re-derive tables at every 50-symbol switch, pushing K1 past 1.1; rejected. The second table is what the agent pre-review found before any simulation: 13 musts in the first RTL pass, the three above being the ones a testbench would have found last, because each needs back-pressure, a second block, or a first-symbol corner. All 13 were fixed and 36/36 unit and smoke tests passed on the fixed RTL.

sources:
- 1.634 mm² → hw/huffman_engine/docs/ppa.md:76
- 1.0068 → hw/huffman_engine/docs/ppa.md:76
- 1.63× → hw/huffman_engine/docs/ppa.md:76
- K5 (≤1.0 mm²) → hw/huffman_engine/docs/ppa.md:74
- Symtab (17.3 kbit) + length window (8.6 kbit) → hw/huffman_engine/docs/ppa.md:77
- 0.75 mm² → hw/huffman_engine/docs/ppa.md:77
- ≈ 1.53 mm² (proj.; −~0.1 mm² → hw/huffman_engine/docs/ppa.md:78
- >1.1 → hw/huffman_engine/docs/ppa.md:78
- 1.3 % → hw/huffman_engine/docs/ppa.md:62
- 95 % of the design → hw/huffman_engine/docs/ppa.md:60
- Output-skid overflow → hw/huffman_engine/docs/review_rtl.md:13
- hangs by block 2–3 → hw/huffman_engine/docs/review_rtl.md:14
- Symbol 0 issues before the first selector pop → hw/huffman_engine/docs/review_rtl.md:15
- 13 must → hw/huffman_engine/docs/review_rtl.md:51
- All 13 musts fixed; 36/36 → hw/huffman_engine/docs/review_rtl.md:57
- issue gate accounts for in-flight C1 → hw/huffman_engine/docs/review_rtl.md:58
- `build_done_o` is a level → hw/huffman_engine/docs/review_rtl.md:59
- sel_stall holds C0 until the first selector applies → hw/huffman_engine/docs/review_rtl.md:60

## B05 · mtf_cam in full: K3 1.0686 measured against a 1.063 model, 0.187 mm² with 5.3× headroom, 37.5 MHz from a run that met 27 ns, and list invariants proven unbounded at 16 entries
- owner: Y
- status: DRAFT
- stage: Trade-offs
- visual: assets/mtf_block_diagram.png
- answers: Q22, Q23

notes:
The block diagram: a 256-entry shift-register list with a 256:1 rank read mux and a registered parallel move, an item FIFO with a 2-wide write port, the RUNA/RUNB run counter, the run expander and the W = 8 lane packer behind an AXI4-Lite register block. Numbers: 158,441 cycles for the benchmark block, K3 = 1.0686 on the DUT against the 1.063 model, the delta being the FIFO's 2-slot reservation; 18,814 cells, 0.187 mm², 5.3× under the 1.0 mm² soft ceiling with the list at 68 %; Fmax 37.5 MHz from a post-CTS run whose 27 ns constraint was met (+0.3066 ns worst setup slack), the 20 ns run having failed by 6.5964 ns; power ≈ 10.2 mW at that operating point, default activity, indicative only. Formal: the three list invariants (permutation preserved, lookup returns the pre-shift byte at rank r, the moved byte lands at rank 0) are proven unbounded by k-induction at N_LIST=16; at the production 256 the general check is bounded to depth 6 and a fill-abstracted run shows 24 consecutive moves preserve the permutation. An unbounded proof at 256 was tried with smtbmc k-induction, ABC PDR and rIC3, all timing out at 900 s: a SAT wall, stated as such.

sources:
- 1.0686 measured on the DUT → hw/docs/hardware_report.md:322
- 1.063 → hw/docs/hardware_report.md:322
- 0.187 mm² / 18,814 cells → hw/docs/hardware_report.md:350
- 68 % → hw/docs/hardware_report.md:350
- 5.3× headroom → hw/docs/hardware_report.md:359
- 1.0 mm² area ceiling → hw/docs/hardware_report.md:359
- 37.5 MHz → hw/docs/hardware_report.md:359
- 158,441 cycles → hw/docs/hardware_report.md:332
- 256-entry move-to-front list → hw/docs/hardware_report.md:302
- +0.3066 ns worst setup slack → hw/docs/hardware_report.md:314
- failed** by 6.5964 ns → hw/docs/hardware_report.md:315
- ≈ 10.2 mW → hw/docs/hardware_report.md:360
- unbounded @ N_LIST=16 → hw/docs/hardware_report.md:483
- depth 6 → hw/docs/hardware_report.md:484
- fill-abstracted → hw/docs/hardware_report.md:485
- 24 consecutive moves preserve the permutation → hw/docs/hardware_report.md:486
- ABC PDR, and rIC3 all TIMEOUT at 900 s → hw/mtf_cam/docs/testplan.md:151
- 2-wide write port → hw/mtf_cam/docs/uarch.md:71
- 2-slot reservation → hw/mtf_cam/docs/review_rtl.md:16

## B08 · The HW/SW interface is one register-map convention over AXI4-Lite, AXI4-Stream for bulk data, and per-module driver models that match their maps with 0 diffs
- owner: Y
- status: DRAFT
- stage: Accelerate
- visual: table
- answers: Q26, Q25, grill "same clock or CDC", grill "T_if unmeasured"

table:
| Offset | Register | Access | Meaning (huffman_engine, MAS §4) |
|---|---|---|---|
| 0x000 | ID | RO | ASCII `HUF1`; same header on every module (ADR-0005) |
| 0x008 | CTRL | write-1 pulse | bit 0 DOORBELL, bit 1 ABORT; ignored with ERR_BUSY while BUSY |
| 0x00C | STATUS | RO / W1C | BUSY live; sticky DONE, ABORTED, ERR_* |
| 0x040 | CYCLES_LO | RO | accepted doorbell → DONE, low word of a 64-bit counter |
| 0x104 | START_BIT | RW | first code bit inside the s_bits buffer |
| 0x400 + 4·w | LEN[w] | RW | length window, 288 words of six 5-bit fields |

notes:
Every module owns a 4 KB AXI4-Lite window with the same header (ID, VERSION, CTRL, STATUS, IRQ_EN, counters at 0x040, module registers from 0x100), so three Python drivers share one base class and one testbench register agent (ADR-0005). Bulk data never goes through registers: huffman takes the compressed bytes and selectors as AXI4-Stream, hands symbols to mtf_cam as 32-bit beats, and mtf_cam's 64-bit L-vector stream goes to platform DMA (ADR-0001). Each driver's offsets and fields are generated from its MAS §4 and check_regmap.py reports 0 diffs for all three. How far each driver was exercised, honestly: grape's is co-simulated against the RTL through the AXI-Lite agent, reading back all 35 state components bit-identical with CYCLES = 250; mtf's passes 16/16 in RTL co-simulation; huffman's is checked against the signed-off cycle model, not the RTL. Per block the huffman configuration is ≈ 157 AXI-Lite transactions, ≈ 628 cycles, with the streams overlapped by DMA; the DMA sink is assumed to sustain W = 8 bytes per cycle, ≈ 300 MB/s at 37.5 MHz. What remains unmeasured is T_if: configuration, DMA setup and the copies of the input and the 336,184 L-vector bytes. No software calls the hardware yet.

sources:
- 0x000 | ID | 31:0 | RO | 0x48554631 | ASCII `HUF1` → hw/huffman_engine/docs/mas.md:56
- 0x008 | CTRL → hw/huffman_engine/docs/mas.md:58
- 0x00C | STATUS → hw/huffman_engine/docs/mas.md:60
- 0x040 | CYCLES_LO → hw/huffman_engine/docs/mas.md:74
- 0x104 | START_BIT → hw/huffman_engine/docs/mas.md:82
- 0x400 + 4·w | LEN[w] → hw/huffman_engine/docs/mas.md:89
- 6 × 288 × 5-bit length window → hw/docs/hardware_report.md:290
- 4 KB AXI-Lite window with the same header → hw/docs/adr/0005-register-map-conventions.md:6
- 0x040.. | counters → hw/docs/adr/0005-register-map-conventions.md:17
- 32-bit AXI4-Lite slave → hw/docs/adr/0001-bus-family.md:8
- 64-bit (8·W, W = 8) AXI4-Stream out → hw/docs/hardware_report.md:310
- `driver/check_regmap.py` → hw/huffman_engine/docs/integration.md:17
- register-map consistency (0 diffs) → hw/huffman_engine/docs/integration.md:33
- register-map consistency (0 diffs) → hw/mtf_cam/docs/integration.md:40
- 0 differences → hw/docs/hardware_report.md:157
- 35 state components bit-identical to the golden model, CYCLES = 250 → hw/docs/hardware_report.md:162-163
- RTL-cosim 16/16 pass → hw/docs/hardware_report.md:327
- RTL-cosim extension → hw/huffman_engine/docs/integration.md:31
- ≈ 157 AXI-Lite → hw/huffman_engine/docs/integration.md:13
- ≈ 628 cycles → hw/huffman_engine/docs/integration.md:14
- ≈ 300 MB/s at 37.5 MHz → hw/mtf_cam/docs/integration.md:116
- W = 8 → hw/mtf_cam/docs/integration.md:115
- 336,184 L-vector bytes → report_pyflate.txt:448
- not measured → hw/docs/hardware_report.md:473

## B09 · Cross-module PPA in full: cells and area by flow, post-CTS Fmax, indicative power, tests and coverage, all at the same evidence stage
- owner: Y
- status: DRAFT
- stage: Trade-offs
- visual: table
- answers: Q23, Q24, Q21, grill "why do all three miss 50 MHz"

table:
| Metric | grape_pipeline | huffman_engine | mtf_cam |
|---|---:|---:|---:|
| Cells, plain Yosys (sky130 HD) | 584,454 ‡ | 151,058 | 18,814 |
| Area, plain Yosys | 4.075 mm² ‡ | 1.634 mm² | 0.187 mm² |
| Cells / area, OpenLane synthesis of the final RTL | 446,932 / 4.66 mm² (5.65 mm² placed) | not rerun | not rerun |
| Fmax, post-CTS STA (target 50 MHz) | 19.46 MHz | 39.9 MHz | 37.5 MHz |
| Power, default activity, indicative | ≈ 19.2 mW @ 150 ns | ≈ 283 mW @ 40 ns | ≈ 10.2 mW @ 27 ns |
| Cycle KPI | 124 /step | 1.0068 /sym | 1.0686 /sym |

| Verification | grape_pipeline | huffman_engine | mtf_cam |
|---|---:|---:|---:|
| Directed + random tests | 9/9 | 17/17 | 16/16 |
| Line / toggle coverage | 91.7 % / 96.0 % | 90.4 % / 90.3 % † | 92.0 % / 93.8 % † |
| Branch coverage | 94.8 % | 91.7 % | 96.8 % |
| Functional bins, all hit | 59 | 34 | 129 |
| End-to-end estimate | ≈ 1.66× at 19.46 MHz | ≈ 6.6× as a chain; stage ≈ 28× vs the Python loop | same chain figure |

notes:
Two footnotes carry the honesty. ‡ grape's plain-Yosys figures predate the final issue-selection rewrite; the OpenLane row is the netlist the 19.46 MHz timing was measured on, and the two recipes are not comparable with each other, so the plain-Yosys row is the one comparable across the three modules. † huffman and mtf toggle coverage is measured over the control-signal subset (signals ≤ 4 bits wide), with the wide data buses waived by a documented width sweep; grape's is over all signals. All three Fmax values are post-CTS static timing, the same stage, so they are comparable on that axis; none completed routed GDS, so there is no die shot. Power uses default switching activity at each run's own constraint, so the three numbers are not comparable with each other and support no energy claim. Every module misses 50 MHz post-CTS (grape 2.6×, mtf 1.33×, huffman 1.25×); the documented follow-ups, pipelining the integrate-multiply path and the table build, are datapath changes deferred beyond the PPA stage.

sources:
- 584,454 ‡ | 151,058 | 18,814 → hw/docs/hardware_report.md:438
- 4.075 mm² ‡ | 1.634 mm² | 0.187 mm² → hw/docs/hardware_report.md:439
- 446,932 → hw/docs/hardware_report.md:440
- 4.66 mm² (5.65 mm² placed) → hw/docs/hardware_report.md:441
- 124 /step | 1.0068 /sym | 1.0686 /sym → hw/docs/hardware_report.md:442
- 19.46 MHz | 39.9 MHz | 37.5 MHz → hw/docs/hardware_report.md:443
- 19.2 mW @ 150 ns, 283 mW @ 40 ns, 10.2 mW @ 27 ns → hw/docs/hardware_report.md:462-463
- 9/9 | 17/17 | 16/16 → hw/docs/hardware_report.md:446
- 91.7 % / 96.0 % | 90.4 % / 90.3 %† | 92.0 % / 93.8 %† → hw/docs/hardware_report.md:447
- ≈ 1.66× (19.46 MHz) → hw/docs/hardware_report.md:448
- ≈ 6.6× vs the original as a chain → hw/docs/hardware_report.md:448
- ≈ 28× vs the optimized Python loop → hw/docs/hardware_report.md:448
- 94.8 % / 91.7 % / 96.8 % → hw/docs/hardware_report.md:457
- 59 / 34 / 129 functional bins → hw/docs/hardware_report.md:458
- control-signal subset** (signals ≤ 4 bits → hw/docs/hardware_report.md:454-455
- miss 50 MHz post-CTS (grape 2.6×, mtf 1.33×, huffman 1.25×) → hw/docs/hardware_report.md:491
- pipeline the integrate-multiply path; pipeline the table build → hw/docs/hardware_report.md:492
- None completed routed GDS sign-off (no die shot) → hw/docs/hardware_report.md:461
