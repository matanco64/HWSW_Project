# Slide S12 (13 of 27)

Layout: "Title and body". Insert after slide S11.

Title (exact text, do not shorten or rephrase):

    What would beat Rust: the clock it takes, a wider unit mix, and a Rust host around the same hardware

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Projection (not a measurement) | Compute time | vs Rust 9.530 ms | What it assumes |
|---|---|---|---|
| Clock at which grape compute alone matches Rust | 2.48 Mcycles / 9.530 ms ≈ 260 MHz | parity | 13.4x the post-CTS clock; zero residual |
| grape at the 50 MHz target | 49.6 ms (+11.6 ms residual = 61.16 ms, 3.78x vs original) | 6.42x slower | timing closure we did not reach |
| 3 add + 4 mul, schedule model | 117 cycles/step → 120.2 ms at 19.46 MHz | 12.6x slower | model only; needs 245 MHz for parity |
| Rust host + same hardware at 19.46 MHz | 127.4 + 0.48 ms = 127.9 ms | 13.4x slower | residual scales to 5% of the Rust run |
| N = 100 with 24 add + 24 mul + 2 sqrt + 2 rcp | 0.029 µs/pair at 19.46 MHz | 1.6x faster | clock survives 8x wider issue; SRAM state |

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   Accelerate   ·   **Trade-offs**

Speaker notes (exact text, paste into the notes pane):

    Everything on this slide is a projection from the schedule model and the report's numbers; derivations.md holds the arithmetic. Clock: the datapath alone matches Rust at about 260 MHz, 13.4 times what post-CTS timing supports; at the 50 MHz target the system would still be 6.42x slower. Width: a fourth multiplier saves 6 cycles per step in the model, 123 to 117, because at N = 5 one pair's 80-cycle chain bounds the step. Host: swapping Python for Rust around the same device trims the residual from 11.6 ms to about 0.48 ms, an 8% change. Only more bodies change the verdict: at N = 100 the model needs 24 adders and 24 multipliers to run 1.6x faster than native, assuming the clock survives the wider issue logic, which our own 1-wide versus 3-wide data says it does not.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Trade-offs", and the notes are saved. Reply with a screenshot of
the slide in edit view.
