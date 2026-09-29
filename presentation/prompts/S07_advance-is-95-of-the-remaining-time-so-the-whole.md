# Slide S07 (8 of 27)

Layout: "Title and body · Accelerate" (Slide → Apply layout). Insert after slide S06.

Title (exact text, do not shorten or rephrase):

    advance() is 95% of the remaining time, so the whole step goes on-chip after one doorbell

Body: insert the image `C:\Users\Kogan\HWSW_presentation\assets\grape_report.png` with your direct upload tool.
Size it to fill the body box: width 9.2 in, or height 3.4 in if that binds first, keeping the
aspect ratio; place it at x = 0.4 in, y = 1.6 in and centre it horizontally in the body box.
It must not overlap the title or the footer tracker. No caption, no border, no crop.

Do not touch the footer tracker: the layout already highlights "Accelerate".

Speaker notes (exact text, paste into the notes pane):

    Amdahl first, hardware second. The profile says 95% of the original run is inside advance(), so f = 0.95 and the ceiling for any accelerator is 20x; at the 50 MHz design target the model gives 3.78x, which is why the PRD asked for at least 4x. The boundary follows from the loop shape: 20,000 serial steps over five bodies and ten pairs. If the host called the device once per step, the register traffic would dwarf the arithmetic, so software loads the body state and the pair list, rings one doorbell, and reads the state back after all 20,000 steps. That costs about 150 AXI-Lite transactions per run, under 0.03% of the compute. ADR-0001 therefore chose MMIO only: no DMA, no stream ports, because a few hundred bytes per invocation do not justify a DMA engine and its verification.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Accelerate" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S07 (expected: position 8, body image grape_report.png,
notes_set yes, tracker Accelerate via layout).
