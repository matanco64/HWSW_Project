# Slide S12 (13 of 27)

Layout: "Title and body · Trade-offs" (Slide → Apply layout). Insert after slide S11.

Title (exact text, do not shorten or rephrase):

    What would beat Rust: the clock it takes, a wider unit mix, and a Rust host around the same hardware

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Projection | Result | vs Rust | Assumes |
|---|---|---|---|
| Clock for compute parity | ≈ 260 MHz | parity | 13.4x today's clock, no residual |
| At the 50 MHz target | 61.16 ms | 6.42x slower | timing closure |
| 3 add + 4 mul (model) | 117 cycles/step, 120.2 ms | 12.6x slower | model only |
| Rust host + same HW | 127.9 ms | 13.4x slower | residual 5% of the Rust run |
| N = 100, 24 add + 24 mul | 0.029 µs/pair | 1.6x faster | clock survives 8x issue |

Do not touch the footer tracker: the layout already highlights "Trade-offs".

Speaker notes (exact text, paste into the notes pane):

    Everything on this slide is a projection from the schedule model and the report's numbers; derivations.md holds the arithmetic. Clock: the datapath alone matches Rust at about 260 MHz, 13.4 times what post-CTS timing supports; at the 50 MHz target the system would still be 6.42x slower. Width: a fourth multiplier saves 6 cycles per step in the model, 123 to 117, because at N = 5 one pair's 80-cycle chain bounds the step. Host: swapping Python for Rust around the same device trims the residual from 11.6 ms to about 0.48 ms, an 8% change. Only more bodies change the verdict: at N = 100 the model needs 24 adders and 24 multipliers to run 1.6x faster than native, assuming the clock survives the wider issue logic, which our own 1-wide versus 3-wide data says it does not.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Trade-offs" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S12 (expected: position 13, body table 6x4,
notes_set yes, tracker Trade-offs via layout).
