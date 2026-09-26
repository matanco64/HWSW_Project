# Slide B04 (BACKUP)

Layout: "Title and body". Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    huffman_engine's area is storage: 1.634 mm² as built in flip-flops, ≈ 0.75 mm² projected with SRAM macros, and two table sets would save area but break K1

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Design point | Area | K1 cyc/sym | 1.0 mm² soft ceiling | Verdict |
|---|---:|---:|---|---|
| As built: flop symtab + 6 table register sets | 1.634 mm² (measured) | 1.0068 | miss (1.63×) | signed off, 0-cycle switch |
| Symtab 17.3 kbit + length window 8.6 kbit in SRAM macros | ≈ 0.75 mm² std cells + 2 macros (projected) | 1.0068 | meets | not synthesized: no SRAM compiler in the open sky130 HD flow |
| 2 table register sets, re-derive on each switch | ≈ 1.53 mm² (projected) | > 1.1 | miss | rejected: breaks K1 and the 0-cycle switch |
| RTL-review must | Symptom | Fix |
|---|---|---|
| R1 output-skid overflow | three cycles of back-pressure silently drop a symbol beat | issue gate counts the in-flight C1 beat |
| R2 PREP exit misses the build_done pulse | BUSY forever, no error; the real multi-block flow hangs by block 2–3 | build_done became a level |
| R3 symbol 0 issues before the first selector pop | silent bzip2 corruption from a stale table selector | sel_stall holds C0 until the first selector applies |

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   Accelerate   ·   **Trade-offs**

Speaker notes (exact text, paste into the notes pane):

    The decode datapath is 1.3 % of the design and carries no sequential area; huff_tables plus huff_regs are 95 %. That is the whole area story, so the only real lever is where the tables live. As built they are flip-flops, which is why the 1.0 mm² soft ceiling is missed by 1.63×. Moving the two large single-port arrays into SRAM macros projects ≈ 0.75 mm² of standard cells plus two macros, but no SRAM compiler exists in our open sky130 flow, so it is a projection. Cutting the six table sets to two would save only ≈ 0.1 mm² and re-derive tables at every 50-symbol switch, pushing K1 past 1.1; rejected. The second table is what the agent pre-review found before any simulation: 13 musts in the first RTL pass, the three above being the ones a testbench would have found last, because each needs back-pressure, a second block, or a first-symbol corner. All 13 were fixed and 36/36 unit and smoke tests passed on the fixed RTL.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Trade-offs", and the notes are saved. Reply with a screenshot of
the slide in edit view.
