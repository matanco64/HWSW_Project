# Correction for slide S12 (deck slide 13): replace the table

Go to slide 13. Its title and speaker notes are correct; do not touch them. The table was too
tall; the spec table has been shortened. Replace it.

1. Delete the existing table.
2. Insert this table exactly (paste as a styled HTML table is fine): header row bold, fill #1F4E79,
   white text; body rows Roboto 16 pt (14 pt if 16 pt does not fit, 12 pt as the last resort):

| Projection | Result | vs Rust | Assumes |
|---|---|---|---|
| Clock for compute parity | ≈ 260 MHz | parity | 13.4x today's clock, no residual |
| At the 50 MHz target | 61.16 ms | 6.42x slower | timing closure |
| 3 add + 4 mul (model) | 117 cycles/step, 120.2 ms | 12.6x slower | model only |
| Rust host + same HW | 127.9 ms | 13.4x slower | residual 5% of the Rust run |
| N = 100, 24 add + 24 mul | 0.029 µs/pair | 1.6x faster | clock survives 8x issue |

3. Table at x = 0.4 in, y = 1.6 in, width 9.2 in; set column widths so that no header word breaks
   mid-word and the longest column gets the most width; bottom edge at or above y = 5.0 in.

Done when: the table's bottom edge is at or above 5.0 in, no cell text is cut, no header wraps
mid-word. Reply with the STATUS block for S12 (expected: position 13, body table 6x4).
