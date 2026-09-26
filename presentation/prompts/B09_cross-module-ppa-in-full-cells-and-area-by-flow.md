# Slide B09 (BACKUP)

Layout: "Title and body". Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    Cross-module PPA in full: cells and area by flow, post-CTS Fmax, indicative power, tests and coverage, all at the same evidence stage

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Metric | grape_pipeline | huffman_engine | mtf_cam |
|---|---:|---:|---:|
| Cells, plain Yosys (sky130 HD) | 584,454 ‡ | 151,058 | 18,814 |
| Area, plain Yosys | 4.075 mm² ‡ | 1.634 mm² | 0.187 mm² |
| Cells / area, OpenLane synthesis of the final RTL | 446,932 / 4.66 mm² (5.65 mm² placed) | not rerun | not rerun |
| Fmax, post-CTS STA (target 50 MHz) | 19.46 MHz | 39.9 MHz | 37.5 MHz |
| Power, default activity, indicative | ≈ 19.2 mW @ 150 ns | ≈ 283 mW @ 40 ns | ≈ 10.2 mW @ 27 ns |
| Cycle KPI | 124 /step | 1.0068 /sym | 1.0686 /sym |
| Verification | grape_pipeline | huffman_engine | mtf_cam |
|---|---:|---:|---:|
| Directed + random tests | 9/9 | 17/17 | 16/16 |
| Line / toggle coverage | 91.7 % / 96.0 % | 90.4 % / 90.3 % † | 92.0 % / 93.8 % † |
| Branch coverage | 94.8 % | 91.7 % | 96.8 % |
| Functional bins, all hit | 59 | 34 | 129 |
| End-to-end estimate | ≈ 1.66× at 19.46 MHz | ≈ 6.6× as a chain; stage ≈ 28× vs the Python loop | same chain figure |

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   Accelerate   ·   **Trade-offs**

Speaker notes (exact text, paste into the notes pane):

    Two footnotes carry the honesty. ‡ grape's plain-Yosys figures predate the final issue-selection rewrite; the OpenLane row is the netlist the 19.46 MHz timing was measured on, and the two recipes are not comparable with each other, so the plain-Yosys row is the one comparable across the three modules. † huffman and mtf toggle coverage is measured over the control-signal subset (signals ≤ 4 bits wide), with the wide data buses waived by a documented width sweep; grape's is over all signals. All three Fmax values are post-CTS static timing, the same stage, so they are comparable on that axis; none completed routed GDS, so there is no die shot. Power uses default switching activity at each run's own constraint, so the three numbers are not comparable with each other and support no energy claim. Every module misses 50 MHz post-CTS (grape 2.6×, mtf 1.33×, huffman 1.25×); the documented follow-ups, pipelining the integrate-multiply path and the table build, are datapath changes deferred beyond the PPA stage.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Trade-offs", and the notes are saved. Reply with a screenshot of
the slide in edit view.
