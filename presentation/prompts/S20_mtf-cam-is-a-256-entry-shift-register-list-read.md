# Slide S20 (21 of 27)

Layout: "Title and body". Insert after slide S19.

Title (exact text, do not shorten or rephrase):

    mtf_cam is a 256-entry shift-register list read by rank; width 8 sits at the knee of the area/cycle sweep

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| W (output bytes/beat) | Area | K3 model (cyc/sym) | K3 ≤ 1.10 | Verdict |
|---|---:|---:|---|---|
| 4 | 0.182 mm² | 1.175 | fails | rejected |
| 8 | 0.187 mm² | 1.063 | meets | chosen: the knee |
| 16 | 0.208 mm² | 1.023 | meets | +10.9 % area for 3.8 % fewer cycles, not needed |

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   **Accelerate**   ·   Trade-offs

Speaker notes (exact text, paste into the notes pane):

    Each bzip2 symbol is a rank into a 256-entry list of recently used bytes: emit that byte and move it to the front. Hardware: a 256 × 8 shift register with a 256:1 read mux; every entry is writable each cycle, so the move takes one cycle and needs no RAM (the "CAM" is the list; nothing is content-searched). Run groups expand through a W-byte packer; W is the knob: W = 4 breaks the K3 ≤ 1.10 KPI, W = 16 costs 10.9 % more area for 3.8 % fewer cycles, so W = 8 is the knee; the list is 68 % of the 0.187 mm². Measured: 158,441 cycles, K3 = 1.0686 against the 1.063 model. The uArch review caught that the cycle model enqueues two items in one cycle, so the item FIFO needed a 2-wide write port; with one port K3 lands near 1.30.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Accelerate", and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S20 (expected: position 21, body table 4x5,
notes_set yes, tracker Accelerate highlighted).
