# Slide S03 (3 of 26)

Layout: "Title and body". Insert after slide S02.

Title (exact text, do not shorten or rephrase):

    97.7% of samples sit in advance(); list indexing and float boxing dominate the C frames

Body: Insert → Image → Upload from computer → `\\wsl.localhost\Ubuntu\home\yuvalk\HWSW\HWSW_Proj\presentation\assets\print_nbody_stock.png`.
Fit it inside the body box, keep aspect ratio, centre it. No caption, no border.

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   **Profile**   ·   Optimize   ·   Accelerate   ·   Trade-offs

Speaker notes (exact text, paste into the notes pane):

    Two profilers, two views. py-spy on release CPython puts 97.7% of 310 samples in advance(); everything else is start-up and imports. perf at 999 Hz on the debug build shows what the interpreter does inside it: one tower under _PyEval_EvalFrameDefault at 99.31% inclusive, with binary_op1, the generic arithmetic dispatch, at 20.07%, float object handling at 16.25% of self time and list access and index conversion at 11.26%. There is no second hotspot. The list traffic is the part pure Python can remove: the per-pair unpacking and the read-modify-write of each velocity list. The float boxing it cannot remove, because every operation still allocates a Python float. Debug-build percentages locate the costs; release-build timing establishes the benefit.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Profile", and the notes are saved. Reply with a screenshot of
the slide in edit view.
