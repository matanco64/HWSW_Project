# Slide S13 (14 of 27)

Layout: "Title and body · Analyze" (Slide → Apply layout). Insert after slide S12.

Title (exact text, do not shorten or rephrase):

    pyflate is bzip2 decompression in pure Python: Huffman decode, move-to-front, run-length, inverse BWT

Body: insert the image `C:\Users\Kogan\HWSW_presentation\assets\pyflate_stages.png` with your direct upload tool.
Size it to fill the body box: width 9.2 in, or height 3.5 in if that binds first, keeping the
aspect ratio; place it at x = 0.4 in, y = 1.5 in and centre it horizontally in the body box.
It must not overlap the title or the footer tracker. No caption, no border, no crop.

Do not touch the footer tracker: the layout already highlights "Analyze".

Speaker notes (exact text, paste into the notes pane):

    Despite its name, the measured fixture is bzip2, not DEFLATE: interpreter.tar.bz2 expands from 67,562 bytes to 399,360 bytes, and the MD5 check sits outside the timer. One block, six Huffman tables, 148,271 symbols, with a table switch every 50 symbols. The symbol loop, which is the bit reader, Huffman decode, move-to-front and RUNA/RUNB expansion, produces the 336,184-byte L-vector, the last column of the BWT matrix. Inverse BWT and RLE4, where four equal bytes and a count k stand for 4 + k copies, produce the output. Only the standard library is used. Keep this boundary in mind: the Rust kernel and both accelerators take exactly the symbol loop and leave the rest in Python.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Analyze" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S13 (expected: position 14, body image pyflate_stages.png,
notes_set yes, tracker Analyze via layout).
