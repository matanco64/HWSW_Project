# Report deltas — status

The reading-pass findings (C4, B1–B3, R1–R22) and what happened to each. Applied by Yuval on
2026-09-19 under the rule *hardware section + Conclusion + appendix hardware paragraph only;
software text never touched*. The full rationale and suggested wording for every item is the
previous revision of this file: `git show 54a738c:report/REPORT_DELTAS.md`.

| Item | What | Status | Where |
|---|---|---|---|
| C4 | huffman 8.9 MHz pre-placement → **39.9 MHz post-CTS**, power ≈ 283 mW, all three post-CTS | applied | pyflate §5 cost table + "Evidence levels" |
| R1 | `grape_pipeline` never introduced | applied | nbody §5 opening |
| R5 | nbody power row wrong ("no power result") | applied | nbody §5 cost table (≈ 19 mW) |
| R8 | nbody has no bottom line | applied | nbody §5 "Does the hardware win?" |
| R9 | `huffman_engine` / `mtf_cam` never explained; "CAM" misleading | applied | pyflate §5 opening; "CAM" → "move-to-front list" |
| R11 | pyflate bottom line against the wrong baseline | applied | pyflate §5 "Does the hardware win?" (two tables + verdict) |
| R12 (+R6) | hardware workflow / sky130 / Yosys / OpenLane never explained | applied | "How these numbers were produced" in both §5 |
| R14 | stale appendix sentence (huffman pre-placement) | applied | appendix A8 |
| R15 | chain clocking undecided; "never simulated together" | applied | pyflate §5 clocking + "How it was tested" (159,303 cycles) |
| R18 | Conclusions silent on hardware | applied | both §6 |
| R4 | run tag and date in a table cell | applied | nbody §5 (removed) |
| R7 | history vs final design | applied | nbody §5 (11.15 → 19.46 narrative removed; area hedge kept, one sentence) |
| R10 | why two modules | applied | pyflate §5 |
| R13 | nbody cost table | applied | nbody §5 |
| R16 | formula undefined; three stock-based paragraphs | applied | both §5; the three paragraphs deleted |
| R21 | hardware evidence filed under the VM section | applied | appendix A8 |
| R22 | toolchain table | applied | appendix A8 |
| B1 | grape cell count | applied | nbody §5 cost table |
| B3 | mtf formal understated | applied | pyflate §5 "Evidence levels" |
| R3 | run-in labels end with "." | applied everywhere (2026-09-20) | labels only; bold full sentences keep their period |
| R2 | global figure spacing in `style.typ` | **declined** | it re-flows a software page in pyflate (+1 page); §5 uses local spacing instead |
| R20 | "VM" never spelled out | applied (2026-09-20) | first use in all three documents; A7 retitled |
| R17 | math audit | no action | the audited paragraphs were replaced; the new figures are re-derived in `hw/docs/hardware_report.md` |
| R19 | appendix is optional | no action | rule kept: nothing needed to follow §5 lives only in the appendix |
| B2 | 3.8 % vs 3.9 % | retracted | the report was right; `hw/mtf_cam/docs/ppa.md` fixed |
| A, D, E | consistent items, caveats to keep, README | no action / done | caveats kept in the new text |

Later hardware results folded in: huffman 27 ns confirmation run meets timing (39.5 MHz,
`hw/huffman_engine/synth/evidence/tight27_*`).

## 2026-09-20 — software-side pass (on Matan's behalf, at Yuval's request)

| Item | What | Status |
|---|---|---|
| S1 | section headings use the brief's names | applied, both reports |
| S2 | grader read of nbody §1–§4 (B1m): numbers all re-derived OK; 12 coverage/wording items | 11 applied; 24.26× vs 24.3× left |
| S3 | grader read of pyflate §1–§4 (B2m): numbers all re-derived OK; 10 items, 2 provenance | applied except naming unification and the extra "T1 only" ablation row |
| S4 | "T3" undefined | applied (development-ladder definition) |
| S5 | forced page breaks stranding text after the additions | removed; nbody 7 pages, pyflate 9 |
| S6 | larger-N hardware projection (Yuval's question) | new nbody §5 subsection + `schedule_model_n.py` |
