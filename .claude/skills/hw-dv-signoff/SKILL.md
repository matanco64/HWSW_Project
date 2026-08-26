---
name: hw-dv-signoff
description: Close coverage with constrained-random pyuvm sequences and sign off verification of an accelerator module (stages 7 dv_coverage and 8 dv_signoff of hw/FLOW.md). Use when hw-flow reaches either stage or the user asks to close coverage, run the full-benchmark equivalence, or sign off a module.
---

# hw-dv-signoff — stages 7 and 8

Inputs: green `tb/` from bring-up, `docs/testplan.md` matrix, `golden/`, full benchmark input
(`benchmarks/bm_<bench>` data or the 20,000-step `advance`). Outputs: `tb/sequences/random_*.py`,
coverage reports under `tb/cov/`, `STATUS.json` evidence. Two stages, one skill; run the
coverage part to `done` before starting sign-off.

## Stage 7 — coverage closure (`dv_coverage`)

1. `python3 tools/hw/status.py set <module> dv_coverage in_progress`.
2. Write constrained-random `uvm_sequence`s (`tb/sequences/random_<feature>.py`): randomise the
   transaction fields the testplan's covergroup bins name; constraints from `mas.md` valid ranges;
   seeds logged (`SEED=` in the runner). Register them in `test_random`.
3. Functional coverage: cocotb-coverage-style covergroups in the `uvm_monitor`s, bins as listed in
   the testplan; report written to `tb/cov/func_cov.txt` at `report_phase`.
4. `make -C hw/<module> cov` (Verilator `--coverage`, line + toggle report `tb/cov/coverage.txt`).
   Loop: read the uncovered lines → add a directed or random sequence → rerun. Exclusions
   (`// verilator coverage_off`) only with a testplan-cited reason.
5. Gate rows; `metric dv.line_cov / dv.toggle_cov / dv.func_cov`; `set ... done`.

| Criterion | Evidence |
|---|---|
| constrained-random sequences | `ls tb/sequences/random_*.py`; `make sim TESTCASE=test_random → PASS` |
| line/toggle ≥ 90 % | `tb/cov/coverage.txt` summary lines |
| all functional covergroups hit | `tb/cov/func_cov.txt`: every bin ≥ 1 |

## Stage 8 — sign-off (`dv_signoff`, human checkpoint)

1. `set <module> dv_signoff in_progress`.
2. **Full-benchmark equivalence**: `test_full_benchmark` streams the entire input through the DUT
   and compares with the golden trace under the testplan tolerance
   (`make sim TESTCASE=test_full_benchmark`). `huffman_engine`/`mtf_cam`: every block of
   `interpreter.tar.bz2`; `grape_pipeline`: 20,000 steps, energy check.
3. Full regression: `make sim` (all tests), `make sim-icarus` (4-state, X-free after reset),
   `make lint`, `make formal` where the testplan lists properties (sby `PASS`).
4. `hw-review` RTL mode over final `rtl/` + `tb/`; resolve `must`.
5. Gate rows; metrics (`dv.tests_run`, `dv.tests_pass`, `dv.formal`); `set ... review` and hand to
   `hw-flow` for approval.

| Criterion | Evidence |
|---|---|
| golden equivalence on the full benchmark input | `test_full_benchmark → PASS, N items, 0 mismatches` |
| directed + random suites pass | `make sim` summary `tests_pass == tests_run` |
| coverage goals | `dv_coverage` gate rows (line, toggle, functional) |
| lint clean | `make lint → 0 warnings` |
| Icarus 4-state run X-free after reset | `make sim-icarus → PASS, no X assertions` |
| formal (sby) where listed | `make formal → PASS` or `n/a: testplan §Formal none` |

```
python3 tools/hw/status.py gate <module> dv_signoff "<criterion>" pass|n/a "<evidence>"   # ×6
python3 tools/hw/status.py set <module> dv_signoff review
```
