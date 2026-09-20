# For Matan — what changed in your report files, and two asks

Yuval applied the hardware reading-pass notes directly (2026-09-19). Rule followed: **only the
hardware section (§5), the Conclusion (§6) and the appendix's hardware paragraph were edited;
every software line is byte-identical** (checked by script against the pre-edit sources, in the
`.typ` and in the built `.txt`). `style.typ` and `report/fig/` are untouched.

See it: `git diff 54a738c -- report/*.typ` · built with `report/build.sh` (all table checks pass).

| File | What changed |
|---|---|
| `report_nbody.typ` §5 | `grape_pipeline` introduced (GRAPE lineage, why FP64); "how these numbers were produced"; one cost table (adds cells, coverage, ≈ 19 mW power); new "Does the hardware win?" with tier table + verdict; history sentences (11.15 → 19.46, run tag, date) removed |
| `report_pyflate.typ` §5 | both modules introduced + why two; huffman **39.9 MHz post-CTS** (was 8.9 pre-placement) and ≈ 283 mW; shared clock, no CDC; chain **simulated together** (159,303 cycles, byte-exact); comparison at the matched boundary (A3's 3.30 ms) instead of stock-based 1.97× / 1.15× / 2.7× projections, which are removed; "CAM" wording dropped |
| both §6 | Conclusions now state the hardware bottom line. Your software sentences are kept (nbody's second sentence gained the 9.53 ms / 24.3× figure) |
| `report_appendix.typ` | "Hardware evidence map" → own section **A8** (it was under the VM section but nothing in it ran on the VM); stale "pre-placement" sentence fixed; toolchain table added |
| Page counts | nbody 6 → 7, pyflate 7 → 8, appendix 5 → 6 (two forced page breaks inside §5 removed) |
| Elsewhere | `promts.txt` merged verbatim into `prompt.txt` (the brief names one file); README link updated; README hardware paragraph refreshed |

## Update 2026-09-20 — software-side items also applied (Yuval asked for them to be closed)

Two independent grader-style reads of §1–§4 (one per report) re-derived every number from
`results/` — **no arithmetic or transcription error was found** — and listed coverage / wording
gaps against the brief. Applied, all small and factual (`git diff 20e8080 -- report/*.typ`):

- **Headings carry the brief's section names** (Overview / Initial analysis / Optimizations /
  Performance comparison / Hardware acceleration proposal / Conclusion); numbering unchanged.
- **Brief coverage:** profilers named (py-spy; `perf record -F 999` on `python3-dbg` + FlameGraph);
  libraries and concrete data structures stated in both §1; a "Reading the flame graphs" paragraph in
  nbody (the `.txt` has no figures); "T3" defined in the pyflate ablation.
- **Provenance (please double-check these two):** pyflate §4 said *eleven* Rust crate tests passed on
  the VM — the canonical VM log (`results/vm_canonical_20260910_2c8c754/rust_tests.log`) shows **10**;
  the 11th (property test, `536ee64`) was added after the timed revision. And the "Measurement scope"
  note now says the later commits (comment trim, `collections.Counter` histogram, Rust code-length cap
  23 → 20) were **not re-timed**.
- **Wording:** "VM" spelled out; run-in labels end with ":"; IPC, BH, FMM, pyperf vs pyperformance
  glossed; cache-miss rates explained as medians of per-run rates; nbody table columns say
  "Optimized Python"; the pyflate 23.8 % cache-miss drop is flagged as capture-dependent (an earlier
  capture shows ≈ 2 %); "1.67× baseline is 283.88 ms, so 4.00 × 1.67 ≠ 6.61" stated.
- **Layout:** the forced `#pagebreak()`s that stranded a few lines on a new page were removed
  (pyflate: all five; nbody: one). Pages: nbody 7, pyflate 9, appendix 6. The brief sets no limit.
- **New in nbody §5:** "Would a larger N change the verdict?" — the hardware schedule model run for
  N bodies (`hw/grape_pipeline/docs/schedule_model_n.py`), compared with your §4 sweep.

Also applied: one name per configuration in pyflate ("Python + Rust extension" now appears in the
§4 table row and the counters header), the "T1 only" ablation row (+393.6 / +397.2 / +200.6 ms, from
the two VM logs and FINDINGS), and 24.26× used consistently in nbody.

## Asks

1. **Skim the diff** (`git diff 54a738c -- report/*.typ`, about 15 min), especially §5 / §6 and the two
   provenance corrections above, and tell Yuval anything you disagree with.

## Nothing else is left open on the report side

Tried and rejected: a global figure-spacing line in `style.typ` (it re-flows pyflate and adds a page);
nbody uses a local `#v(0.5em)` after its figures instead, pyflate keeps its original spacing.

Full rationale for every item is in git history: `git show 54a738c:report/REPORT_DELTAS.md`.
