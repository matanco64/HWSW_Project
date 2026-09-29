# Batch S13–S20: build 8 slides autonomously, then export

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

# Slide S13 (14 of 27)

Layout: "Title and body · Analyze" (Slide → Apply layout). Insert after slide S12.

Title (exact text, do not shorten or rephrase):

    pyflate is bzip2 decompression in pure Python: Huffman decode, move-to-front, run-length, inverse BWT

Body: insert the image `C:\Users\Kogan\HWSW_presentation\assets\pyflate_stages.png` with your direct upload tool.
Size it to fill the body box: width 9.2 in, or height 3.4 in if that binds first, keeping the
aspect ratio; place it at x = 0.4 in, y = 1.6 in and centre it horizontally in the body box.
It must not overlap the title or the footer tracker. No caption, no border, no crop.

Do not touch the footer tracker: the layout already highlights "Analyze".

Speaker notes (exact text, paste into the notes pane):

    Despite its name, the measured fixture is bzip2, not DEFLATE: interpreter.tar.bz2 expands from 67,562 bytes to 399,360 bytes, and the MD5 check sits outside the timer. One block, six Huffman tables, 148,271 symbols, with a table switch every 50 symbols. The symbol loop, which is the bit reader, Huffman decode, move-to-front and RUNA/RUNB expansion, produces the 336,184-byte L-vector, the last column of the BWT matrix. Inverse BWT and RLE4, where four equal bytes and a count k stand for 4 + k copies, produce the output. Only the standard library is used. Keep this boundary in mind: the Rust kernel and both accelerators take exactly the symbol loop and leave the rest in Python.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Analyze" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S13 (expected: position 14, body image pyflate_stages.png,
notes_set yes, tracker Analyze via layout).

---

# Slide S14 (15 of 27)

Layout: "Title and body · Analyze" (Slide → Apply layout). Insert after slide S13.

Title (exact text, do not shorten or rephrase):

    A canonical Huffman code is decoded by comparing the next bits against one threshold per length

Body: insert the image `C:\Users\Kogan\HWSW_presentation\assets\huffman_tree.png` with your direct upload tool.
Size it to fill the body box: width 9.2 in, or height 3.4 in if that binds first, keeping the
aspect ratio; place it at x = 0.4 in, y = 1.6 in and centre it horizontally in the body box.
It must not overlap the title or the footer tracker. No caption, no border, no crop.

Do not touch the footer tracker: the layout already highlights "Analyze".

Speaker notes (exact text, paste into the notes pane):

    With code lengths [2,2,2,3,3] the canonical codes are 00, 01, 10 for a, b, c and 110, 111 for d, e: codes of one length are consecutive integers, so each length has a limit and a base. Decode 01110: peek 01, emit b, consume two bits. Peek 11, above the length-2 range, so extend to 110 = 6, at or below limit[3] = 7; base[3] = 3, so perm[3] = d. Nothing is scanned. The original matcher visited about 5.0 entries per symbol out of 258, which is why the table alone was not the whole win.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Analyze" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S14 (expected: position 15, body image huffman_tree.png,
notes_set yes, tracker Analyze via layout).

---

# Slide S15 (16 of 27)

Layout: "Title and body · Profile" (Slide → Apply layout). Insert after slide S14.

Title (exact text, do not shorten or rephrase):

    40.86% of the original samples are Huffman symbol decode, 13.44% move-to-front, and about a quarter is the bit reader

Body: insert the image `C:\Users\Kogan\HWSW_presentation\assets\print_pyflate_stock_slide.png` with your direct upload tool.
Size it to fill the body box: width 9.2 in, or height 3.4 in if that binds first, keeping the
aspect ratio; place it at x = 0.4 in, y = 1.6 in and centre it horizontally in the body box.
It must not overlap the title or the footer tracker. No caption, no border, no crop.

Do not touch the footer tracker: the layout already highlights "Profile".

Speaker notes (exact text, paste into the notes pane):

    Two profilers answer two questions. perf on the debug build says the interpreter sits in _PyEval_EvalFrameDefault at 99.50% inclusive, but it cannot name a Python function. py-spy on release CPython can, from 372 samples: find_next_symbol, the Huffman matcher, is 40.86% inclusive; move_to_front 13.44%; the bit-reader functions snoopbits, readbits and _mask are 9.41%, 9.95% and 5.91% of self time, together about a quarter; bwt_reverse is 14.52% inclusive. The surprise is that the matcher visits only 5.0 entries on average out of 258, so a lookup table cannot be the whole answer. The C-frame view explains the rest: a quarter of the time allocates and frees objects, a per-byte int and a list slice per symbol, and 9.45% is call machinery. These are sparse profiles: a 1% cell is one to four samples.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Profile" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S15 (expected: position 16, body image print_pyflate_stock_slide.png,
notes_set yes, tracker Profile via layout).

---

# Slide S16 (17 of 27)

Layout: "Title and body · Optimize" (Slide → Apply layout). Insert after slide S15.

Title (exact text, do not shorten or rephrase):

    Three optimizations, each measured by reverting it, take pyflate from 1,123.49 ms to 281.16 ms, 4.00x

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Reverted from the shipped decoder (T3) | VM trial 1 | VM trial 2 |
|---|---|---|
| None (full T3 runtime) | 271.2 ms | 273.9 ms |
| Regex-assisted RLE4 | +100.6 ms | +98.7 ms |
| Primary Huffman lookup | +52.6 ms | +49.4 ms |
| Counting-sort BWT | +20.8 ms | +17.2 ms |
| All reverted (T1 only) | +393.6 ms | +397.2 ms |

Do not touch the footer tracker: the layout already highlights "Optimize".

Speaker notes (exact text, paste into the notes pane):

    Three changes shipped on top of the per-byte fixes: a flat primary lookup table for Huffman codes with a canonical fallback, regex-assisted RLE4 so the run scan happens in C, and counting-sort construction of the BWT traversal table. To attribute the gain we revert one change at a time and time best-of-seven interleaved decompressions on the VM; the two trials agree within 4 ms on every row. RLE4 is worth about 100 ms, the lookup about 50 ms, the BWT sort about 20 ms. Costs need not add, and the development interpreter ranked them the other way round, so measure on the platform you report. End to end under pyperformance: 1,123.49 ± 10.99 to 281.16 ± 3.05 ms, 4.00x, 75.0% less time, byte-exact against bz2.decompress. The ablation drives the module directly, so its 271.2 ms is not 281.16 ms.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Optimize" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S16 (expected: position 17, body table 6x3,
notes_set yes, tracker Optimize via layout).

---

# Slide S17 (18 of 27)

Layout: "Title and body · Optimize" (Slide → Apply layout). Insert after slide S16.

Title (exact text, do not shorten or rephrase):

    After optimization inverse BWT is about 80% of what remains; a Rust kernel for symbol decode reaches 170.01 ms, 6.61x end to end

Body: insert the image `C:\Users\Kogan\HWSW_presentation\assets\print_pyflate_opt_slide.png` with your direct upload tool.
Size it to fill the body box: width 9.2 in, or height 3.4 in if that binds first, keeping the
aspect ratio; place it at x = 0.4 in, y = 1.6 in and centre it horizontally in the body box.
It must not overlap the title or the footer tracker. No caption, no border, no crop.

Do not touch the footer tracker: the layout already highlights "Optimize".

Speaker notes (exact text, paste into the notes pane):

    After the Python work the profile changes shape. From 122 samples, _decode_symbols_python, the loop that replaced the matcher, is 32.79% self; inverse BWT is 38.52% inclusive and rle4_expand 5.74%. The Rust/PyO3 BlockDecoder takes that symbol loop in one call per block; headers, inverse BWT, RLE4 and MD5 stay in Python. Under direct pyperf that is 283.88 ± 3.34 to 170.01 ± 2.30 ms, 1.67x; against the original, 6.61x and 84.9% less time. The kernel itself takes 3.304 ms per decode where the Python loop took about 117 ms. What remains is inverse BWT: 137.7 ms for the whole transform, about 80% of the remaining time; the traversal alone is 47.8 ms, never add the two. Caveat: a 32.79% share would cap the gain at 1.49x, below the measured 1.67x, so 122 samples locate work but do not calibrate Amdahl.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Optimize" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S17 (expected: position 18, body image print_pyflate_opt_slide.png,
notes_set yes, tracker Optimize via layout).

---

# Slide S18 (19 of 27)

Layout: "Title and body · Accelerate" (Slide → Apply layout). Insert after slide S17.

Title (exact text, do not shorten or rephrase):

    Huffman decode is a 0.40 fraction of the original run, a 1.67× ceiling alone, so we chain it with move-to-front on one AXI stream

Body: insert the image `C:\Users\Kogan\HWSW_presentation\assets\decode_report.png` with your direct upload tool.
Size it to fill the body box: width 9.2 in, or height 3.4 in if that binds first, keeping the
aspect ratio; place it at x = 0.4 in, y = 1.6 in and centre it horizontally in the body box.
It must not overlap the title or the footer tracker. No caption, no border, no crop.

Do not touch the footer tracker: the layout already highlights "Accelerate".

Speaker notes (exact text, paste into the notes pane):

    On the VM py-spy profile, Huffman symbol decode plus its bit reader is f = 0.40 of the 1,123.49 ms original, so even an infinitely fast decoder caps at 1/(1 − 0.40) = 1.67×. Move-to-front is another 0.1344 and consumes exactly the decoder's 148,271 output symbols, so the two are chained on chip; that covers about half the run on this profile (the module doc's ≈ 0.63 and ≈ 2.7× ceiling summed the older cProfile Huffman share of 49.6 %). Who does what: the CPU parses each block header, writes the 6 × 147 code lengths and the used-byte map over AXI4-Lite, starts both modules, then runs inverse BWT, RLE4 and MD5. The hardware builds its tables, decodes, and hands each symbol to mtf_cam as one 32-bit AXI-Stream beat, value in TDATA[8:0], type in [11:9] (ADR-0006); platform DMA returns the L-vector.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Accelerate" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S18 (expected: position 19, body image decode_report.png,
notes_set yes, tracker Accelerate via layout).

---

# Slide S19 (20 of 27)

Layout: "Title and body · Accelerate" (Slide → Apply layout). Insert after slide S18.

Title (exact text, do not shorten or rephrase):

    huffman_engine decodes one symbol per cycle: a barrel shifter, 20 parallel comparators, and six preloaded table sets so a table switch costs zero cycles

Body: insert the image `C:\Users\Kogan\HWSW_presentation\assets\huffman_block_diagram.png` with your direct upload tool.
Size it to fill the body box: width 9.2 in, or height 3.4 in if that binds first, keeping the
aspect ratio; place it at x = 0.4 in, y = 1.6 in and centre it horizontally in the body box.
It must not overlap the title or the footer tracker. No caption, no border, no crop.

Do not touch the footer tracker: the layout already highlights "Accelerate".

Speaker notes (exact text, paste into the notes pane):

    The only serial dependency is the recurrence: where symbol N+1 starts depends on symbol N's length. So that loop is one cycle: barrel-shift the 64-bit window, compare it against the first-code threshold of all 20 lengths in parallel, priority-encode the shortest match, consume; symbol-table lookup and beat emission pipeline behind the loop. bzip2 switches tables every 50 symbols, so six table register sets are preloaded and the switch is 0-cycle (ADR-0008). Inputs: a 32-bit compressed stream and an 8-bit selector stream; output: 32-bit beats with a 9-bit symbol; target 50 MHz. On the real block: 149,276 cycles for 148,271 symbols, K1 = 1.0068 against a budget of 1.10. The first full-shape run showed 1.5068, an almost-full gate that ignored the same-cycle pop, fixed in one line; un-gating DEFLATE at coverage then exposed an extra-bit-count latching bug the unit tests never reached.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Accelerate" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S19 (expected: position 20, body image huffman_block_diagram.png,
notes_set yes, tracker Accelerate via layout).

---

# Slide S20 (21 of 27)

Layout: "Title and body · Accelerate" (Slide → Apply layout). Insert after slide S19.

Title (exact text, do not shorten or rephrase):

    mtf_cam is a 256-entry shift-register list read by rank; width 8 sits at the knee of the area/cycle sweep

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| W (output bytes/beat) | Area | K3 model (cyc/sym) | K3 ≤ 1.10 | Verdict |
|---|---:|---:|---|---|
| 4 | 0.182 mm² | 1.175 | fails | rejected |
| 8 | 0.187 mm² | 1.063 | meets | chosen: the knee |
| 16 | 0.208 mm² | 1.023 | meets | +10.9 % area for 3.8 % fewer cycles, not needed |

Do not touch the footer tracker: the layout already highlights "Accelerate".

Speaker notes (exact text, paste into the notes pane):

    Each bzip2 symbol is a rank into a 256-entry list of recently used bytes: emit that byte and move it to the front. Hardware: a 256 × 8 shift register with a 256:1 read mux; every entry is writable each cycle, so the move takes one cycle and needs no RAM (the "CAM" is the list; nothing is content-searched). Run groups expand through a W-byte packer; W is the knob: W = 4 breaks the K3 ≤ 1.10 KPI, W = 16 costs 10.9 % more area for 3.8 % fewer cycles, so W = 8 is the knee; the list is 68 % of the 0.187 mm². Measured: 158,441 cycles, K3 = 1.0686 against the 1.063 model. The uArch review caught that the cycle model enqueues two items in one cycle, so the item FIFO needed a 2-wide write port; with one port K3 lands near 1.30.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Accelerate" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S20 (expected: position 21, body table 4x5,
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
