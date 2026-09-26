# Slide S08 (9 of 27)

Layout: "Title and body". Insert after slide S07.

Title (exact text, do not shorten or rephrase):

    grape_pipeline computes full IEEE FP64 in the benchmark's own operation order, with 3 adders and 3 multipliers chosen by a cycle model

Body: Insert → Image → Upload from computer → `\\wsl.localhost\Ubuntu\home\yuvalk\HWSW\HWSW_Proj\presentation\assets\grape_block_diagram.png`.
Fit it inside the body box, keep aspect ratio, centre it. No caption, no border.

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   **Accelerate**   ·   Trade-offs

Speaker notes (exact text, paste into the notes pane):

    Inputs and outputs: a 32-bit AXI4-Lite slave with a 12-bit address inside a 4 KB window, plus one interrupt. Through that window software writes FP64 body state as word pairs, DT, a 32-bit NSTEPS, and the pair list; it reads back state, counters and status. The register map is 15 rows. Inside, the datapath is our own FP64 units: three 3-stage adders, three 3-stage multipliers, one radix-4 SRT square root of about 30 cycles and one Newton reciprocal of about 22 cycles. Deliberately no FMA: the Python trajectory rounds after every multiply and every add, and fusing them would break bit-exactness against the emulation model. A step is a fixed 290-operation graph; the cycle model list-scheduled it onto candidate unit mixes and 3 add plus 3 mul was the smallest mix under the 128-cycle budget. Clock target 50 MHz.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Accelerate", and the notes are saved. Reply with a screenshot of
the slide in edit view.
