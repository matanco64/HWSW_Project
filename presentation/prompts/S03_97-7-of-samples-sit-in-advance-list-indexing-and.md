# Slide S03 (4 of 27)

Layout: "Title and body · Profile" (Slide → Apply layout). Insert after slide S02.

Title (exact text, do not shorten or rephrase):

    97.7% of samples sit in advance(); list indexing and float boxing dominate the C frames

Body: insert the image `C:\Users\Kogan\HWSW_presentation\assets\print_nbody_stock_slide.png` with your direct upload tool.
Size it to fill the body box: width 9.2 in, or height 3.4 in if that binds first, keeping the
aspect ratio; place it at x = 0.4 in, y = 1.6 in and centre it horizontally in the body box.
It must not overlap the title or the footer tracker. No caption, no border, no crop.

Do not touch the footer tracker: the layout already highlights "Profile".

Speaker notes (exact text, paste into the notes pane):

    Two profilers, two views. py-spy on release CPython puts 97.7% of 310 samples in advance(); everything else is start-up and imports. perf at 999 Hz on the debug build shows what the interpreter does inside it: one tower under _PyEval_EvalFrameDefault at 99.31% inclusive, with binary_op1, the generic arithmetic dispatch, at 20.07%, float object handling at 16.25% of self time and list access and index conversion at 11.26%. There is no second hotspot. The list traffic is the part pure Python can remove: the per-pair unpacking and the read-modify-write of each velocity list. The float boxing it cannot remove, because every operation still allocates a Python float. Debug-build percentages locate the costs; release-build timing establishes the benefit.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Profile" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S03 (expected: position 4, body image print_nbody_stock_slide.png,
notes_set yes, tracker Profile via layout).
