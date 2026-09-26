# Slide S25 (26 of 27)

Layout: "Title and body". Insert after slide S24.

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

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   Accelerate   ·   **Trade-offs**

Speaker notes (exact text, paste into the notes pane):

    Every hardware frequency here is a post-CTS static-timing estimate: cells and clock tree placed, signal wires not routed, no silicon. grape's 19.46 MHz is the weakest number in the deck, back-computed from a run constrained at 150 ns, a 2.9x extrapolation with no confirmation run. Every end-to-end speedup is a projection: measured RTL cycles over that clock, plus a 5% Python residual we assumed rather than measured, and no interface or DMA time at all. The grape area predates the final picker rewrite; the OpenLane area of the final RTL uses a different recipe. Power figures use default switching activity at three different clocks, so they are indicative and not comparable. On the software side, later commits pass the exactness oracle but were not re-timed.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Trade-offs", and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S25 (expected: position 26, body table 7x3,
notes_set yes, tracker Trade-offs highlighted).
