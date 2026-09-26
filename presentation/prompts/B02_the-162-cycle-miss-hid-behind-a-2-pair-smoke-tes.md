# Slide B02 (BACKUP)

Layout: "Title and body". Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    The 162-cycle miss hid behind a 2-pair smoke test; the full-shape test at sign-off found it

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Stage | Workload | K1 cycles/step | Result |
|---|---|---|---|
| uArch schedule model | 290-op graph, nominal / worst corner | 123 / 127 | within 128 |
| DV bring-up smoke | 2 pairs, 2 steps | 126 | within 128, gate green |
| DV sign-off, full benchmark | 10 pairs, 20,000 steps | 162 | fails 128 |
| After 3-wide accumulate + per-lane integrate | 10 pairs, 20,000 steps | 124 | passes; smoke fell to 111 |

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   **Accelerate**   ·   Trade-offs

Speaker notes (exact text, paste into the notes pane):

    The model said 123, the smoke test said 126, and both were honest; the smoke shape simply could not show the problem. With two pairs the static force schedule dominates and the accumulate phase is hidden; with ten pairs the single-issue accumulate and the globally gated integrate serialized, and the real benchmark measured 162. The fix, widening the accumulate to three issues per cycle and letting each lane integrate as soon as its own chain retires, landed at 124, and the same smoke test then read 111. The lesson written into the flow: measure the KPI on the full-shape workload at bring-up, not only on the tiny smoke; the gap was visible one stage earlier to anyone who ran ten pairs. The huffman module paid that rule back on its first full-shape run.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Accelerate", and the notes are saved. Reply with a screenshot of
the slide in edit view.
