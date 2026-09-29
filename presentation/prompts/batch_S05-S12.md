# Batch S05–S12: build 8 slides autonomously, then export

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

# Slide S05 (6 of 27)

Layout: "Title and body · Optimize" (Slide → Apply layout). Insert after slide S04.

Title (exact text, do not shorten or rephrase):

    Struct-of-arrays and NumPy lose at N = 5; only leaving Python wins: the Rust tier runs in 9.530 ms

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Variant | Result | Against | Where |
|---|---|---|---|
| Struct-of-arrays | 0.88x | original | dev host |
| NumPy | 0.35–0.46x | original | dev host |
| Barnes-Hut, N = 5 | 3.92x slower | direct sum | VM |
| Rust, 9.530 ms | 15.25x | optimized Python, 145.30 ms | VM |
| Rust, 9.530 ms | 24.26x | original, 231.20 ms | VM |

Do not touch the footer tracker: the layout already highlights "Optimize".

Speaker notes (exact text, paste into the notes pane):

    Before leaving Python we tried the obvious alternatives, and at ten pairs they lose. A struct-of-arrays layout runs at 0.88x of the original's speed and NumPy at 0.35–0.46x: array setup and per-call overhead exceed the work. Barnes-Hut is 3.92x slower at N = 5 in the VM force sweep, 0.077 against 0.020 ms; it only crosses over near N = 300, which is a backup slide. What wins is leaving the interpreter. The Rust/PyO3 System runs all 20,000 steps and both energy evaluations in one call, 9.530 ± 0.050 ms, bit-identical in state and energy at 5, 10 and 31 bodies. Watch the denominators: 15.25x is against the same file's Python back end under direct pyperf, 145.30 ms; against the pyperformance original of 231.20 ms it is 24.26x. The two ratios must not be multiplied.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Optimize" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S05 (expected: position 6, body table 6x4,
notes_set yes, tracker Optimize via layout).

---

# Slide S06 (7 of 27)

Layout: "Title and body · Optimize" (Slide → Apply layout). Insert after slide S05.

Title (exact text, do not shorten or rephrase):

    Native runs 26.7x fewer instructions while IPC drops from 3.28 to 1.83: the win is instruction count, not the pipeline

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Per iteration | Optimized Python | Native Rust | Ratio |
|---|---|---|---|
| Elapsed time | 141.08 ms | 9.462 ms | |
| Instructions | 1,103.62 M | 41.32 M | 26.7x fewer |
| Cycles | 336.24 M | 22.55 M | 14.9x fewer |
| IPC | 3.28 | 1.83 | lower |
| Branches | 185.97 M | 3.92 M | |

Do not touch the footer tracker: the layout already highlights "Optimize".

Speaker notes (exact text, paste into the notes pane):

    This is a separate pinned warm-loop experiment, 64 iterations per run, medians of three runs, user-mode counters only. Native retires 26.7x fewer instructions and 14.9x fewer cycles, yet its IPC falls from 3.28 to 1.83. That is not a contradiction: runtime is cycles over clock, and IPC counts retired instructions, not useful force updates. Interpreter bookkeeping pipelines beautifully and is still work. Cache misses are 59.6 against 2.5 per iteration, far too few to matter. So nbody's cost was instruction count from the interpreter, not the memory system and not the pipeline, which is the fact the hardware half has to live with: there is no memory stall for an accelerator to hide.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Optimize" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S06 (expected: position 7, body table 6x4,
notes_set yes, tracker Optimize via layout).

---

# Slide S07 (8 of 27)

Layout: "Title and body · Accelerate" (Slide → Apply layout). Insert after slide S06.

Title (exact text, do not shorten or rephrase):

    advance() is 95% of the remaining time, so the whole step goes on-chip after one doorbell

Body: insert the image `C:\Users\Kogan\HWSW_presentation\assets\grape_report.png` with your direct upload tool.
Size it to fill the body box: width 9.2 in, or height 3.4 in if that binds first, keeping the
aspect ratio; place it at x = 0.4 in, y = 1.6 in and centre it horizontally in the body box.
It must not overlap the title or the footer tracker. No caption, no border, no crop.

Do not touch the footer tracker: the layout already highlights "Accelerate".

Speaker notes (exact text, paste into the notes pane):

    Amdahl first, hardware second. The profile says 95% of the original run is inside advance(), so f = 0.95 and the ceiling for any accelerator is 20x; at the 50 MHz design target the model gives 3.78x, which is why the PRD asked for at least 4x. The boundary follows from the loop shape: 20,000 serial steps over five bodies and ten pairs. If the host called the device once per step, the register traffic would dwarf the arithmetic, so software loads the body state and the pair list, rings one doorbell, and reads the state back after all 20,000 steps. That costs about 150 AXI-Lite transactions per run, under 0.03% of the compute. ADR-0001 therefore chose MMIO only: no DMA, no stream ports, because a few hundred bytes per invocation do not justify a DMA engine and its verification.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Accelerate" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S07 (expected: position 8, body image grape_report.png,
notes_set yes, tracker Accelerate via layout).

---

# Slide S08 (9 of 27)

Layout: "Title and body · Accelerate" (Slide → Apply layout). Insert after slide S07.

Title (exact text, do not shorten or rephrase):

    grape_pipeline computes full IEEE FP64 in the benchmark's own operation order, with 3 adders and 3 multipliers chosen by a cycle model

Body: insert the image `C:\Users\Kogan\HWSW_presentation\assets\grape_block_diagram.png` with your direct upload tool.
Size it to fill the body box: width 9.2 in, or height 3.4 in if that binds first, keeping the
aspect ratio; place it at x = 0.4 in, y = 1.6 in and centre it horizontally in the body box.
It must not overlap the title or the footer tracker. No caption, no border, no crop.

Do not touch the footer tracker: the layout already highlights "Accelerate".

Speaker notes (exact text, paste into the notes pane):

    Inputs and outputs: a 32-bit AXI4-Lite slave with a 12-bit address inside a 4 KB window, plus one interrupt. Through that window software writes FP64 body state as word pairs, DT, a 32-bit NSTEPS, and the pair list; it reads back state, counters and status. The register map is 15 rows. Inside, the datapath is our own FP64 units: three 3-stage adders, three 3-stage multipliers, one radix-4 SRT square root of about 30 cycles and one Newton reciprocal of about 22 cycles. Deliberately no FMA: the Python trajectory rounds after every multiply and every add, and fusing them would break bit-exactness against the emulation model. A step is a fixed 290-operation graph; the cycle model list-scheduled it onto candidate unit mixes and 3 add plus 3 mul was the smallest mix under the 128-cycle budget. Clock target 50 MHz.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Accelerate" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S08 (expected: position 9, body image grape_block_diagram.png,
notes_set yes, tracker Accelerate via layout).

---

# Slide S09 (10 of 27)

Layout: "Title and body · Accelerate" (Slide → Apply layout). Insert after slide S08.

Title (exact text, do not shorten or rephrase):

    K1 is 124 cycles per step against a budget of 128, found only after the full-shape test exposed 162

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Design point | Cells (Yosys) | Area | K1 cycles/step | Verdict |
|---|---|---|---|---|
| 1-wide accumulate, 1-port RF | 393,367 | 2.938 mm² | 162 | fails K1 ≤ 128 |
| 3-wide accumulate, 3-port RF | 584,454 | 4.075 mm² | 124 | chosen: +38.7% area, −23.5% cycles |

Do not touch the footer tracker: the layout already highlights "Accelerate".

Speaker notes (exact text, paste into the notes pane):

    The uArch model predicted 123 cycles per step, and the bring-up smoke test measured 126, so every gate was green until sign-off. The sign-off test runs the real workload, all ten pairs for 20,000 steps, and there K1 was 162: the smoke test used only two pairs, a shape in which the static schedule hides the accumulate phase, and the RTL had implemented the ordered velocity accumulate as single-issue. Widening it to three ops per cycle, with a per-lane integrate and a 3-port body register file, brought K1 to 124, inside the model's 123 to 127 window. Both design points are fully synthesized, so the trade-off is measured: 38.7% more area for 23.5% fewer cycles. Renegotiating K1 to 162 was offered and declined at the sign-off checkpoint.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Accelerate" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S09 (expected: position 10, body table 3x5,
notes_set yes, tracker Accelerate via layout).

---

# Slide S10 (11 of 27)

Layout: "Title and body · Trade-offs" (Slide → Apply layout). Insert after slide S09.

Title (exact text, do not shorten or rephrase):

    Post-CTS timing gives 19.46 MHz against a 50 MHz target; the accumulate picker set the clock and a parallel-prefix rewrite bought 1.75x

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Metric | Value | Evidence |
|---|---|---|
| Cells / area (Yosys) | 584,454 / 4.075 mm² | pre-final-rewrite netlist |
| Cells / area (OpenLane) | 446,932 / 4.66 mm² | other recipe, not comparable |
| Fmax, post-CTS | 11.15 → 19.46 MHz (1.75x) | extrapolated from a 150 ns run |
| Power | ≈ 19.2 mW | default activity, indicative |
| Target | 50 MHz, missed 2.6x | integrate-multiplier path next |

Do not touch the footer tracker: the layout already highlights "Trade-offs".

Speaker notes (exact text, paste into the notes pane):

    The area figures come from two synthesis recipes: plain Yosys on the netlist before the final rewrite, and OpenLane's own synthesis of the final RTL; they are not comparable with each other. The clock story is the interesting one. The first post-CTS run gave 11.15 MHz, and the critical path was the 3-wide accumulate issue picker, a 60-deep combinational scan. Rewriting the two prefix operations as balanced trees removed that path without adding a cycle: 19.46 MHz, 1.75x, K1 still 124, every output bit-exact. That number is an extrapolation: the run was constrained at 150 ns and back-computes 51.38 ns from 98.6 ns of slack, and unlike the other two modules grape has no confirmation run near the result. The 50 MHz target is missed 2.6x; the new limiter is the integrate-multiplier operand path.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Trade-offs" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S10 (expected: position 11, body table 6x3,
notes_set yes, tracker Trade-offs via layout).

---

# Slide S11 (12 of 27)

Layout: "Title and body · Trade-offs" (Slide → Apply layout). Insert after slide S10.

Title (exact text, do not shorten or rephrase):

    At 19.46 MHz grape ties optimized Python and is about 15x slower than Rust

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Tier | Time / run | vs original | Evidence |
|---|---|---|---|
| Original Python | 231.20 ms | 1.00x | measured, course VM |
| Optimized Python | 143.13 ms | 1.62x | measured, course VM |
| grape @ 19.46 MHz | ≈ 139 ms = 127.4 ms compute + 11.6 ms residual | ≈ 1.66x | projected |
| Native Rust | 9.530 ms | 24.26x | measured, course VM |

Do not touch the footer tracker: the layout already highlights "Trade-offs".

Speaker notes (exact text, paste into the notes pane):

    This is the honest result. Compute is 2.48 million measured RTL cycles divided by the 19.46 MHz post-CTS clock, 127.4 ms. We add an assumed 5% Python residual for the harness and the two energy evaluations, 11.6 ms; nobody has measured that residual, and no software has ever called this hardware, so the interface time is unmeasured and can only make the row slower. The projection lands at about 139 ms: 1.66x over the original, a tie with optimized Python at 1.03x, and about 15x slower than the 9.53 ms Rust tier. Per step that is 124 cycles or 6.4 µs against 0.48 µs natively. The cause is the clock, not the interface; the residual alone already exceeds the whole Rust run.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Trade-offs" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S11 (expected: position 12, body table 5x4,
notes_set yes, tracker Trade-offs via layout).

---

# Slide S12 (13 of 27)

Layout: "Title and body · Trade-offs" (Slide → Apply layout). Insert after slide S11.

Title (exact text, do not shorten or rephrase):

    What would beat Rust: the clock it takes, a wider unit mix, and a Rust host around the same hardware

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Projection | Result | vs Rust | Assumes |
|---|---|---|---|
| Clock for compute parity | ≈ 260 MHz | parity | 13.4x today's clock, no residual |
| At the 50 MHz target | 61.16 ms | 6.42x slower | timing closure |
| 3 add + 4 mul (model) | 117 cycles/step, 120.2 ms | 12.6x slower | model only |
| Rust host + same HW | 127.9 ms | 13.4x slower | residual 5% of the Rust run |
| N = 100, 24 add + 24 mul | 0.029 µs/pair | 1.6x faster | clock survives 8x issue |

Do not touch the footer tracker: the layout already highlights "Trade-offs".

Speaker notes (exact text, paste into the notes pane):

    Everything on this slide is a projection from the schedule model and the report's numbers; derivations.md holds the arithmetic. Clock: the datapath alone matches Rust at about 260 MHz, 13.4 times what post-CTS timing supports; at the 50 MHz target the system would still be 6.42x slower. Width: a fourth multiplier saves 6 cycles per step in the model, 123 to 117, because at N = 5 one pair's 80-cycle chain bounds the step. Host: swapping Python for Rust around the same device trims the residual from 11.6 ms to about 0.48 ms, an 8% change. Only more bodies change the verdict: at N = 100 the model needs 24 adders and 24 multipliers to run 1.6x faster than native, assuming the clock survives the wider issue logic, which our own 1-wide versus 3-wide data says it does not.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Trade-offs" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S12 (expected: position 13, body table 6x4,
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
