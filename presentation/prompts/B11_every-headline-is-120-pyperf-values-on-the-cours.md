# Slide B11 (BACKUP)

Layout: "Title and body". Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    Every headline is 120 pyperf values on the course VM, and the ± is spread, not a confidence interval

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Item | What it is | Value |
|---|---|---|
| Route A: pyperformance run, rigorous | original vs optimized, same benchmark name | 231.20 → 143.13 ms; 1,123.49 → 281.16 ms |
| Route B: direct pyperf | Python back end vs Rust of the same file, HWSW_BACKEND the only change | 145.30 → 9.530 ms; 283.88 → 170.01 ms |
| Values per JSON | 40 worker processes, three values each | 120 values, pinned to guest CPU 0 |
| ± in every table | sample standard deviation, not a confidence interval | effective n 40.2 and 41.8 for nbody original and optimized |
| Timed revision | 2c8c754, the canonical run | later commits pass the same oracles but were not re-timed |
| Hash names under results/ | pre-rewrite ids, kept as the historical record | 2c8c754 is 69b6bd5 after the rewrite |

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   **Optimize**   ·   Accelerate   ·   Trade-offs

Speaker notes (exact text, paste into the notes pane):

    Every headline came from the course VM, Ubuntu 22.04, release CPython, pyperf in rigorous mode, every timed run pinned to guest CPU 0, from one canonical run of revision 2c8c754. Two routes. Original versus optimized goes through pyperformance, which builds its own environment and therefore cannot see our wheel; Python back end versus Rust runs the same benchmark file directly under pyperf with only HWSW_BACKEND changed, and native mode fails rather than falls back. Each JSON holds 120 values, 40 worker processes times three values, and the ± is the sample standard deviation across them, not a confidence interval. Values from one worker are correlated: the intraclass correlation is 0.994 for the nbody original, so the effective sample size is about 40.2 and 41.8 for nbody's original and optimized runs. The reductions are still tens of standard errors. Commits after the timed revision were not re-timed: nbody removed a dead store from the generated advance() and widened the optional-import fallback; pyflate trimmed comments, moved the BWT histogram to collections.Counter and lowered the Rust code-length cap from 23 to 20. All pass the same exactness oracles, and results/vm_verify_20260921_f407567 re-ran the correctness checks on the VM at the submitted revision. Directory names under results/ keep the pre-rewrite commit ids: 2c8c754 is 69b6bd5 after the history rewrite, and the mapping is in docs/history-rewrite.md.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Optimize", and the notes are saved. Reply with a screenshot of
the slide in edit view.
