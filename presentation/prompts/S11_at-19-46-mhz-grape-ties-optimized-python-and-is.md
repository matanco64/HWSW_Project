# Slide S11 (11 of 26)

Layout: "Title and body". Insert after slide S10.

Title (exact text, do not shorten or rephrase):

    At 19.46 MHz grape ties optimized Python and is about 15x slower than Rust

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Tier | Time / run | vs original | Evidence |
|---|---|---|---|
| Original Python | 231.20 ms | 1.00x | measured, course VM |
| Optimized Python | 143.13 ms | 1.62x | measured, course VM |
| grape @ 19.46 MHz | ≈ 139 ms = 127.4 ms compute + 11.6 ms residual | ≈ 1.66x | projected |
| Native Rust | 9.530 ms | 24.26x | measured, course VM |

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   Accelerate   ·   **Trade-offs**

Speaker notes (exact text, paste into the notes pane):

    This is the honest result. Compute is 2.48 million measured RTL cycles divided by the 19.46 MHz post-CTS clock, 127.4 ms. We add an assumed 5% Python residual for the harness and the two energy evaluations, 11.6 ms; nobody has measured that residual, and no software has ever called this hardware, so the interface time is unmeasured and can only make the row slower. The projection lands at about 139 ms: 1.66x over the original, a tie with optimized Python at 1.03x, and about 15x slower than the 9.53 ms Rust tier. Per step that is 124 cycles or 6.4 µs against 0.48 µs natively. The cause is the clock, not the interface; the residual alone already exceeds the whole Rust run.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Trade-offs", and the notes are saved. Reply with a screenshot of
the slide in edit view.
