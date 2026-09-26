# Presentation strategy

Course brief §9: 20–25 min talk, then 5–10 min of questions, at a slot the staff schedule.
Audience: course staff, addressed as a fellow ECE student who did not do the project.

**Date:** Monday 6 October 2026, in person, presented from Yuval's laptop (WSL has the simulator for Q&A).
**Speakers:** Matan (software half), Yuval (hardware half).
**Deck:** Google Slides, built by a Claude desktop agent from `prompts/`, verified against
`deck.md` slide by slide. The repo is the source of truth; the Slides file is the output.

## The one sentence

> Every number on these slides has a measured source, and we say which ones are projections.

Most groups show speedup numbers. We show speedup numbers *with their denominators and their
evidence level*, including the accelerator that did not beat the Rust kernel. Honesty is the
differentiator, not decoration.

## Decisions (settled 2026-09-26, do not re-open without both speakers)

| Decision | Choice |
|---|---|
| Pattern | Assertion-evidence: each slide title is a full-sentence claim; the body is one figure or one table; no bullet lists; the words live in speaker notes. |
| Look | Google Slides default theme, one accent colour, one font pair, no animations. A thin footer tracker on every slide: `Analyze → Profile → Optimize → Accelerate → Trade-offs`, current stage highlighted. |
| Structure | Interleaved per benchmark: open → nbody SW → nbody HW → pyflate SW → pyflate HW → how we worked / limits → close. The mic changes hands three times. |
| HW depth | grape_pipeline (nbody) and huffman_engine (pyflate) told properly. mtf_cam appears as the pyflate chain partner on one slide; full detail in backup. |
| Honesty on stage | The nbody HW result slide says it: grape at 19.46 MHz ties optimized Python and is ~15x slower than Rust, with the cause and the fix. It is followed by a projection slide: what would beat Rust (clock needed, wider unit mix from the schedule model, Rust host + HW vs Python host + HW). Same candour for the three 50 MHz misses and the pyflate chain's ~6.6x tie with Rust. |
| Demo | Embedded ~20 s clip of the huffman→mtf chain co-simulation (`make -C hw/pyflate_accel sim`, byte-exact on the real input). A terminal stays open behind the slides for Q&A: nbody before/after run, grape driver co-sim, the chain sim. No live demo inside the talk. |
| SW slides | Drafted in full from the reports, owner `M`, status `DRAFT`, every number cited to `file:line`. Matan confirms or replaces; he never starts from blank. |
| Language | English slides. |
| Location | `presentation/` on `main`, committed after the submission. |
| Build cadence | Setup prompts one at a time, each verified; slides in batches of five with one verification pass per batch. |
| Screenshots | The desktop agent's screenshot for each prompt is saved by Yuval to `presentation/verify/<id>.png` (Windows path `\\wsl.localhost\Ubuntu\home\yuvalk\HWSW\HWSW_Proj\presentation\verify`); the verifier logs the verdict in `verify/README.md`. |
| Notes pass | Build first; Yuval refines the hardware speaker notes afterwards in `deck_parts/hw_*.md`, then the affected prompts are re-issued. |

## What we will NOT talk about in the main flow

Each of these gets at most one backup slide and is answered only if asked:

- DV methodology detail: pyuvm structure, coverage percentages, formal engines and depths.
- The OpenLane out-of-memory and routing saga.
- The retired MDP benchmark.
- Prompt-log mechanics and the AI-tooling setup (one backup slide on how AI was used).
- Repo hygiene, the history rewrite, the submission packaging.
- The external rehearsal reviews.
- Barnes-Hut and the large-N sweep beyond one sentence.
- Timing-statistics methodology (pyperf route, workers, what ± means).

Two things that look like process but stay in the main flow, one slide each: **how we worked**
(10 stages, 4 human checkpoints, 136 gate criteria, about 350 review findings (126 must); agents pre-review,
humans decide) and **limits** (evidence levels, what is projected, what is unmeasured).

## Time budget (target 22:30, hard cap 25:00)

| Segment | Owner | Seconds |
|---|---|---|
| Open: two workloads, one question, the canonical runtimes table | M | 90 |
| nbody SW: 10 pairs, flame graph, specialization 1.62x, tiers, counters | M | 270 |
| nbody HW: boundary + Amdahl, grape, K1, PPA, result vs Rust, projection | Y | 270 |
| pyflate SW: bzip2 pipeline, Huffman example, flame graph, ablation, Rust kernel | M | 300 |
| pyflate HW: Amdahl + chain, huffman_engine, mtf_cam, clip, chain result, trade-offs | Y | 300 |
| How we worked + limits | Y | 60 |
| Close: what we learned, the next experiment | M+Y | 60 |
| **Total** | | **1350 = 22:30** |

Buffer to the 25:00 cap: 150 s. If a rehearsal runs long, cut S06 (counters) and S17 (Huffman
worked example) first; they are teaching aids, not claims.

## Criticisms we pre-empt on purpose (from the two rehearsal reviews)

grape loses to Rust · the accelerators target a stage software already made cheap · 19.46 MHz
is an extrapolation · two profilers give two denominators · profile percentages are from sparse
samples · no software ever calls the hardware, interface time unmeasured · timed revision ≠
submitted revision · "what did you decide versus the agent?"

## Step ladder with definition of done

| # | Step | Output | Done when |
|---|---|---|---|
| 1 | Strategy | `STRATEGY.md` | Both speakers agree; cut list and time budget written; date filled in. |
| 2 | Storyboard | `storyboard.md` | Seconds sum ≤ 1380; every brief §7 bullet (HW description, I/O, architecture, HW/SW interface, justification, block diagram, PPA trade-offs) and each §1–§6 flow item maps to ≥1 slide; every slide has an owner; the projection slide exists. |
| 3 | Spec | `deck.md` | `tools/presentation/check_numbers.py` exits 0; every `visual` names a file that will exist in `assets/`; one visual per slide; every SW slide is `DRAFT`/`M`; the limits slide covers every `hardware_report.md` §5 disclosure the talk touches; `report/defense_guide.md` has no stale number. |
| 4 | Assets | `assets/*.png`, clip | Every file named in `deck.md` exists, opens, and is legible at projector size (each viewed once); the clip plays and is ≤ 25 s. |
| 5 | Build | Slides file, `verify/` | Setup prompts done (theme, footer tracker, image import); for every slide the Drive text-layer diff against `deck.md` is clean and the screenshot is approved; both recorded in `verify/`; deviations fixed by re-issuing the prompt, never by editing the spec to match. |
| 6 | Matan pass | `deck.md` statuses | No slide left in `DRAFT`; any replaced number re-passes `check_numbers.py`. |
| 7 | Rehearsal | `qa.md`, this file | One timed run ≤ 23:00 recorded below; every question in `qa.md` has an owner and an answer path; the terminal demo tested from a cold shell; Phase P in `report/CLOSEOUT.md` ticked. |

## Spec format (`deck.md`)

One section per slide. `check_numbers.py` and `gen_prompts.py` parse exactly this shape.

```
## S07 · advance() is 95% of the remaining time, so the whole step goes on-chip
- owner: Y
- status: DRAFT
- stage: Accelerate
- seconds: 45
- visual: assets/grape_report.png
- answers: G4, Q20            (backup slides only; question ids from qa.md)
- exempt: 5, 10               (small integers deliberately unsourced)

table:
| Tier | Time | Speedup |
|---|---|---|
| ... | ... | ... |

notes:
Speaker notes, plain prose. Every significant number here or in the title
must appear in a sources line below.

sources:
- 95% → hw/docs/hardware_report.md:118
- 143.13 → report_nbody.txt:161
```

Rules the checker enforces: every number with a decimal point, or ≥ 100, or carrying a unit
(x, %, ms, MHz, mm², mW, cycles, bytes, samples, cells) that appears in the title, table or
notes must be quoted in a `sources` line, and each quoted fragment must actually appear at the
cited line(s) of the cited file.

## Desktop-agent contract

Three setup prompts (`prompts/00a_theme.md`, `00b_footer.md`, `00c_images.md`), then one prompt per
slide, generated by `tools/presentation/gen_prompts.py` from `deck.md`. Each prompt carries the
exact title, the visual filename under `presentation/assets/` (reachable from Windows through
WSL), the exact speaker notes, and a "done when" line ending in "reply with a screenshot".
Verification per slide: the Drive connector reads the deck back; the title and notes must appear
verbatim; the screenshot must show the visual without overflow. Results go to `verify/`.

## Schedule to 6 October

| When | What | Who |
|---|---|---|
| Sat 27 Sep | Matan reads STRATEGY + his 13 slides; dry run of setup prompt 00a on the desktop agent | M, Y |
| Sun 28 – Mon 29 Sep | Build session 1: setup 00a–00c verified, slides S00–S12 in batches of five | Y + verifier |
| Tue 30 Sep – Wed 1 Oct | Build session 2: S13–S26, backup B01–B12; Matan's edits to SW slides applied and re-issued | Y, M |
| Thu 2 Oct | Yuval's notes pass on hw_*.md; affected prompts re-issued; qa.md answers rehearsed alone | Y |
| Fri 3 – Sat 4 Oct | Full timed run-through together, trims; terminal demo tested from a cold shell | M, Y |
| Sun 5 Oct | Rehearsal only. No content changes after noon. | M, Y |
| Mon 6 Oct | Presentation | |

## Open for Matan

- Agree the decisions table above, or say what to change.
- Confirm or replace each `owner: M` slide in `deck.md` (13 slides + S26); every number cites a report line.
- Decide on two shipped-report inconsistencies found while sourcing the slides: `hw/docs/hardware_report.md:94-96`
  labels the mtf_cam power run as 20 ns while quoting the 27 ns figure (10.2 mW); `hw/huffman_engine/docs/integration.md:80-99`
  still narrates the cProfile 1.97x ceiling next to the shipped 1.67x. Fix in the repo post-submission, or leave and explain if asked.

## Progress (2026-09-26)

| Step | State | Evidence |
|---|---|---|
| 1 Strategy | written, awaiting Matan's agreement and the date | this file |
| 2 Storyboard | done | `storyboard.md`: title + 26 main slides, 1350 s; brief coverage check at the bottom |
| 3 Spec | done, all slides `DRAFT` | `deck.md` 39/39 pass `check_numbers.py`; `derivations.md` holds the projection arithmetic |
| 4 Assets | done | 15 files in `assets/` from `make_assets.py`; clip 44 frames / 24.5 s, sim 2/2 PASS byte-exact |
| 5 Build | not started | `prompts/` generated (briefing + 3 setup + 39 slides), `verify/` ready |
| 6 Matan pass | not started | 13 `owner: M` slides + S26 |
| 7 Rehearsal | not started | `qa.md`: 47 questions, all owned |

## Rehearsal log

| Date | Run time | Notes |
|---|---|---|
| | | |
