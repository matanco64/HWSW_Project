# Batch B01–B06: build 6 slides autonomously, then export

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

# Slide B01 (BACKUP)

Layout: "Title and body · Accelerate" (Slide → Apply layout). Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    grape's step is a fixed 290-operation graph scheduled onto 3 adders and 3 multipliers

Body: insert the image `C:\Users\Kogan\HWSW_presentation\assets\grape_uarch.png` with your direct upload tool.
Size it to fill the body box: width 9.2 in, or height 3.4 in if that binds first, keeping the
aspect ratio; place it at x = 0.4 in, y = 1.6 in and centre it horizontally in the body box.
It must not overlap the title or the footer tracker. No caption, no border, no crop.

Do not touch the footer tracker: the layout already highlights "Accelerate".

Speaker notes (exact text, paste into the notes pane):

    Datapath: pair i issues at cycle 2i into the shared units. Per pair, the front end subtracts the three coordinates, squares and sums them, takes the square root, multiplies to d3, takes the reciprocal, then forms the magnitude and the six force terms; every one of those is a Python-visible binary64 rounding held in its own register. Per step that is 125 adds, 145 multiplies, 10 square roots and 10 reciprocals, 290 operations, which a greedy list scheduler places on the units as a static reservation table checked by an SVA assertion. Control: the step FSM is IDLE, LATCH, RUN, COMMIT, DONE or ABORT; RUN ends when all 290 ops have retired and ABORT is sampled only at COMMIT. The accumulate sequencer keeps a 5-by-3 busy scoreboard per body component so velocity updates on one lane stay in program order. Timing budget: each pipeline stage was estimated at 8 ns or less against the 20 ns period, which is why the 50 MHz target looked comfortable on paper; the picker path that later set the clock was not in that table.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Accelerate" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for B01 (expected: position end of deck, body image grape_uarch.png,
notes_set yes, tracker Accelerate via layout).

---

# Slide B02 (BACKUP)

Layout: "Title and body · Accelerate" (Slide → Apply layout). Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    The 162-cycle miss hid behind a 2-pair smoke test; the full-shape test at sign-off found it

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Stage | Workload | K1 cycles/step | Result |
|---|---|---|---|
| uArch schedule model | 290-op graph, nominal / worst corner | 123 / 127 | within 128 |
| DV bring-up smoke | 2 pairs, 2 steps | 126 | within 128, gate green |
| DV sign-off, full benchmark | 10 pairs, 20,000 steps | 162 | fails 128 |
| After 3-wide accumulate + per-lane integrate | 10 pairs, 20,000 steps | 124 | passes; smoke fell to 111 |

Do not touch the footer tracker: the layout already highlights "Accelerate".

Speaker notes (exact text, paste into the notes pane):

    The model said 123, the smoke test said 126, and both were honest; the smoke shape simply could not show the problem. With two pairs the static force schedule dominates and the accumulate phase is hidden; with ten pairs the single-issue accumulate and the globally gated integrate serialized, and the real benchmark measured 162. The fix, widening the accumulate to three issues per cycle and letting each lane integrate as soon as its own chain retires, landed at 124, and the same smoke test then read 111. The lesson written into the flow: measure the KPI on the full-shape workload at bring-up, not only on the tiny smoke; the gap was visible one stage earlier to anyone who ran ten pairs. The huffman module paid that rule back on its first full-shape run.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Accelerate" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for B02 (expected: position end of deck, body table 5x4,
notes_set yes, tracker Accelerate via layout).

---

# Slide B03 (BACKUP)

Layout: "Title and body · Accelerate" (Slide → Apply layout). Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    Unit-mix sweep: 2+2 → 133 cycles, 3+3 → 123/127, 3+4 → 117; 3+3 is the last point under 128

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Inventory | Step cycles, nominal (sqrt 30 / rcp 22) | Worst corner (32 / 24) | Verdict |
|---|---|---|---|
| 2 add, 2 mul | 133 | 137 | issue-bandwidth bound: 145 mul-ops per step |
| 2 add, 3 mul | 125 | 129 | fails the worst corner by 1 cycle |
| 3 add, 3 mul | 123 | 127 | chosen: last point under 128 at both corners |
| 3 add, 4 mul | 117 | 121 | 6 cycles for a fourth multiplier |

Do not touch the footer tracker: the layout already highlights "Accelerate".

Speaker notes (exact text, paste into the notes pane):

    The sweep is simulated, not estimated: schedule_model.py builds the 290-operation step and list-schedules it onto each inventory, with the unit latencies at nominal and at a two-cycle-slower corner for sqrt and reciprocal. Two multipliers cannot carry 145 mul-ops per step, so both 2-mul points sit at 133. Two adders with three multipliers make the nominal budget at 125 but miss the worst corner by one cycle, so the ADR rejected it. Three of each gives 123 and 127, the last mix that passes at both corners, and it is what the RTL implements. A fourth multiplier buys 6 cycles because at N = 5 the step is latency-bound by one pair's chain; the stretch goal of 64 cycles was declared unreachable at issue interval 2 and not pursued. The output of the model, rerun for this deck, is copied into derivations.md.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Accelerate" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for B03 (expected: position end of deck, body table 5x4,
notes_set yes, tracker Accelerate via layout).

---

# Slide B04 (BACKUP)

Layout: "Title and body · Trade-offs" (Slide → Apply layout). Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    huffman_engine's area is storage: 1.634 mm² as built in flip-flops, ≈ 0.75 mm² projected with SRAM macros, and two table sets would save area but break K1

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

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

Do not touch the footer tracker: the layout already highlights "Trade-offs".

Speaker notes (exact text, paste into the notes pane):

    The decode datapath is 1.3 % of the design and carries no sequential area; huff_tables plus huff_regs are 95 %. That is the whole area story, so the only real lever is where the tables live. As built they are flip-flops, which is why the 1.0 mm² soft ceiling is missed by 1.63×. Moving the two large single-port arrays into SRAM macros projects ≈ 0.75 mm² of standard cells plus two macros, but no SRAM compiler exists in our open sky130 flow, so it is a projection. Cutting the six table sets to two would save only ≈ 0.1 mm² and re-derive tables at every 50-symbol switch, pushing K1 past 1.1; rejected. The second table is what the agent pre-review found before any simulation: 13 musts in the first RTL pass, the three above being the ones a testbench would have found last, because each needs back-pressure, a second block, or a first-symbol corner. All 13 were fixed and 36/36 unit and smoke tests passed on the fixed RTL.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Trade-offs" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for B04 (expected: position end of deck, body table 8x5,
notes_set yes, tracker Trade-offs via layout).

---

# Slide B05 (BACKUP)

Layout: "Title and body · Trade-offs" (Slide → Apply layout). Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    mtf_cam in full: K3 1.0686 measured against a 1.063 model, 0.187 mm² with 5.3× headroom, 37.5 MHz from a run that met 27 ns, and list invariants proven unbounded at 16 entries

Body: insert the image `C:\Users\Kogan\HWSW_presentation\assets\mtf_block_diagram.png` with your direct upload tool.
Size it to fill the body box: width 9.2 in, or height 3.4 in if that binds first, keeping the
aspect ratio; place it at x = 0.4 in, y = 1.6 in and centre it horizontally in the body box.
It must not overlap the title or the footer tracker. No caption, no border, no crop.

Do not touch the footer tracker: the layout already highlights "Trade-offs".

Speaker notes (exact text, paste into the notes pane):

    The block diagram: a 256-entry shift-register list with a 256:1 rank read mux and a registered parallel move, an item FIFO with a 2-wide write port, the RUNA/RUNB run counter, the run expander and the W = 8 lane packer behind an AXI4-Lite register block. Numbers: 158,441 cycles for the benchmark block, K3 = 1.0686 on the DUT against the 1.063 model, the delta being the FIFO's 2-slot reservation; 18,814 cells, 0.187 mm², 5.3× under the 1.0 mm² soft ceiling with the list at 68 %; Fmax 37.5 MHz from a post-CTS run whose 27 ns constraint was met (+0.3066 ns worst setup slack), the 20 ns run having failed by 6.5964 ns; power ≈ 10.2 mW at that operating point, default activity, indicative only. Formal: the three list invariants (permutation preserved, lookup returns the pre-shift byte at rank r, the moved byte lands at rank 0) are proven unbounded by k-induction at N_LIST=16; at the production 256 the general check is bounded to depth 6 and a fill-abstracted run shows 24 consecutive moves preserve the permutation. An unbounded proof at 256 was tried with smtbmc k-induction, ABC PDR and rIC3, all timing out at 900 s: a SAT wall, stated as such.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Trade-offs" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for B05 (expected: position end of deck, body image mtf_block_diagram.png,
notes_set yes, tracker Trade-offs via layout).

---

# Slide B06 (BACKUP)

Layout: "Title and body · Accelerate" (Slide → Apply layout). Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    Verification evidence per module: tests, line/toggle/branch coverage, formal, both simulators

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Evidence | grape_pipeline | huffman_engine | mtf_cam |
|---|---|---|---|
| Directed + random tests, Verilator and Icarus | 9/9 | 17/17 | 16/16 |
| Line / toggle coverage | 91.7% / 96.0% (all signals) | 90.4% / 90.3% (control subset) | 92.0% / 93.8% (control subset) |
| Branch coverage; functional bins hit | 94.8%; 59 | 91.7%; 34 | 96.8%; 129 |
| Golden equivalence on the real input | 20,000 steps, 0 mismatches | 148,271 beats trace-exact | 336,184 bytes byte-exact |
| Formal (SymbiYosys) | FSM arcs, BMC depth 40 + cover | 4 tasks: ctrl arcs, skid, aligner cap | 7 tasks; unbounded at 16 entries, bounded at 256 |

Do not touch the footer tracker: the layout already highlights "Accelerate".

Speaker notes (exact text, paste into the notes pane):

    Every module runs its full directed plus constrained-random suite on Verilator and again on Icarus, the 4-state simulator that shows X after reset. The scoreboard oracle is the benchmark's own Python code, and each module is checked on the real benchmark input end to end: grape bit-exact over 20,000 steps, huffman trace-exact over 148,271 beats, mtf byte-exact over 336,184 bytes, and the huffman-to-mtf chain is co-simulated as well. Coverage carries a caveat: huffman and mtf toggle coverage is measured over the control-signal subset, because wide data buses whose upper bits the benchmark cannot toggle are waived with the width sweep as evidence; grape's is over all signals. Formal covers control properties only: grape's FSM arcs at BMC depth 40, huffman's four tasks, and mtf's list invariants, unbounded at 16 entries but only bounded at the production 256.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Accelerate" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for B06 (expected: position end of deck, body table 6x4,
notes_set yes, tracker Accelerate via layout).

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
