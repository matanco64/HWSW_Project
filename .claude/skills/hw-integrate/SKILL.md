---
name: hw-integrate
description: Realise the HW/SW interface of a finished accelerator module — Python driver model matching the register map, cycle-accurate speedup estimate vs the baseline profile, report §7 material (stage 10 of hw/FLOW.md). Use when hw-flow reaches integration or the user asks for the driver, the speedup estimate, or the report's hardware section.
---

# hw-integrate — stage 10, integration

Inputs: `docs/mas.md` (register map, driver API sketch), `docs/ppa.md` (Fmax, chosen point),
`STATUS.json` metrics, `results/baseline_<bench>_stats.txt` (mean ± std), profile percentages from
`results/perf_report_<bench>.txt` / `report_<bench>.txt` §2, `tb/` (cycle counts from
`test_full_benchmark`). Outputs: `hw/<module>/docs/integration.md`,
`hw/<module>/driver/<module>_driver.py` (+ `test_driver.py`), text for `report_<bench>.txt` §5.

## Procedure

1. `python3 tools/hw/status.py set <module> integration in_progress`.
2. **Driver model.** `driver/<module>_driver.py`: register offsets/fields generated from the MAS
   register map (one constant per row, same names), a `MMIO` protocol class (`read32/write32`),
   the API functions from `mas.md §Driver API` (`load_state`, `start`, `wait_done`, DMA
   descriptor build), and a `SimBackend` that drives the same pyuvm `axi_lite_agent` so the tb
   can run the driver against the RTL. `test_driver.py` checks every register constant against
   `mas.md` (parse the table) and runs the API on the `SimBackend` (`make sim
   TESTCASE=test_driver`).
3. **Software side.** Patch points in `benchmarks/bm_<bench>/run_benchmark.py` (function → driver
   call), data marshalling cost (bytes per invocation from the PRD HW/SW split), what stays in
   Python (iBWT, RLE1, CRC; energy reporting).
4. **Speedup estimate.** Baseline `T` = mean from `baseline_<bench>_stats.txt`. Accelerated
   fraction `f` = profile share of the replaced functions. Hardware time = cycles from
   `test_full_benchmark` (or KPI × work) ÷ Fmax from `ppa.md`, plus driver overhead (MMIO writes ×
   assumed bus latency, DMA bytes ÷ assumed bandwidth — state both). Amdahl:
   `S = 1 / ((1 − f) + t_hw/T)`; give the ideal `1/(1 − f)` bound beside it and a sensitivity row
   for the two assumptions. All inputs cited by file and line.
5. **Consistency check.** Register names in driver == `mas.md` == `rtl/axi_lite_regs` — script
   the diff (`python3 driver/check_regmap.py`), zero differences.
6. **Write `docs/integration.md`**: HW/SW interface (APIs, driver, MMIO, DMA); software changes;
   speedup table; assumptions; rubric map: each `project_instructions.md` §7 bullet → the file and
   section that answers it (FLOW.md "Rubric mapping"); the paragraphs to paste into
   `report_<bench>.txt` §5.
7. Record gate rows; `set ... done`.

## Gate (FLOW.md row 10)

| Criterion | Evidence |
|---|---|
| register map ↔ driver model consistent | `driver/check_regmap.py → 0 differences`; `test_driver → PASS` |
| cycle-accurate speedup estimate vs `results/baseline_*` | `docs/integration.md §Speedup` — T, f, cycles, Fmax cited |
| report §7 bullets mapped | `docs/integration.md §Rubric map` — 7 bullets, each with a path |

```
python3 tools/hw/status.py gate <module> integration "<criterion>" pass "<evidence>"   # ×3
python3 tools/hw/status.py set <module> integration done
```
