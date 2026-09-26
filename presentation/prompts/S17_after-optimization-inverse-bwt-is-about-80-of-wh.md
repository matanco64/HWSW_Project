# Slide S17 (18 of 27)

Layout: "Title and body". Insert after slide S16.

Title (exact text, do not shorten or rephrase):

    After optimization inverse BWT is about 80% of what remains; a Rust kernel for symbol decode reaches 170.01 ms, 6.61x end to end

Body: Insert → Image → Upload from computer → `\\wsl.localhost\Ubuntu\home\yuvalk\HWSW\HWSW_Proj\presentation\assets\print_pyflate_opt.png`.
Fit it inside the body box, keep aspect ratio, centre it. No caption, no border.

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   **Optimize**   ·   Accelerate   ·   Trade-offs

Speaker notes (exact text, paste into the notes pane):

    After the Python work the profile changes shape. From 122 samples, _decode_symbols_python, the loop that replaced the matcher, is 32.79% self; inverse BWT is 38.52% inclusive and rle4_expand 5.74%. The Rust/PyO3 BlockDecoder takes that symbol loop in one call per block; headers, inverse BWT, RLE4 and MD5 stay in Python. Under direct pyperf that is 283.88 ± 3.34 to 170.01 ± 2.30 ms, 1.67x; against the original, 6.61x and 84.9% less time. The kernel itself takes 3.304 ms per decode where the Python loop took about 117 ms. What remains is inverse BWT: 137.7 ms for the whole transform, about 80% of the remaining time; the traversal alone is 47.8 ms, never add the two. Caveat: a 32.79% share would cap the gain at 1.49x, below the measured 1.67x, so 122 samples locate work but do not calibrate Amdahl.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Optimize", and the notes are saved. Reply with a screenshot of
the slide in edit view.
