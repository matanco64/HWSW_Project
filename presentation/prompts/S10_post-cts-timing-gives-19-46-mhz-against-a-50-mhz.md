# Slide S10 (11 of 27)

Layout: "Title and body". Insert after slide S09.

Title (exact text, do not shorten or rephrase):

    Post-CTS timing gives 19.46 MHz against a 50 MHz target; the accumulate picker set the clock and a parallel-prefix rewrite bought 1.75x

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Metric | Value | Evidence level |
|---|---|---|
| Cells / area, plain Yosys | 584,454 / 4.075 mm² | synthesis before the final picker rewrite |
| Cells / area, OpenLane recipe, final RTL | 446,932 / 4.66 mm² | different recipe, not comparable with the row above |
| Fmax, post-CTS STA | 11.15 → 19.46 MHz (1.75x), bit-exact | extrapolated from a 150 ns run with 98.6 ns slack |
| Power | ≈ 19.2 mW | tool estimate, default activity, indicative only |
| Clock target | 50 MHz, missed 2.6x | next limiter: integrate-multiplier operand path |

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   Accelerate   ·   **Trade-offs**

Speaker notes (exact text, paste into the notes pane):

    The area figures come from two synthesis recipes: plain Yosys on the netlist before the final rewrite, and OpenLane's own synthesis of the final RTL; they are not comparable with each other. The clock story is the interesting one. The first post-CTS run gave 11.15 MHz, and the critical path was the 3-wide accumulate issue picker, a 60-deep combinational scan. Rewriting the two prefix operations as balanced trees removed that path without adding a cycle: 19.46 MHz, 1.75x, K1 still 124, every output bit-exact. That number is an extrapolation: the run was constrained at 150 ns and back-computes 51.38 ns from 98.6 ns of slack, and unlike the other two modules grape has no confirmation run near the result. The 50 MHz target is missed 2.6x; the new limiter is the integrate-multiplier operand path.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Trade-offs", and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S10 (expected: position 11, body table 6x3,
notes_set yes, tracker Trade-offs highlighted).
