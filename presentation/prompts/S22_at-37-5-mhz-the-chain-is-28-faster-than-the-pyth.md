# Slide S22 (23 of 27)

Layout: "Title and body". Insert after slide S21.

Title (exact text, do not shorten or rephrase):

    At 37.5 MHz the chain is 28× faster than the Python loop and 1.3× slower than the Rust kernel; end to end it is a 6.6× tie because inverse BWT sets the floor

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Stage implementation | Stage time | End-to-end path | End-to-end time | vs original |
|---|---:|---|---:|---:|
| — | — | Original Python | 1,123.49 ms | 1.00× |
| Optimized Python loop | ≈ 117 ms (derived) | Optimized Python | 281.16 ms | 4.00× |
| Rust kernel | 3.30 ms (measured) | Python + Rust kernel | 170.01 ms | 6.61× |
| HW chain @ 37.5 MHz, 159,303 cycles | ≈ 4.25 ms (projected) | Python + HW chain @ 37.5 MHz | ≈ 171 ms | ≈ 6.6× |
| HW chain @ 50 MHz target | ≈ 3.19 ms (projected) | Python + HW chain @ 50 MHz | ≈ 170 ms | ≈ 6.6× |

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   Accelerate   ·   **Trade-offs**

Speaker notes (exact text, paste into the notes pane):

    Same boundary as the Rust kernel: 148,271 symbols in, 336,184 bytes out. Hardware time is measured chain cycles over the post-CTS clock, 159,303 cycles at 37.5 MHz ≈ 4.25 ms; Rust's 3.30 ms is a phase-isolated VM measurement; the ≈ 117 ms Python loop is derived (283.88 − 170.01 + 3.30). So the chain replaces the interpreter loop ≈ 28× faster but is ≈ 1.3× slower than Rust at the achievable clock, parity at 50 MHz. End to end it lands at ≈ 171 ms, a tie with the delivered 170.01 ms: off the interpreter this stage is ≈ 2 % of what remains, and inverse BWT at 137.7 ms (≈ 80 %) sets the floor for both routes. Not in these rows: DMA and host-interface time T_if is unmeasured and can only add; the per-block bus cost is modelled at ≈ 628 cycles, streams overlapped by DMA.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Trade-offs", and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S22 (expected: position 23, body table 6x5,
notes_set yes, tracker Trade-offs highlighted).
