---
name: hw-dv-testplan
description: Write the verification testplan (features ↔ tests ↔ covergroups ↔ checkers, golden-model interface, formal properties) for an accelerator module (stage 5 of hw/FLOW.md). Use when hw-flow reaches dv_testplan or the user asks what tests a module needs.
---

# hw-dv-testplan — stage 5, DV testplan

Inputs: `docs/prd.md` (acceptance tests, `PRD-Fn`), `docs/mas.md` (interfaces, register map),
`docs/uarch.md` (FSMs, hazards), `rtl/` (parameters), `hw/<module>/golden/` (frozen Python
reference). Output: `hw/<module>/docs/testplan.md`. Methodology reference: `tb-best-practices`
(layered TB) in pyuvm vocabulary.

## Procedure

1. `python3 tools/hw/status.py set <module> dv_testplan in_progress`.
2. **Feature list.** One row per `PRD-Fn`, per register, per FSM transition, per hazard in
   `uarch.md §Hazards`, per error case in `mas.md §Error`. Id `F-nn`.
3. **Matrix** (the artifact's core): `feature | test (directed / random sequence name) |
   covergroup + bins | checker (scoreboard / assertion) | priority | status`. Every feature has all
   four columns; a feature with no checker is not verifiable and goes back to the spec.
4. **Env plan** in pyuvm terms: `uvm_test` names (`test_smoke`, `test_<feature>`, `test_random`),
   `uvm_env` composition, agents (`stream_agent` for valid/ready streams, `axi_lite_agent` for
   MMIO — both from `hw/common/tb/`), `uvm_sequencer`/`uvm_driver`/`uvm_monitor` per agent,
   `uvm_scoreboard` fed through TLM analysis ports, `ConfigDB` keys (`dut`, `clk_period_ns`,
   `golden`), sequence list under `tb/sequences/`.
5. **Golden-model interface.** The Python call the scoreboard makes, its inputs (from the same
   stimulus the driver sends) and the expected stream it returns, tolerance policy
   (`grape_pipeline`: |ΔE/E| ≤ 1e-12 and per-step ulp diff; `huffman_engine`:
   `(table_id, code_len, symbol)` trace exact; `mtf_cam`: byte stream exact). Full-benchmark
   input for sign-off: `benchmarks/bm_<bench>` data file, or the 20,000-step `advance`.
6. **Coverage goals.** Line/toggle ≥ 90 % (Verilator `--coverage`); functional bins per
   covergroup listed; exclusions justified per line.
7. **Formal properties** (sby, optional per module): handshake (`valid` stable until `ready`),
   FSM reachability, `mtf_cam` permutation invariant, aligner never under-runs. List with the
   property file name `formal/<name>.sv`; "none" is acceptable with a reason.
8. `hw-review` spec mode on the testplan (traceability check); resolve `must`. Record; set `done`.

## Gate (FLOW.md row 5)

| Criterion | Evidence |
|---|---|
| features ↔ tests ↔ covergroups ↔ checkers matrix | `docs/testplan.md §Matrix` — N rows, no empty cell |
| golden-model interface defined | `§Golden model` — function signature + tolerance |
| formal properties listed | `§Formal` — list or "none: <reason>" |

```
cd "$(git rev-parse --show-toplevel)"
python3 tools/hw/status.py gate <module> dv_testplan "<criterion>" pass "<evidence>"   # ×3
python3 tools/hw/status.py set <module> dv_testplan done
```
