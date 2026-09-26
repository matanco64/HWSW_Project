# Slide S19 (20 of 27)

Layout: "Title and body". Insert after slide S18.

Title (exact text, do not shorten or rephrase):

    huffman_engine decodes one symbol per cycle: a barrel shifter, 20 parallel comparators, and six preloaded table sets so a table switch costs zero cycles

Body: Insert → Image → Upload from computer → `\\wsl.localhost\Ubuntu\home\yuvalk\HWSW\HWSW_Proj\presentation\assets\huffman_block_diagram.png`.
Fit it inside the body box, keep aspect ratio, centre it. No caption, no border.

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   **Accelerate**   ·   Trade-offs

Speaker notes (exact text, paste into the notes pane):

    The only serial dependency is the recurrence: where symbol N+1 starts depends on symbol N's length. So that loop is one cycle: barrel-shift the 64-bit window, compare it against the first-code threshold of all 20 lengths in parallel, priority-encode the shortest match, consume; symbol-table lookup and beat emission pipeline behind the loop. bzip2 switches tables every 50 symbols, so six table register sets are preloaded and the switch is 0-cycle (ADR-0008). Inputs: a 32-bit compressed stream and an 8-bit selector stream; output: 32-bit beats with a 9-bit symbol; target 50 MHz. On the real block: 149,276 cycles for 148,271 symbols, K1 = 1.0068 against a budget of 1.10. The first full-shape run showed 1.5068, an almost-full gate that ignored the same-cycle pop, fixed in one line; un-gating DEFLATE at coverage then exposed an extra-bit-count latching bug the unit tests never reached.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Accelerate", and the notes are saved. Reply with a screenshot of
the slide in edit view.
