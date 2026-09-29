# Slide S08 (9 of 27)

Layout: "Title and body · Accelerate" (Slide → Apply layout). Insert after slide S07.

Title (exact text, do not shorten or rephrase):

    grape_pipeline computes full IEEE FP64 in the benchmark's own operation order, with 3 adders and 3 multipliers chosen by a cycle model

Body: insert the image `C:\Users\Kogan\HWSW_presentation\assets\grape_block_diagram.png` with your direct upload tool.
Size it to fill the body box: width 9.2 in, or height 3.4 in if that binds first, keeping the
aspect ratio; place it at x = 0.4 in, y = 1.6 in and centre it horizontally in the body box.
It must not overlap the title or the footer tracker. No caption, no border, no crop.

Do not touch the footer tracker: the layout already highlights "Accelerate".

Speaker notes (exact text, paste into the notes pane):

    Inputs and outputs: a 32-bit AXI4-Lite slave with a 12-bit address inside a 4 KB window, plus one interrupt. Through that window software writes FP64 body state as word pairs, DT, a 32-bit NSTEPS, and the pair list; it reads back state, counters and status. The register map is 15 rows. Inside, the datapath is our own FP64 units: three 3-stage adders, three 3-stage multipliers, one radix-4 SRT square root of about 30 cycles and one Newton reciprocal of about 22 cycles. Deliberately no FMA: the Python trajectory rounds after every multiply and every add, and fusing them would break bit-exactness against the emulation model. A step is a fixed 290-operation graph; the cycle model list-scheduled it onto candidate unit mixes and 3 add plus 3 mul was the smallest mix under the 128-cycle budget. Clock target 50 MHz.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Accelerate" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S08 (expected: position 9, body image grape_block_diagram.png,
notes_set yes, tracker Accelerate via layout).
