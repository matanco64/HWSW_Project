# Slide S06 (7 of 27)

Layout: "Title and body". Insert after slide S05.

Title (exact text, do not shorten or rephrase):

    Native runs 26.7x fewer instructions while IPC drops from 3.28 to 1.83: the win is instruction count, not the pipeline

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Per iteration | Optimized Python | Native Rust | Ratio |
|---|---|---|---|
| Elapsed time | 141.08 ms | 9.462 ms | |
| Instructions | 1,103.62 M | 41.32 M | 26.7x fewer |
| Cycles | 336.24 M | 22.55 M | 14.9x fewer |
| IPC | 3.28 | 1.83 | lower |
| Branches | 185.97 M | 3.92 M | |

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   **Optimize**   ·   Accelerate   ·   Trade-offs

Speaker notes (exact text, paste into the notes pane):

    This is a separate pinned warm-loop experiment, 64 iterations per run, medians of three runs, user-mode counters only. Native retires 26.7x fewer instructions and 14.9x fewer cycles, yet its IPC falls from 3.28 to 1.83. That is not a contradiction: runtime is cycles over clock, and IPC counts retired instructions, not useful force updates. Interpreter bookkeeping pipelines beautifully and is still work. Cache misses are 59.6 against 2.5 per iteration, far too few to matter. So nbody's cost was instruction count from the interpreter, not the memory system and not the pipeline, which is the fact the hardware half has to live with: there is no memory stall for an accelerator to hide.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Optimize", and the notes are saved. Reply with a screenshot of
the slide in edit view.
