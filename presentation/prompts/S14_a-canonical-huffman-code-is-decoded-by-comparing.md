# Slide S14 (15 of 27)

Layout: "Title and body". Insert after slide S13.

Title (exact text, do not shorten or rephrase):

    A canonical Huffman code is decoded by comparing the next bits against one threshold per length

Body: Insert → Image → Upload from computer → `\\wsl.localhost\Ubuntu\home\yuvalk\HWSW\HWSW_Proj\presentation\assets\huffman_tree.png`.
Fit it inside the body box, keep aspect ratio, centre it. No caption, no border.

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    **Analyze**   ·   Profile   ·   Optimize   ·   Accelerate   ·   Trade-offs

Speaker notes (exact text, paste into the notes pane):

    With code lengths [2,2,2,3,3] the canonical codes are 00, 01, 10 for a, b, c and 110, 111 for d, e: codes of one length are consecutive integers, so each length has a limit and a base. Decode 01110: peek 01, emit b, consume two bits. Peek 11, above the length-2 range, so extend to 110 = 6, at or below limit[3] = 7; base[3] = 3, so perm[3] = d. Nothing is scanned. The original matcher visited about 5.0 entries per symbol out of 258, which is why the table alone was not the whole win.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Analyze", and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S14 (expected: position 15, body image huffman_tree.png,
notes_set yes, tracker Analyze highlighted).
