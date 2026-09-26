# Slide S16 (17 of 27)

Layout: "Title and body". Insert after slide S15.

Title (exact text, do not shorten or rephrase):

    Three optimizations, each measured by reverting it, take pyflate from 1,123.49 ms to 281.16 ms, 4.00x

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Reverted from the shipped decoder (T3) | VM trial 1 | VM trial 2 |
|---|---|---|
| None (full T3 runtime) | 271.2 ms | 273.9 ms |
| Regex-assisted RLE4 | +100.6 ms | +98.7 ms |
| Primary Huffman lookup | +52.6 ms | +49.4 ms |
| Counting-sort BWT | +20.8 ms | +17.2 ms |
| All reverted (T1 only) | +393.6 ms | +397.2 ms |

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   **Optimize**   ·   Accelerate   ·   Trade-offs

Speaker notes (exact text, paste into the notes pane):

    Three changes shipped on top of the per-byte fixes: a flat primary lookup table for Huffman codes with a canonical fallback, regex-assisted RLE4 so the run scan happens in C, and counting-sort construction of the BWT traversal table. To attribute the gain we revert one change at a time and time best-of-seven interleaved decompressions on the VM; the two trials agree within 4 ms on every row. RLE4 is worth about 100 ms, the lookup about 50 ms, the BWT sort about 20 ms. Costs need not add, and the development interpreter ranked them the other way round, so measure on the platform you report. End to end under pyperformance: 1,123.49 ± 10.99 to 281.16 ± 3.05 ms, 4.00x, 75.0% less time, byte-exact against bz2.decompress. The ablation drives the module directly, so its 271.2 ms is not 281.16 ms.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Optimize", and the notes are saved. Reply with a screenshot of
the slide in edit view.
