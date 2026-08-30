---
name: hw-prd
description: Write the Product Requirements Document for an accelerator module through a grilling interview (stage 1 of hw/FLOW.md). Use when hw-flow reaches the prd stage or the user asks for a PRD, KPIs, or the HW/SW split of a module.
---

# hw-prd — stage 1, PRD

Inputs: `research/hw-algorithms-<bench>.md`, `results/baseline_<bench>_stats.txt`,
`results/perf_report_<bench>.txt`, `report_<bench>.txt` §5 stub, `benchmarks/bm_<bench>/`.
Output: `hw/<module>/docs/prd.md`. Shared vocabulary: `hw/CONTEXT.md`; decisions:
`hw/docs/adr/NNNN-<slug>.md`. PRDs of all three modules are written in lockstep (shared bus,
clock and driver decisions become one ADR each).

## Procedure

1. `python3 tools/hw/status.py set <module> prd in_progress`.
2. Invoke `grilling` and `domain-modeling` directly (`grill-with-docs` is user-invocation only and the Skill tool refuses it), seeded
   with the agenda below. Every term the user and the research note use differently goes into
   `hw/CONTEXT.md` the moment it is settled; every cross-module choice becomes an ADR.
3. Golden model first: `golden/` **wraps the upstream benchmark algorithm** (import + instrument,
   never re-implement) — `dev/<bench>/t0_stock.py` or a pinned commit, because
   `benchmarks/bm_<bench>/run_benchmark.py` carries the software teammate's optimisations.
   Cross-check the golden against a C library where one exists (`bz2`, `zlib`, NumPy). Count
   consumed bits/bytes in the wrapper itself; a reference's own position or size reporting is
   not trusted (stock pyflate's `tellbits()` is off by 16). An *emulation model* of the
   hardware's exact algorithm sits beside it as the pyuvm predictor. Calibrate every numeric
   tolerance or cycle claim in software (`golden/calibrate.py`) before writing the number into a
   requirement; quote the measured value and the margin. Three rules that each cost an
   iteration once: quote the reference's index expression verbatim in the emulation-model
   docstring (`favourites[r - 1]` → rank = s − 1); normalise captured values (ints vs 1-byte
   `bytes`) at capture; a cycle claim comes from a two-sided *simulation* with named resources
   (queues, ports, widths) and a printed sweep, never from a closed-form estimate.
4. Write `docs/prd.md` with these sections: Purpose and workload slice; KPIs; Functional
   requirements (numbered `PRD-Fn`); HW/SW split; Interfaces (at PRD level: bus family, clock
   target, data volume per invocation); Non-goals; Acceptance tests; Open questions.
5. Every requirement row carries: id, statement, measurable KPI with unit, acceptance test
   (the `make` target or tb sequence that will prove it), source (profile line / research §).
6. Run `hw-review` in spec mode; resolve every `must`.
7. Record gate rows and set `review` (checkpoint; the human approves via `hw-flow`).

## Agenda (module-specific)

**grape_pipeline** — KPI = **cycles per step** (20,000 dependent steps; pair throughput is not
the bottleneck, rsqrt-chain latency is — research §5). Clock target (sky130, 50–100 MHz). FP64
decision: IEEE binary64 RNE datapath in the benchmark's operation order; oracle = |ΔE/E| ≤ 1e-12
plus per-step diff, never bit-exact trajectories (research §4) — record as ADR. Pair-list input
interface (stretch: software tree walk at large N). Non-goal: GRAPE-style FP32 + fixed
accumulate (compare it in PPA only).
**huffman_engine** — KPI = **symbols per cycle** (target 1 sym/cycle, comparator cascade,
research §1 a′), table-build cycles per block (≤ ~300), both bzip2 (MSB-first, MAXLEN 20, 2–6
tables, selectors every 50 symbols) and DEFLATE (LSB-first, MAXLEN 15) modes. Workload slice from
the profile: `find_next_symbol` ~44 % + bit-buffer ~20 %. SW keeps delta-coded length parsing.
**mtf_cam** — KPI = 1 symbol/cycle sustained including RUNA/RUNB expansion; output = L-vector byte
stream into a DMA buffer; slice = `move_to_front` ~11 %. Non-goal: inverse BWT stays in software
(research §3) — state it as a deliberate non-target for report §7.
**All** — read the software teammate's latest findings first (`dev/<bench>/FINDINGS.md`,
`git log -- benchmarks/bm_<bench>/`): the optimised software moves the hotspots. HW/SW split
table (function → HW/SW → data crossing per invocation, bytes); Amdahl bound from *self-time*
profile shares; speed-up quoted against both the stock and the optimised software; acceptance
test names that `hw-dv-testplan` will reuse.

## Gate (FLOW.md row 1)

| Criterion | Evidence command |
|---|---|
| every requirement has a measurable KPI + acceptance test | `grep -c '^| PRD-' hw/<module>/docs/prd.md` equals rows with a KPI and test column filled; cite the table |
| HW/SW split table | `docs/prd.md §HW/SW split` |
| workload slice quantified from `results/` profile | percentages quoted with `results/perf_report_<bench>.txt` line numbers |
| `hw-review` findings resolved | `docs/review_prd.md: N findings, 0 must open` |

```
cd "$(git rev-parse --show-toplevel)"
python3 tools/hw/status.py gate <module> prd "<criterion>" pass "<evidence>"   # ×4
python3 tools/hw/status.py set <module> prd review
```
