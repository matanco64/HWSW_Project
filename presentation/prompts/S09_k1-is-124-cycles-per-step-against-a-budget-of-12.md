# Slide S09 (10 of 27)

Layout: "Title and body". Insert after slide S08.

Title (exact text, do not shorten or rephrase):

    K1 is 124 cycles per step against a budget of 128, found only after the full-shape test exposed 162

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Design point | Cells (Yosys) | Area | K1 cycles/step | Verdict |
|---|---|---|---|---|
| 1-wide accumulate, 1-port RF | 393,367 | 2.938 mm² | 162 | fails K1 ≤ 128 |
| 3-wide accumulate, 3-port RF | 584,454 | 4.075 mm² | 124 | chosen: +38.7% area, −23.5% cycles |

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   **Accelerate**   ·   Trade-offs

Speaker notes (exact text, paste into the notes pane):

    The uArch model predicted 123 cycles per step, and the bring-up smoke test measured 126, so every gate was green until sign-off. The sign-off test runs the real workload, all ten pairs for 20,000 steps, and there K1 was 162: the smoke test used only two pairs, a shape in which the static schedule hides the accumulate phase, and the RTL had implemented the ordered velocity accumulate as single-issue. Widening it to three ops per cycle, with a per-lane integrate and a 3-port body register file, brought K1 to 124, inside the model's 123 to 127 window. Both design points are fully synthesized, so the trade-off is measured: 38.7% more area for 23.5% fewer cycles. Renegotiating K1 to 162 was offered and declined at the sign-off checkpoint.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Accelerate", and the notes are saved. Reply with a screenshot of
the slide in edit view.
