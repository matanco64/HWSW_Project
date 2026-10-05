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
