# Slide S04 (5 of 27)

Layout: "Title and body · Optimize" (Slide → Apply layout). Insert after slide S03.

Title (exact text, do not shorten or rephrase):

    Specializing advance() to the fixed pair list removes the list traffic: 231.20 → 143.13 ms, 1.62x, bit-identical state

Body: insert the image `C:\Users\Kogan\HWSW_presentation\assets\print_nbody_opt_slide.png` with your direct upload tool.
Size it to fill the body box: width 9.2 in, or height 3.4 in if that binds first, keeping the
aspect ratio; place it at x = 0.4 in, y = 1.6 in and centre it horizontally in the body box.
It must not overlap the title or the footer tracker. No caption, no border, no crop.

Do not touch the footer tracker: the layout already highlights "Optimize".

Speaker notes (exact text, paste into the notes pane):

    At import time we emit an advance() with the pair loop unrolled, coordinates in locals and masses as literals; state is loaded before the step loop and written back afterwards, so energy still observes the original body objects. The arithmetic is untouched: mag = dt * (dsq ** -1.5) in the same order, so final state and energy compare exactly equal after 20,000 steps, not merely within a tolerance. Under pyperformance the run goes from 231.20 ± 7.85 to 143.13 ± 1.56 ms, 1.62x, 38.1% less time; the 88.1 ms reduction is about 70 times the clustered standard error. The optimized profile confirms the mechanism: list access and index conversion fall from 11.26% to 0.06% of self time, float handling does not fall, and advance() still holds 91.4% of 210 samples. That residue is what the native tier removes.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Optimize" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S04 (expected: position 5, body image print_nbody_opt_slide.png,
notes_set yes, tracker Optimize via layout).
