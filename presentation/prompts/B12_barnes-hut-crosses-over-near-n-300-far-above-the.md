# Slide B12 (BACKUP)

Layout: "Title and body". Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    Barnes-Hut crosses over near N = 300, far above the benchmark's N = 5; grape's cost per pair falls with the pair count

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| N | Direct | Barnes-Hut | BH / direct |
|---|---|---|---|
| 5 | 0.020 ms | 0.077 ms | 3.92x |
| 100 | 4.746 ms | 8.410 ms | 1.77x |
| 300 | 42.977 ms | 42.489 ms | 0.99x |
| 800 | 313.489 ms | 158.846 ms | 0.51x |
| 1,600 | 1,254.660 ms | 382.471 ms | 0.30x |

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   Accelerate   ·   **Trade-offs**

Speaker notes (exact text, paste into the notes pane):

    Section 5 of the nbody report extends the workload beyond the required N = 5. It is a pure-Python force-evaluation sweep on the VM with the Barnes-Hut tree rebuilt at each evaluation, θ = 0.5, best of seven; it is not the full integration benchmark. At five bodies the tree costs 3.92x more than direct summation; the crossover is near N = 300 for this distribution of near-coplanar circular orbits, and the median acceleration error is not a worst-case or trajectory bound. Native Rust stays 21–22x over rolled Python from N = 100 to 3,200. The specialized generator grows as O(N²) in source size and falls back to the rolled pair loop above 20,000 pairs. On the hardware side, grape is latency-bound at N = 5: 12.3 cycles per pair in the model, 12.4 measured, falling to about 4.4 cycles per pair at N = 100 as the pipelined units fill; but above N ≈ 300 the software competitor becomes Barnes-Hut rather than direct summation, so the comparison has to change too.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Trade-offs", and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for B12 (expected: position end of deck, body table 6x4,
notes_set yes, tracker Trade-offs highlighted).
