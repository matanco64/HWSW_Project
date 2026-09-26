# Slide S07 (8 of 27)

Layout: "Title and body". Insert after slide S06.

Title (exact text, do not shorten or rephrase):

    advance() is 95% of the remaining time, so the whole step goes on-chip after one doorbell

Body: Insert → Image → Upload from computer → `\\wsl.localhost\Ubuntu\home\yuvalk\HWSW\HWSW_Proj\presentation\assets\grape_report.png`.
Fit it inside the body box, keep aspect ratio, centre it. No caption, no border.

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   **Accelerate**   ·   Trade-offs

Speaker notes (exact text, paste into the notes pane):

    Amdahl first, hardware second. The profile says 95% of the original run is inside advance(), so f = 0.95 and the ceiling for any accelerator is 20x; at the 50 MHz design target the model gives 3.78x, which is why the PRD asked for at least 4x. The boundary follows from the loop shape: 20,000 serial steps over five bodies and ten pairs. If the host called the device once per step, the register traffic would dwarf the arithmetic, so software loads the body state and the pair list, rings one doorbell, and reads the state back after all 20,000 steps. That costs about 150 AXI-Lite transactions per run, under 0.03% of the compute. ADR-0001 therefore chose MMIO only: no DMA, no stream ports, because a few hundred bytes per invocation do not justify a DMA engine and its verification.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Accelerate", and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S07 (expected: position 8, body image grape_report.png,
notes_set yes, tracker Accelerate highlighted).
