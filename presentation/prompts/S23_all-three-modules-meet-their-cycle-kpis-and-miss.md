# Slide S23 (23 of 26)

Layout: "Title and body". Insert after slide S22.

Title (exact text, do not shorten or rephrase):

    All three modules meet their cycle KPIs and miss 50 MHz; huffman_engine's area is 95 % tables in flip-flops, so SRAM would roughly halve it

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Metric | grape_pipeline | huffman_engine | mtf_cam |
|---|---:|---:|---:|
| Cells / area, plain Yosys sky130 | 584,454 / 4.075 mm² | 151,058 / 1.634 mm² | 18,814 / 0.187 mm² |
| Cycle KPI, measured vs bound | 124 /step ≤ 128 | 1.0068 /sym ≤ 1.10 | 1.0686 /sym ≤ 1.10 |
| Fmax, post-CTS STA (target 50 MHz) | 19.46 MHz | 39.9 MHz | 37.5 MHz |
| Power, default activity, indicative | ≈ 19.2 mW @ 150 ns | ≈ 283 mW @ 40 ns | ≈ 10.2 mW @ 27 ns |
| Directed + random tests | 9/9 | 17/17 | 16/16 |

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   Accelerate   ·   **Trade-offs**

Speaker notes (exact text, paste into the notes pane):

    Three modules at one evidence stage: every Fmax is post-CTS static timing from a run that met its constraint. Each module meets its cycle KPI: grape 124 cycles per step against 128, huffman 1.0068 per symbol against 1.10, mtf 1.0686 against 1.10. Each misses the 50 MHz target: 19.46, 39.9 and 37.5 MHz. huffman's 1.634 mm² misses the 1.0 mm² soft ceiling by 1.63×, a storage miss: symbol table and length window are ≈ 34 kbit of flip-flops, 95 % of the area, the decode cascade 1.3 %; SRAM macros project ≈ 0.75 mm² of standard cells, not synthesized in our flow. Power is a tool estimate at default activity on three different clocks: indicative, not comparable. One correction on record: huffman was first published at 25.1 MHz because a script read hold slack as setup; the setup report gives 39.9 MHz.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Trade-offs", and the notes are saved. Reply with a screenshot of
the slide in edit view.
