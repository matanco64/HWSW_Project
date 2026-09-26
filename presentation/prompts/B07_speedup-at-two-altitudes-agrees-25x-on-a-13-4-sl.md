# Slide B07 (BACKUP)

Layout: "Title and body". Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    Speedup at two altitudes agrees: 25x on a 13.4% slice is 1.148x; two profilers give f = 0.496 vs 0.40

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Question | Numbers | Reading |
|---|---|---|
| mtf stage alone vs whole benchmark | 80.4 ms / 3.169 ms = 25.4x at 50 MHz; 1/((1−0.1344)+0.1344/25) = 1.148x | same result at two altitudes |
| huffman f from cProfile (PRD) | f = 0.496 → 1/(1−0.496) = 1.98x | per-call overhead inflates tiny bit-reader calls |
| huffman f from VM py-spy (report) | f = 0.40 → 1/(1−0.40) = 1.67x | sampled; the one the reports use |
| mtf standalone ceiling | f = 0.1344 → 1.16x | why it is chained, not standalone |
| Chain, measured at the Rust boundary | ≈ 28x over the Python loop, ≈ 1.3x slower than Rust, ≈ 6.6x end to end | the figure the reports quote |

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   Accelerate   ·   **Trade-offs**

Speaker notes (exact text, paste into the notes pane):

    Two questions the reviewers asked. First, how can a stage be 25x faster while the benchmark barely moves? Because the move-to-front stage is 13.44% of the original run: a 25x stage speedup on that slice gives 1.148x by Amdahl, and both numbers describe the same result, one at stage altitude and one at benchmark altitude. Second, why did the huffman fraction change? The PRD sized the module from a local cProfile run, f = 0.496, a 1.98x ceiling; cProfile's per-call overhead inflates the many tiny bit-reader calls. The sampled py-spy profile on the course VM gives 0.40 and a 1.67x ceiling, and that is the denominator the reports use. Neither standalone figure is a report claim; the reports quote the chain measured at the Rust boundary.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Trade-offs", and the notes are saved. Reply with a screenshot of
the slide in edit view.
