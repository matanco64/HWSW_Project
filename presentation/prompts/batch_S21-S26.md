# Batch S21–S26: build 6 slides autonomously, then export

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

# Slide S21 (22 of 27)

Layout: "Title and body · Accelerate" (Slide → Apply layout). Insert after slide S20.

Title (exact text, do not shorten or rephrase):

    The chain reproduces the benchmark output byte-exact: 336,184 bytes in 159,303 cycles, with and without back-pressure

Body: insert the image `C:\Users\Kogan\HWSW_presentation\assets\chain_cosim.gif` with your direct upload tool.
Size it to fill the body box: width 9.2 in, or height 3.4 in if that binds first, keeping the
aspect ratio; place it at x = 0.4 in, y = 1.6 in and centre it horizontally in the body box.
It must not overlap the title or the footer tracker. No caption, no border, no crop.

Do not touch the footer tracker: the layout already highlights "Accelerate".

Speaker notes (exact text, paste into the notes pane):

    The clip is `make -C hw/pyflate_accel sim`: Verilator builds a logic-free wrapper that wires huffman_engine's output stream straight into mtf_cam's input, the cocotb test programs both modules, doorbells mtf_cam first, streams the real benchmark block and compares the L-vector with the golden model; it runs in ~30 s and ends 2/2 PASS. Both runs are byte-exact over 336,184 bytes: 159,303 cycles with an always-ready sink, 189,448 under 50 % random output back-pressure. That is 0.54 % above the standalone mtf projection; the difference is the decoder's table-build start-up. The link statistics say who sets the pace: the decoder was stalled by mtf_cam on 10,013 cycles while mtf_cam starved on only 873, so the chain runs at mtf's 1.0686 cycles per symbol, not the decoder's 1.0068. One shared clock, no clock-domain crossing; the rate difference is absorbed by tready back-pressure.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Accelerate" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S21 (expected: position 22, body image chain_cosim.gif,
notes_set yes, tracker Accelerate via layout).

---

# Slide S22 (23 of 27)

Layout: "Title and body · Trade-offs" (Slide → Apply layout). Insert after slide S21.

Title (exact text, do not shorten or rephrase):

    At 37.5 MHz the chain is 28× faster than the Python loop and 1.3× slower than the Rust kernel; end to end it is a 6.6× tie because inverse BWT sets the floor

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Stage implementation | Stage time | End-to-end path | End-to-end time | vs original |
|---|---:|---|---:|---:|
| — | — | Original Python | 1,123.49 ms | 1.00× |
| Optimized Python loop | ≈ 117 ms (derived) | Optimized Python | 281.16 ms | 4.00× |
| Rust kernel | 3.30 ms (measured) | Python + Rust kernel | 170.01 ms | 6.61× |
| HW chain @ 37.5 MHz, 159,303 cycles | ≈ 4.25 ms (projected) | Python + HW chain @ 37.5 MHz | ≈ 171 ms | ≈ 6.6× |
| HW chain @ 50 MHz target | ≈ 3.19 ms (projected) | Python + HW chain @ 50 MHz | ≈ 170 ms | ≈ 6.6× |

Do not touch the footer tracker: the layout already highlights "Trade-offs".

Speaker notes (exact text, paste into the notes pane):

    Same boundary as the Rust kernel: 148,271 symbols in, 336,184 bytes out. Hardware time is measured chain cycles over the post-CTS clock, 159,303 cycles at 37.5 MHz ≈ 4.25 ms; Rust's 3.30 ms is a phase-isolated VM measurement; the ≈ 117 ms Python loop is derived (283.88 − 170.01 + 3.30). So the chain replaces the interpreter loop ≈ 28× faster but is ≈ 1.3× slower than Rust at the achievable clock, parity at 50 MHz. End to end it lands at ≈ 171 ms, a tie with the delivered 170.01 ms: off the interpreter this stage is ≈ 2 % of what remains, and inverse BWT at 137.7 ms (≈ 80 %) sets the floor for both routes. Not in these rows: DMA and host-interface time T_if is unmeasured and can only add; the per-block bus cost is modelled at ≈ 628 cycles, streams overlapped by DMA.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Trade-offs" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S22 (expected: position 23, body table 6x5,
notes_set yes, tracker Trade-offs via layout).

---

# Slide S23 (24 of 27)

Layout: "Title and body · Trade-offs" (Slide → Apply layout). Insert after slide S22.

Title (exact text, do not shorten or rephrase):

    All three modules meet their cycle KPIs and miss 50 MHz; huffman_engine's area is 95 % tables in flip-flops, so SRAM would roughly halve it

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Metric | grape_pipeline | huffman_engine | mtf_cam |
|---|---:|---:|---:|
| Cells / area, plain Yosys sky130 | 584,454 / 4.075 mm² | 151,058 / 1.634 mm² | 18,814 / 0.187 mm² |
| Cycle KPI, measured vs bound | 124 /step ≤ 128 | 1.0068 /sym ≤ 1.10 | 1.0686 /sym ≤ 1.10 |
| Fmax, post-CTS STA (target 50 MHz) | 19.46 MHz | 39.9 MHz | 37.5 MHz |
| Power, default activity, indicative | ≈ 19.2 mW @ 150 ns | ≈ 283 mW @ 40 ns | ≈ 10.2 mW @ 27 ns |
| Directed + random tests | 9/9 | 17/17 | 16/16 |

Do not touch the footer tracker: the layout already highlights "Trade-offs".

Speaker notes (exact text, paste into the notes pane):

    Three modules at one evidence stage: every Fmax is post-CTS static timing from a run that met its constraint. Each module meets its cycle KPI: grape 124 cycles per step against 128, huffman 1.0068 per symbol against 1.10, mtf 1.0686 against 1.10. Each misses the 50 MHz target: 19.46, 39.9 and 37.5 MHz. huffman's 1.634 mm² misses the 1.0 mm² soft ceiling by 1.63×, a storage miss: symbol table and length window are ≈ 34 kbit of flip-flops, 95 % of the area, the decode cascade 1.3 %; SRAM macros project ≈ 0.75 mm² of standard cells, not synthesized in our flow. Power is a tool estimate at default activity on three different clocks: indicative, not comparable. One correction on record: huffman was first published at 25.1 MHz because a script read hold slack as setup; the setup report gives 39.9 MHz.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Trade-offs" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S23 (expected: position 24, body table 6x4,
notes_set yes, tracker Trade-offs via layout).

---

# Slide S24 (25 of 27)

Layout: "Title and body · Trade-offs" (Slide → Apply layout). Insert after slide S23.

Title (exact text, do not shorten or rephrase):

    We ran a ten-stage flow with four human checkpoints: agents pre-reviewed, humans decided

Body: insert the image `C:\Users\Kogan\HWSW_presentation\assets\hw_flow.png` with your direct upload tool.
Size it to fill the body box: width 9.2 in, or height 3.4 in if that binds first, keeping the
aspect ratio; place it at x = 0.4 in, y = 1.6 in and centre it horizontally in the body box.
It must not overlap the title or the footer tracker. No caption, no border, no crop.

Do not touch the footer tracker: the layout already highlights "Trade-offs".

Speaker notes (exact text, paste into the notes pane):

    The picture is the flow every module went through: PRD, architecture spec, micro-architecture, RTL, then verification in four stages, PPA and integration, ten stages in all. Each stage has an exit gate with recorded evidence; across three modules that is 136 gate criteria in the status file. Four of the gates are human checkpoints: PRD, MAS, uArch and DV sign-off. Before each checkpoint an agent pre-reviewed the artifact and wrote a findings table; counting the rows of those tables gives about 350 findings, 126 of them rated must, all resolved before the gate closed. The division of labour was fixed: agents draft and pre-review, the human reads the findings and approves or sends it back. The K1 decision on the previous slides is one such checkpoint.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Trade-offs" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S24 (expected: position 25, body image hw_flow.png,
notes_set yes, tracker Trade-offs via layout).

---

# Slide S25 (26 of 27)

Layout: "Title and body · Trade-offs" (Slide → Apply layout). Insert after slide S24.

Title (exact text, do not shorten or rephrase):

    What the evidence does and does not say: post-CTS timing, one extrapolated clock, unmeasured interface time, un-re-timed commits

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Claim on these slides | What the evidence is | What it is not |
|---|---|---|
| Fmax of all three modules | post-CTS static timing, placed clock tree | routed GDS or silicon |
| grape 19.46 MHz | 2.9x extrapolation from a met 150 ns run | a confirmation run near 51 ns |
| End-to-end speedups | RTL cycles / STA clock + a 5% residual assumption | a measured interface or DMA time |
| grape 4.075 mm², ≈ 19.2 mW | Yosys area before the final rewrite; default-activity power | comparable with the OpenLane area or across modules |
| Software timings | one canonical VM run of one revision | re-timed after the last commits |
| Native bit-identity | checked on the tested configurations | a guarantee for other builds |

Do not touch the footer tracker: the layout already highlights "Trade-offs".

Speaker notes (exact text, paste into the notes pane):

    Every hardware frequency here is a post-CTS static-timing estimate: cells and clock tree placed, signal wires not routed, no silicon. grape's 19.46 MHz is the weakest number in the deck, back-computed from a run constrained at 150 ns, a 2.9x extrapolation with no confirmation run. Every end-to-end speedup is a projection: measured RTL cycles over that clock, plus a 5% Python residual we assumed rather than measured, and no interface or DMA time at all. The grape area predates the final picker rewrite; the OpenLane area of the final RTL uses a different recipe. Power figures use default switching activity at three different clocks, so they are indicative and not comparable. On the software side, later commits pass the exactness oracle but were not re-timed.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Trade-offs" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S25 (expected: position 26, body table 7x3,
notes_set yes, tracker Trade-offs via layout).

---

# Slide S26 (27 of 27)

Layout: "Title and body · Trade-offs" (Slide → Apply layout). Insert after slide S25.

Title (exact text, do not shorten or rephrase):

    What we learned: measure the KPI on the full-shape workload early, and the next experiment is a native inverse BWT and a timing confirmation run

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Lesson or next step | Where it came from |
|---|---|
| Lesson: measure the KPI on the full-shape workload at bring-up | grape read 162 cycles per step at sign-off; the fix landed at 124 |
| Lesson: removing the interpreter and building a fast datapath are different problems | software took almost all of nbody's gain; the accelerator ties optimized Python |
| Lesson: the platform you report on decides the ranking | the pyflate ablation ordered its three changes one way on the dev machine, the other on the VM |
| Next: a native inverse BWT with an isolated timer and a working-set sweep | 137.7 ms is the floor for both the Rust and the hardware route |
| Next: matched phase timing and a routed timing run | the residuals are assumptions; the clocks are post-CTS estimates |

Do not touch the footer tracker: the layout already highlights "Trade-offs".

Speaker notes (exact text, paste into the notes pane):

    Three things we would tell ourselves at the start. First, measure the KPI on the full-shape workload at bring-up: grape read 162 cycles per step at sign-off after every earlier gate was green, because the smoke test used two pairs; the fix landed at 124. Second, removing interpreter overhead and building a fast physical datapath are different problems: software captured almost all of nbody's gain, and the accelerator ties optimized Python. Third, the platform you report on decides the ranking: the pyflate ablation ordered its three changes differently on the development machine and on the VM. Two next experiments: a native inverse BWT with an isolated timer and a working-set sweep, because its 137.7 ms is the floor for both routes; and matched phase timing plus a routed timing run, replacing assumed residuals, post-CTS clocks and the unmeasured interface time.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Trade-offs" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S26 (expected: position 27, body table 6x2,
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
