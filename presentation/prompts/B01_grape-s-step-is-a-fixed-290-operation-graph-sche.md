# Slide B01 (BACKUP)

Layout: "Title and body". Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    grape's step is a fixed 290-operation graph scheduled onto 3 adders and 3 multipliers

Body: Insert → Image → Upload from computer → `\\wsl.localhost\Ubuntu\home\yuvalk\HWSW\HWSW_Proj\presentation\assets\grape_uarch.png`.
Fit it inside the body box, keep aspect ratio, centre it. No caption, no border.

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   **Accelerate**   ·   Trade-offs

Speaker notes (exact text, paste into the notes pane):

    Datapath: pair i issues at cycle 2i into the shared units. Per pair, the front end subtracts the three coordinates, squares and sums them, takes the square root, multiplies to d3, takes the reciprocal, then forms the magnitude and the six force terms; every one of those is a Python-visible binary64 rounding held in its own register. Per step that is 125 adds, 145 multiplies, 10 square roots and 10 reciprocals, 290 operations, which a greedy list scheduler places on the units as a static reservation table checked by an SVA assertion. Control: the step FSM is IDLE, LATCH, RUN, COMMIT, DONE or ABORT; RUN ends when all 290 ops have retired and ABORT is sampled only at COMMIT. The accumulate sequencer keeps a 5-by-3 busy scoreboard per body component so velocity updates on one lane stay in program order. Timing budget: each pipeline stage was estimated at 8 ns or less against the 20 ns period, which is why the 50 MHz target looked comfortable on paper; the picker path that later set the clock was not in that table.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Accelerate", and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for B01 (expected: position end of deck, body image grape_uarch.png,
notes_set yes, tracker Accelerate highlighted).
