# Slide B06 (BACKUP)

Layout: "Title and body". Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    Verification evidence per module: tests, line/toggle/branch coverage, formal, both simulators

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Evidence | grape_pipeline | huffman_engine | mtf_cam |
|---|---|---|---|
| Directed + random tests, Verilator and Icarus | 9/9 | 17/17 | 16/16 |
| Line / toggle coverage | 91.7% / 96.0% (all signals) | 90.4% / 90.3% (control subset) | 92.0% / 93.8% (control subset) |
| Branch coverage; functional bins hit | 94.8%; 59 | 91.7%; 34 | 96.8%; 129 |
| Golden equivalence on the real input | 20,000 steps, 0 mismatches | 148,271 beats trace-exact | 336,184 bytes byte-exact |
| Formal (SymbiYosys) | FSM arcs, BMC depth 40 + cover | 4 tasks: ctrl arcs, skid, aligner cap | 7 tasks; unbounded at 16 entries, bounded at 256 |

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   **Accelerate**   ·   Trade-offs

Speaker notes (exact text, paste into the notes pane):

    Every module runs its full directed plus constrained-random suite on Verilator and again on Icarus, the 4-state simulator that shows X after reset. The scoreboard oracle is the benchmark's own Python code, and each module is checked on the real benchmark input end to end: grape bit-exact over 20,000 steps, huffman trace-exact over 148,271 beats, mtf byte-exact over 336,184 bytes, and the huffman-to-mtf chain is co-simulated as well. Coverage carries a caveat: huffman and mtf toggle coverage is measured over the control-signal subset, because wide data buses whose upper bits the benchmark cannot toggle are waived with the width sweep as evidence; grape's is over all signals. Formal covers control properties only: grape's FSM arcs at BMC depth 40, huffman's four tasks, and mtf's list invariants, unbounded at 16 entries but only bounded at the production 256.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Accelerate", and the notes are saved. Reply with a screenshot of
the slide in edit view.
