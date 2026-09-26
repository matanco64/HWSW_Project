# Slide S15 (15 of 26)

Layout: "Title and body". Insert after slide S14.

Title (exact text, do not shorten or rephrase):

    40.86% of the original samples are Huffman symbol decode, 13.44% move-to-front, and about a quarter is the bit reader

Body: Insert → Image → Upload from computer → `\\wsl.localhost\Ubuntu\home\yuvalk\HWSW\HWSW_Proj\presentation\assets\print_pyflate_stock.png`.
Fit it inside the body box, keep aspect ratio, centre it. No caption, no border.

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   **Profile**   ·   Optimize   ·   Accelerate   ·   Trade-offs

Speaker notes (exact text, paste into the notes pane):

    Two profilers answer two questions. perf on the debug build says the interpreter sits in _PyEval_EvalFrameDefault at 99.50% inclusive, but it cannot name a Python function. py-spy on release CPython can, from 372 samples: find_next_symbol, the Huffman matcher, is 40.86% inclusive; move_to_front 13.44%; the bit-reader functions snoopbits, readbits and _mask are 9.41%, 9.95% and 5.91% of self time, together about a quarter; bwt_reverse is 14.52% inclusive. The surprise is that the matcher visits only 5.0 entries on average out of 258, so a lookup table cannot be the whole answer. The C-frame view explains the rest: a quarter of the time allocates and frees objects, a per-byte int and a list slice per symbol, and 9.45% is call machinery. These are sparse profiles: a 1% cell is one to four samples.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Profile", and the notes are saved. Reply with a screenshot of
the slide in edit view.
