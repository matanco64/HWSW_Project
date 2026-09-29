# Correction for slide S05 (deck slide 6): replace the table

Go to slide 6. Its title and speaker notes are correct; do not touch them. The table was too
tall; the spec table has been shortened. Replace it.

1. Delete the existing table.
2. Insert this table exactly (paste as a styled HTML table is fine): header row bold, fill #1F4E79,
   white text; body rows Roboto 16 pt (14 pt if 16 pt does not fit, 12 pt as the last resort):

| Variant | Result | Against | Where |
|---|---|---|---|
| Struct-of-arrays | 0.88x | original | dev host |
| NumPy | 0.35–0.46x | original | dev host |
| Barnes-Hut, N = 5 | 3.92x slower | direct sum | VM |
| Rust, 9.530 ms | 15.25x | optimized Python, 145.30 ms | VM |
| Rust, 9.530 ms | 24.26x | original, 231.20 ms | VM |

3. Table at x = 0.4 in, y = 1.6 in, width 9.2 in; set column widths so that no header word breaks
   mid-word and the longest column gets the most width; bottom edge at or above y = 5.0 in.

Done when: the table's bottom edge is at or above 5.0 in, no cell text is cut, no header wraps
mid-word. Reply with the STATUS block for S05 (expected: position 6, body table 6x4).
