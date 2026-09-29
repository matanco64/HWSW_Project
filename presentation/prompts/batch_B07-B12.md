# Batch B07–B12: build 6 slides autonomously, then export

Work through the slides below in order without stopping between them. For each slide follow its
block exactly as if it were a single prompt. Do not take a screenshot per slide; instead, at the
end, (1) run the readback export (File → Download → .pptx, then .txt; leave them in Downloads),
(2) take ONE screenshot of the slide-sorter/grid view (View → Grid view) showing all slides, and
(3) reply with one STATUS block per slide, in order, followed by the STATUS RB block.

Rules that apply to every slide in this batch:
- Layout by name ("Title and body · <stage>"); never edit the footer tracker.
- Images: insert the named file from `C:\Users\Kogan\HWSW_presentation\assets` with your direct upload tool, size to
  width 9.2 in (or height 3.4 in if that binds first), place at x = 0.4 in, y = 1.6 in, centred.
  Delete the layout's empty body placeholder afterwards.
- Tables: header row bold, fill #1F4E79, white text; body 16 pt Roboto (set it, the default is
  Arial); no other formatting. Table at x = 0.4 in, y = 1.6 in, width 9.2 in. Set column widths
  yourself: no header word may break mid-word, and the column with the longest text gets the most
  width. If the table does not fit above y = 5.0 in at 16 pt, use 14 pt, then 12 pt, then reduce
  cell padding; say which under deviations. Never drop, merge or reword cells.
- Titles and notes exactly as written. If a title needs three lines, keep it and report it under
  deviations with the slide id; do not shorten it.
- If a slide cannot be completed, leave it as far as you got, write `result: blocked` in its
  STATUS block, and continue with the next slide.

---

# Slide B07 (BACKUP)

Layout: "Title and body · Trade-offs" (Slide → Apply layout). Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    Speedup at two altitudes agrees: 25x on a 13.4% slice is 1.148x; two profilers give f = 0.496 vs 0.40

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Question | Numbers | Reading |
|---|---|---|
| mtf stage alone vs whole benchmark | 80.4 ms / 3.169 ms = 25.4x at 50 MHz; 1/((1−0.1344)+0.1344/25) = 1.148x | same result at two altitudes |
| huffman f from cProfile (PRD) | f = 0.496 → 1/(1−0.496) = 1.98x | per-call overhead inflates tiny bit-reader calls |
| huffman f from VM py-spy (report) | f = 0.40 → 1/(1−0.40) = 1.67x | sampled; the one the reports use |
| mtf standalone ceiling | f = 0.1344 → 1.16x | why it is chained, not standalone |
| Chain, measured at the Rust boundary | ≈ 28x over the Python loop, ≈ 1.3x slower than Rust, ≈ 6.6x end to end | the figure the reports quote |

Do not touch the footer tracker: the layout already highlights "Trade-offs".

Speaker notes (exact text, paste into the notes pane):

    Two questions the reviewers asked. First, how can a stage be 25x faster while the benchmark barely moves? Because the move-to-front stage is 13.44% of the original run: a 25x stage speedup on that slice gives 1.148x by Amdahl, and both numbers describe the same result, one at stage altitude and one at benchmark altitude. Second, why did the huffman fraction change? The PRD sized the module from a local cProfile run, f = 0.496, a 1.98x ceiling; cProfile's per-call overhead inflates the many tiny bit-reader calls. The sampled py-spy profile on the course VM gives 0.40 and a 1.67x ceiling, and that is the denominator the reports use. Neither standalone figure is a report claim; the reports quote the chain measured at the Rust boundary.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Trade-offs" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for B07 (expected: position end of deck, body table 6x3,
notes_set yes, tracker Trade-offs via layout).

---

# Slide B08 (BACKUP)

Layout: "Title and body · Accelerate" (Slide → Apply layout). Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    The HW/SW interface is one register-map convention over AXI4-Lite, AXI4-Stream for bulk data, and per-module driver models that match their maps with 0 diffs

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Offset | Register | Access | Meaning (huffman_engine, MAS §4) |
|---|---|---|---|
| 0x000 | ID | RO | ASCII `HUF1`; same header on every module (ADR-0005) |
| 0x008 | CTRL | write-1 pulse | bit 0 DOORBELL, bit 1 ABORT; ignored with ERR_BUSY while BUSY |
| 0x00C | STATUS | RO / W1C | BUSY live; sticky DONE, ABORTED, ERR_* |
| 0x040 | CYCLES_LO | RO | accepted doorbell → DONE, low word of a 64-bit counter |
| 0x104 | START_BIT | RW | first code bit inside the s_bits buffer |
| 0x400 + 4·w | LEN[w] | RW | length window, 288 words of six 5-bit fields |

Do not touch the footer tracker: the layout already highlights "Accelerate".

Speaker notes (exact text, paste into the notes pane):

    Every module owns a 4 KB AXI4-Lite window with the same header (ID, VERSION, CTRL, STATUS, IRQ_EN, counters at 0x040, module registers from 0x100), so three Python drivers share one base class and one testbench register agent (ADR-0005). Bulk data never goes through registers: huffman takes the compressed bytes and selectors as AXI4-Stream, hands symbols to mtf_cam as 32-bit beats, and mtf_cam's 64-bit L-vector stream goes to platform DMA (ADR-0001). Each driver's offsets and fields are generated from its MAS §4 and check_regmap.py reports 0 diffs for all three. How far each driver was exercised, honestly: grape's is co-simulated against the RTL through the AXI-Lite agent, reading back all 35 state components bit-identical with CYCLES = 250; mtf's passes 16/16 in RTL co-simulation; huffman's is checked against the signed-off cycle model, not the RTL. Per block the huffman configuration is ≈ 157 AXI-Lite transactions, ≈ 628 cycles, with the streams overlapped by DMA; the DMA sink is assumed to sustain W = 8 bytes per cycle, ≈ 300 MB/s at 37.5 MHz. What remains unmeasured is T_if: configuration, DMA setup and the copies of the input and the 336,184 L-vector bytes. No software calls the hardware yet.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Accelerate" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for B08 (expected: position end of deck, body table 7x4,
notes_set yes, tracker Accelerate via layout).

---

# Slide B09 (BACKUP)

Layout: "Title and body · Trade-offs" (Slide → Apply layout). Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    Cross-module PPA in full: cells and area by flow, post-CTS Fmax, indicative power, tests and coverage, all at the same evidence stage

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

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

Do not touch the footer tracker: the layout already highlights "Trade-offs".

Speaker notes (exact text, paste into the notes pane):

    Two footnotes carry the honesty. ‡ grape's plain-Yosys figures predate the final issue-selection rewrite; the OpenLane row is the netlist the 19.46 MHz timing was measured on, and the two recipes are not comparable with each other, so the plain-Yosys row is the one comparable across the three modules. † huffman and mtf toggle coverage is measured over the control-signal subset (signals ≤ 4 bits wide), with the wide data buses waived by a documented width sweep; grape's is over all signals. All three Fmax values are post-CTS static timing, the same stage, so they are comparable on that axis; none completed routed GDS, so there is no die shot. Power uses default switching activity at each run's own constraint, so the three numbers are not comparable with each other and support no energy claim. Every module misses 50 MHz post-CTS (grape 2.6×, mtf 1.33×, huffman 1.25×); the documented follow-ups, pipelining the integrate-multiply path and the table build, are datapath changes deferred beyond the PPA stage.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Trade-offs" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for B09 (expected: position end of deck, body table 13x4,
notes_set yes, tracker Trade-offs via layout).

---

# Slide B10 (BACKUP)

Layout: "Title and body · Trade-offs" (Slide → Apply layout). Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    How we used AI: a stage-gated flow, prompt.txt as the log, and the decisions humans made

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Decision | Options came from | Decided by | Where recorded |
|---|---|---|---|
| FP64 in the benchmark's order, no FMA | agent research + uArch review finding R1 | Yuval, ADR-0002 / ADR-0007, uArch checkpoint | hw/docs/adr, review_uarch.md |
| 3 add + 3 mul unit mix | agent schedule-model sweep | Yuval at the uArch checkpoint | uarch.md §7 |
| Boundary: whole advance() on-chip, MMIO only | PRD grilling interview | Yuval at the PRD and MAS checkpoints | prd.md §4, ADR-0001 |
| Keep K1 ≤ 128 rather than renegotiate to 162 | agent offered both at sign-off | Yuval at the DV sign-off checkpoint | ppa.md |
| Accept the 50 MHz miss and report 19.46 MHz with caveats | PPA stage | Yuval | ppa.md §7 framing |
| Retire the MDP benchmark | scope review | Matan | CLOSEOUT.md |

Do not touch the footer tracker: the layout already highlights "Trade-offs".

Speaker notes (exact text, paste into the notes pane):

    The agent, Claude Code, drafted RTL, testbenches, flow documents and report text; every prompt is in prompt.txt, hand-written at first and auto-logged by a hook afterwards, 220 dated entries over the project. What kept it honest was the flow: ten stages with gates, four of them human checkpoints, and an agent pre-review before each checkpoint whose findings table the human read before approving. Yuval directed the hardware flow and reviewed each gate; Matan designed and measured the software ladder and ran the course-VM measurements. The table lists the decisions a grader may ask about and who made them. The pattern is the same each time: the agent produced options and evidence, the human chose, and the choice is written in an ADR, a checkpoint approval or a close-out record.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Trade-offs" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for B10 (expected: position end of deck, body table 7x4,
notes_set yes, tracker Trade-offs via layout).

---

# Slide B11 (BACKUP)

Layout: "Title and body · Optimize" (Slide → Apply layout). Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    Every headline is 120 pyperf values on the course VM, and the ± is spread, not a confidence interval

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Item | What it is | Value |
|---|---|---|
| Route A: pyperformance run, rigorous | original vs optimized, same benchmark name | 231.20 → 143.13 ms; 1,123.49 → 281.16 ms |
| Route B: direct pyperf | Python back end vs Rust of the same file, HWSW_BACKEND the only change | 145.30 → 9.530 ms; 283.88 → 170.01 ms |
| Values per JSON | 40 worker processes, three values each | 120 values, pinned to guest CPU 0 |
| ± in every table | sample standard deviation, not a confidence interval | effective n 40.2 and 41.8 for nbody original and optimized |
| Timed revision | 2c8c754, the canonical run | later commits pass the same oracles but were not re-timed |
| Hash names under results/ | pre-rewrite ids, kept as the historical record | 2c8c754 is 69b6bd5 after the rewrite |

Do not touch the footer tracker: the layout already highlights "Optimize".

Speaker notes (exact text, paste into the notes pane):

    Every headline came from the course VM, Ubuntu 22.04, release CPython, pyperf in rigorous mode, every timed run pinned to guest CPU 0, from one canonical run of revision 2c8c754. Two routes. Original versus optimized goes through pyperformance, which builds its own environment and therefore cannot see our wheel; Python back end versus Rust runs the same benchmark file directly under pyperf with only HWSW_BACKEND changed, and native mode fails rather than falls back. Each JSON holds 120 values, 40 worker processes times three values, and the ± is the sample standard deviation across them, not a confidence interval. Values from one worker are correlated: the intraclass correlation is 0.994 for the nbody original, so the effective sample size is about 40.2 and 41.8 for nbody's original and optimized runs. The reductions are still tens of standard errors. Commits after the timed revision were not re-timed: nbody removed a dead store from the generated advance() and widened the optional-import fallback; pyflate trimmed comments, moved the BWT histogram to collections.Counter and lowered the Rust code-length cap from 23 to 20. All pass the same exactness oracles, and results/vm_verify_20260921_f407567 re-ran the correctness checks on the VM at the submitted revision. Directory names under results/ keep the pre-rewrite commit ids: 2c8c754 is 69b6bd5 after the history rewrite, and the mapping is in docs/history-rewrite.md.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Optimize" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for B11 (expected: position end of deck, body table 7x3,
notes_set yes, tracker Optimize via layout).

---

# Slide B12 (BACKUP)

Layout: "Title and body · Trade-offs" (Slide → Apply layout). Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    Barnes-Hut crosses over near N = 300, far above the benchmark's N = 5; grape's cost per pair falls with the pair count

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| N | Direct | Barnes-Hut | BH / direct |
|---|---|---|---|
| 5 | 0.020 ms | 0.077 ms | 3.92x |
| 100 | 4.746 ms | 8.410 ms | 1.77x |
| 300 | 42.977 ms | 42.489 ms | 0.99x |
| 800 | 313.489 ms | 158.846 ms | 0.51x |
| 1,600 | 1,254.660 ms | 382.471 ms | 0.30x |

Do not touch the footer tracker: the layout already highlights "Trade-offs".

Speaker notes (exact text, paste into the notes pane):

    Section 5 of the nbody report extends the workload beyond the required N = 5. It is a pure-Python force-evaluation sweep on the VM with the Barnes-Hut tree rebuilt at each evaluation, θ = 0.5, best of seven; it is not the full integration benchmark. At five bodies the tree costs 3.92x more than direct summation; the crossover is near N = 300 for this distribution of near-coplanar circular orbits, and the median acceleration error is not a worst-case or trajectory bound. Native Rust stays 21–22x over rolled Python from N = 100 to 3,200. The specialized generator grows as O(N²) in source size and falls back to the rolled pair loop above 20,000 pairs. On the hardware side, grape is latency-bound at N = 5: 12.3 cycles per pair in the model, 12.4 measured, falling to about 4.4 cycles per pair at N = 100 as the pipelined units fill; but above N ≈ 300 the software competitor becomes Barnes-Hut rather than direct summation, so the comparison has to change too.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Trade-offs" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for B12 (expected: position end of deck, body table 6x4,
notes_set yes, tracker Trade-offs via layout).

---

# Readback: export the deck as plain text

Run this whenever a prompt or the human asks for a readback (normally after every batch of five
slides, and after each setup prompt if asked).

1. In the deck: File → Download → Microsoft PowerPoint (.pptx).
2. Then File → Download → Plain Text (.txt). Both land in the Windows Downloads folder; if
   Chrome asks, answer Keep. Do not try to drive the Save dialog; leave them in Downloads, a sync
   script on the WSL side collects the newest export.
3. Reply with this block only:

    STATUS RB
    result: done | blocked
    deck_url: <URL>
    slide_url: n/a
    position: <total slides now in the deck> of <same>
    title_as_typed: n/a
    body: n/a
    notes_set: n/a
    tracker: n/a
    gemini_used: no
    deviations: the two file names as saved in Downloads | <anything unusual>
    screenshot: not taken: readback only

Do not edit the export and do not edit any slide during a readback.
