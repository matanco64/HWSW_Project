# Slide S01 (2 of 27)

Layout: "Title and body". Insert after slide S00.

Title (exact text, do not shorten or rephrase):

    Two pure-Python pyperformance workloads, one question: where does the time go, and what would it take to move it to hardware?

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Tier | nbody | pyflate |
|---|---|---|
| Original Python (pyperformance) | 231.20 ms, 1.00x | 1,123.49 ms, 1.00x |
| Optimized Python (pyperformance) | 143.13 ms, 1.62x | 281.16 ms, 4.00x |
| Python + Rust (direct pyperf) | 9.530 ms, 24.26x vs original | 170.01 ms, 6.61x vs original |

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    **Analyze**   ·   Profile   ·   Optimize   ·   Accelerate   ·   Trade-offs

Speaker notes (exact text, paste into the notes pane):

    Both workloads ship in pyperformance and are pure Python: nbody integrates five bodies for 20,000 steps, pyflate decompresses a 67,562-byte bzip2 file into 399,360 bytes. The course question is where the time goes and what it would take to move that work into hardware. This table is the whole software result, measured on the course VM with 120 pyperf values per configuration, pinned to one guest CPU. Two routes produced it, with different denominators. Original versus optimized ran through pyperformance: 231.20 to 143.13 ms for nbody, 1.62x, and 1,123.49 to 281.16 ms for pyflate, 4.00x. The Rust tiers ran under direct pyperf against the same file's Python back end, so nbody's kernel ratio of 15.25x sits on a 145.30 ms denominator; against the original it is 24.26x. pyflate's Rust decoder reaches 170.01 ms, 6.61x. Every later slide names its denominator.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Analyze", and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S01 (expected: position 2, body table 4x3,
notes_set yes, tracker Analyze highlighted).
