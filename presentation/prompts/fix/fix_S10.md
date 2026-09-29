# Correction for slide S10 (deck slide 11): replace the table

Go to slide 11. Its title and speaker notes are correct; do not touch them. The table was too
tall; the spec table has been shortened. Replace it.

1. Delete the existing table.
2. Insert this table exactly (paste as a styled HTML table is fine): header row bold, fill #1F4E79,
   white text; body rows Roboto 16 pt (14 pt if 16 pt does not fit, 12 pt as the last resort):

| Metric | Value | Evidence |
|---|---|---|
| Cells / area (Yosys) | 584,454 / 4.075 mm² | pre-final-rewrite netlist |
| Cells / area (OpenLane) | 446,932 / 4.66 mm² | other recipe, not comparable |
| Fmax, post-CTS | 11.15 → 19.46 MHz (1.75x) | extrapolated from a 150 ns run |
| Power | ≈ 19.2 mW | default activity, indicative |
| Target | 50 MHz, missed 2.6x | integrate-multiplier path next |

3. Table at x = 0.4 in, y = 1.6 in, width 9.2 in; set column widths so that no header word breaks
   mid-word and the longest column gets the most width; bottom edge at or above y = 5.0 in.

Done when: the table's bottom edge is at or above 5.0 in, no cell text is cut, no header wraps
mid-word. Reply with the STATUS block for S10 (expected: position 11, body table 6x3).
