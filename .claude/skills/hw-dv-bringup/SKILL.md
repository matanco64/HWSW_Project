---
name: hw-dv-bringup
description: Bring up the pyuvm testbench for an accelerator module until the first directed test passes against the golden model on Verilator (stage 6 of hw/FLOW.md). Use when hw-flow reaches dv_bringup or the user asks to get the testbench running.
---

# hw-dv-bringup — stage 6, DV bring-up

Inputs: `docs/testplan.md` (env plan, matrix), `rtl/`, `hw/<module>/golden/`,
`hw/common/tb/` base classes: `base_test.py` (`uvm_test` with clock/reset and `ConfigDB`
setup), `base_env.py` (`uvm_env` that builds agents and scoreboard), `stream_agent.py`
(valid/ready `uvm_sequencer`/`uvm_driver`/`uvm_monitor`), `axi_lite_agent.py` (MMIO agent over
`cocotbext-axi`), `scoreboard.py` (`uvm_scoreboard` with analysis-port FIFOs and a golden
callback), `vcd2csv.py` (waves → CSV for Python debugging). Runner templates: `gf-cocotb`;
architecture: `tb-best-practices`. Output: `hw/<module>/tb/**`.

## Layout

```
tb/test_<module>.py     # cocotb entry: runs pyuvm tests named in testplan
tb/env.py               # <Module>Env(base_env.BaseEnv): agents + scoreboard + golden binding
tb/sequences/*.py       # uvm_sequence subclasses: smoke, directed per feature, random
tb/unit/                # block-level cocotb tests from hw-rtl
tb/Makefile / pytest    # via ../common/Makefile.cocotb: SIM?=verilator
```

## Procedure

1. `python3 tools/hw/status.py set <module> dv_bringup in_progress`.
2. Subclass the common base classes; wire `ConfigDB` keys from the testplan; connect each monitor's
   analysis port to the scoreboard's export. The scoreboard's expected side calls `golden/`
   exactly as `testplan.md §Golden model` states — never a re-implementation in the tb.
3. Write `test_smoke` (reset → configure via `axi_lite_agent` → one transaction via
   `stream_agent` → compare) as the first `uvm_test`; sequence under `tb/sequences/smoke.py`.
4. `make -C hw/<module> sim` (Verilator). Red first; then iterate. Debugging is
   `superpowers:systematic-debugging`: reproduce, `make waves` (FST), `vcd2csv.py` the relevant
   signals, reason from the CSV, one hypothesis per change. Treat a scoreboard mismatch as an RTL
   bug until the golden call is shown to be misused.
5. Run `make -C hw/<module> sim-icarus` once the smoke test is green: 4-state run must show no X on
   outputs after reset (`uvm_monitor` asserts on `X` values).
6. Add the directed tests from the matrix in priority order until the first full `PRD-Fn`
   acceptance test passes; record which matrix rows are now `pass` in `testplan.md`.
   Measure every cycle-count KPI on a full-shape configuration (maximum pairs/symbols, the
   benchmark's own topology) before leaving bring-up — a tiny smoke hides phases the KPI
   binds on (grape: NPAIRS=2 measured 126 cycles/step, the real 10-pair list 162 vs K1=128).
   Run at least one top-level test with sink backpressure (a deterministic toggling tready):
   almost-full/credit gating bugs are invisible to unit TBs and always-ready sinks (huffman
   K1 1.5068→1.0068). When citing an assertion as gate evidence, confirm the define that
   compiles it appears in the build command (`ifdef SIMULATION` was dead in every build).
7. `hw-review` RTL mode on `tb/` + touched `rtl/`; resolve `must`. Record; set `done`.

## Gate (FLOW.md row 6)

| Criterion | Evidence |
|---|---|
| pyuvm env instantiates | `make -C hw/<module> sim` log: `<Module>Env` build/connect phases complete |
| first directed test passes on Verilator | `make sim TESTCASE=test_smoke → PASS` |
| scoreboard compares against golden | scoreboard log line `compared N items, 0 mismatches` with golden function name |

```
cd "$(git rev-parse --show-toplevel)"
python3 tools/hw/status.py gate <module> dv_bringup "<criterion>" pass "<evidence>"   # ×3
python3 tools/hw/status.py metric <module> dv.tests_run <n>; ... dv.tests_pass <n>
python3 tools/hw/status.py set <module> dv_bringup done
```
