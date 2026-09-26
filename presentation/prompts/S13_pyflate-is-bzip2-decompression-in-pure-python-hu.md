# Slide S13 (13 of 26)

Layout: "Title and body". Insert after slide S12.

Title (exact text, do not shorten or rephrase):

    pyflate is bzip2 decompression in pure Python: Huffman decode, move-to-front, run-length, inverse BWT

Body: Insert → Image → Upload from computer → `\\wsl.localhost\Ubuntu\home\yuvalk\HWSW\HWSW_Proj\presentation\assets\pyflate_stages.png`.
Fit it inside the body box, keep aspect ratio, centre it. No caption, no border.

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    **Analyze**   ·   Profile   ·   Optimize   ·   Accelerate   ·   Trade-offs

Speaker notes (exact text, paste into the notes pane):

    Despite its name, the measured fixture is bzip2, not DEFLATE: interpreter.tar.bz2 expands from 67,562 bytes to 399,360 bytes, and the MD5 check sits outside the timer. One block, six Huffman tables, 148,271 symbols, with a table switch every 50 symbols. The symbol loop, which is the bit reader, Huffman decode, move-to-front and RUNA/RUNB expansion, produces the 336,184-byte L-vector, the last column of the BWT matrix. Inverse BWT and RLE4, where four equal bytes and a count k stand for 4 + k copies, produce the output. Only the standard library is used. Keep this boundary in mind: the Rust kernel and both accelerators take exactly the symbol loop and leave the rest in Python.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Analyze", and the notes are saved. Reply with a screenshot of
the slide in edit view.
