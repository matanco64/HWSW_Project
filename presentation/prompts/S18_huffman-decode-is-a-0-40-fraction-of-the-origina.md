# Slide S18 (18 of 26)

Layout: "Title and body". Insert after slide S17.

Title (exact text, do not shorten or rephrase):

    Huffman decode is a 0.40 fraction of the original run, a 1.67× ceiling alone, so we chain it with move-to-front on one AXI stream

Body: Insert → Image → Upload from computer → `\\wsl.localhost\Ubuntu\home\yuvalk\HWSW\HWSW_Proj\presentation\assets\decode_report.png`.
Fit it inside the body box, keep aspect ratio, centre it. No caption, no border.

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   **Accelerate**   ·   Trade-offs

Speaker notes (exact text, paste into the notes pane):

    On the VM py-spy profile, Huffman symbol decode plus its bit reader is f = 0.40 of the 1,123.49 ms original, so even an infinitely fast decoder caps at 1/(1 − 0.40) = 1.67×. Move-to-front is another 0.1344 and consumes exactly the decoder's 148,271 output symbols, so the two are chained on chip; that covers about half the run on this profile (the module doc's ≈ 0.63 and ≈ 2.7× ceiling summed the older cProfile Huffman share of 49.6 %). Who does what: the CPU parses each block header, writes the 6 × 147 code lengths and the used-byte map over AXI4-Lite, starts both modules, then runs inverse BWT, RLE4 and MD5. The hardware builds its tables, decodes, and hands each symbol to mtf_cam as one 32-bit AXI-Stream beat, value in TDATA[8:0], type in [11:9] (ADR-0006); platform DMA returns the L-vector.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Accelerate", and the notes are saved. Reply with a screenshot of
the slide in edit view.
