# Hardware development flow

`PRD → MAS → uArch → RTL → DV[testplan → bring-up → coverage closure → sign-off] → PPA → HW/SW integration`

This file is the single definition of the flow: stage names, exit gates, the skill that runs each
stage, the hooks that guard it, and how progress is tracked. `hw/PLAN.md` is the concrete step list;
`hw/PROGRESS.md` is generated from `hw/STATUS.json` and never hand-edited.

## Vocabulary

| Term | Meaning here |
|---|---|
| **PRD** | Product Requirements Document — what the accelerator must do and how well: KPIs (cycles/step or symbols/cycle, latency, clock, area budget), workload slice, HW/SW split. `docs/prd.md` |
| **MAS** | Micro-Architecture-independent **Architecture Spec** — external view: I/O, data widths, register map, DMA/streaming choice, block diagram, driver API. `docs/mas.md` |
| **uArch** | Micro-architecture spec — internal view: pipeline stages, FSMs, number formats (Q-notation / IEEE-754), memories, timing budget, CDC. `docs/uarch.md` |
| **RTL** | Synthesizable SystemVerilog under `rtl/`, lint-clean, Yosys-synthesizable subset |
| **DV** | Design Verification. **Testplan** (features → tests → covergroups → checkers, `docs/testplan.md`), **bring-up** (UVM env alive, first directed test passes), **coverage closure** (constrained-random until coverage goals met), **sign-off** (all gate criteria pass) |
| **UVM env** | pyuvm testbench: `uvm_test` → `uvm_env` → agents (`uvm_sequencer`/`uvm_driver`/`uvm_monitor`) → `uvm_scoreboard` fed by the Python golden model; sequences under `tb/sequences/` |
| **Golden model** | Frozen Python reference derived from `benchmarks/bm_*` (`golden/`); the scoreboard's source of truth. Hook-protected against edits |
| **PPA** | Performance / Power / Area from synthesis: Yosys + sky130 Liberty (fast gate), OpenLane 2 (sign-off numbers, die shot). `docs/ppa.md` |
| **Integration** | HW/SW interface realised: register-map ↔ Python driver model, speedup estimate vs baseline profile, report §7 material |
| **Gate** | Exit criteria of a stage, evaluated by tools where possible, recorded with evidence in `STATUS.json` |
| **Checkpoint** | Gate that also needs human approval: PRD, MAS, uArch, DV sign-off |
| **Design review** | Agent pre-review (`hw-review`) run before every checkpoint; findings presented with the artifact |
| **Friction log** | `hw/.advisor/friction.jsonl` — every failed command/lint/sim under `hw/`, mined by `hw-advisor` |

## Modules

| Module | Benchmark | Function | Golden model |
|---|---|---|---|
| `grape_pipeline` | nbody | full `advance(dt, n)` step loop in FP64: pair forces (r⁻³ᐟ² via sqrt + NR reciprocal), velocity + position update; pair-list input | `benchmarks/bm_nbody/run_benchmark.py::advance`, energy oracle |
| `huffman_engine` | pyflate | bit aligner + canonical-Huffman table build + comparator-cascade decode (1 sym/cycle), bzip2 selector FSM, DEFLATE mode (LSB-first, MAXLEN 15) | instrumented pyflate: (table_id, code_len, symbol) trace |
| `mtf_cam` | pyflate | 256-entry move-to-front shift-register CAM + RUNA/RUNB zero-run expander → L-vector byte stream | pyflate `move_to_front` + run decode trace |

Order: lockstep PRD + MAS for all three (shared bus/driver/clock decisions), then module-by-module
from uArch: `grape_pipeline` → `huffman_engine` → `mtf_cam`. Inverse BWT stays in software by
decision (see `research/hw-algorithms-pyflate.md` §3).

## Stages, skills, gates

| # | Stage | Skill | Artifacts | Exit gate | Checkpoint |
|---|---|---|---|---|---|
| 1 | PRD | `hw-prd` | `docs/prd.md` | every requirement has a measurable KPI + acceptance test; HW/SW split table; workload slice quantified from `results/` profile; `hw-review` findings resolved | **human** |
| 2 | MAS | `hw-mas` | `docs/mas.md`, `docs/block_diagram.{mmd,svg}` | I/O table with widths + clock; register map (offset, name, bits, access, reset); DMA/stream protocol; driver API sketch; block diagram; `hw-review` resolved | **human** |
| 3 | uArch | `hw-uarch` | `docs/uarch.md` | pipeline/FSM diagrams; number formats fixed; memories sized; per-stage timing budget; latency/throughput derived and matches PRD KPI; `hw-review` resolved | **human** |
| 4 | RTL | `hw-rtl` | `rtl/*.sv` | `make lint` clean (`verilator --lint-only -Wall`); Yosys `synth` succeeds (synthesizable subset); agent code review resolved | agent review |
| 5 | DV testplan | `hw-dv-testplan` | `docs/testplan.md` | features ↔ tests ↔ covergroups ↔ checkers matrix; golden-model interface defined; formal properties listed | — |
| 6 | DV bring-up | `hw-dv-bringup` | `tb/**` | pyuvm env instantiates; first directed test passes on Verilator; scoreboard compares against golden | — |
| 7 | DV coverage closure | `hw-dv-signoff` | `tb/**`, coverage reports | constrained-random sequences; line/toggle ≥ 90 %; all functional covergroups hit | — |
| 8 | DV sign-off | `hw-dv-signoff` | `STATUS.json` evidence | golden equivalence on the **full benchmark input**; directed + random suites pass; coverage goals; lint clean; Icarus 4-state run X-free after reset; formal (sby) where listed | **human** |
| 9 | PPA | `hw-ppa` | `docs/ppa.md`, `synth/` | Yosys+Liberty area + cell counts; OpenLane 2 run: Fmax, area µm², power; trade-off table (≥2 design points) | — |
| 10 | Integration | `hw-integrate` | `docs/integration.md`, driver model | register map ↔ driver model consistent; cycle-accurate speedup estimate vs `results/baseline_*`; report §7 bullets mapped | — |

Cross-cutting skills: `hw-flow` (orchestrator), `hw-review` (pre-review), `hw-status` (only writer
of `STATUS.json`), `hw-advisor` (lessons + skill improvement). Third-party: `claude-skill-verilog`
(RTL style, Verilator/Yosys rules), `gf-cocotb` (cocotb runner templates), `tb-best-practices`
(TB architecture), superpowers (`test-driven-development`, `requesting-code-review`,
`systematic-debugging`), `grill-with-docs` (drives PRD/MAS/uArch interviews).

## Orchestration — `/hw-flow <module>`

0. Ordering rule: all PRDs before any MAS (lockstep); the uArch of the next module in `order` starts
   only after the previous module's `dv_signoff` is `done`. At most one non-checkpoint stage advances
   per invocation.
1. Read `hw/STATUS.json`; find the module's first stage not `done`.
2. If the stage is a checkpoint in state `review`: present the artifact + `hw-review` findings, ask
   for approval; on approval mark `done` and stop (one checkpoint per invocation).
3. Otherwise run the stage skill; on completion evaluate the gate with tools; record evidence via
   `hw-status`; run `hw-advisor`; if the stage is a checkpoint set `review` and stop, else advance.
4. Never skip a gate; a failed gate sets `blocked` with the failing criterion.

## Hooks (`.claude/settings.json` → `tools/hw/*.py`)

**Mode gate.** `hw/.advisor/mode` (gitignored, per machine; `/hw-mode on|off|status`,
`tools/hw/mode.py`) is the explicit signal that a checkout is used for hardware work. Unset → the
first session asks once (AskUserQuestion) and records the answer. `off` → SessionStart injection and
the Stop reminder stay silent and `/hw-flow` refuses; path-scoped hooks never fire outside `hw/`
anyway. A software-only teammate therefore sees nothing of the flow.

| Event | Matcher | Action |
|---|---|---|
| PostToolUse | Edit/Write of `hw/**/*.sv` | `verilator --lint-only -Wall` on the file; warnings returned to the agent |
| PostToolUse | Edit/Write of `hw/STATUS.json` | regenerate `hw/PROGRESS.md`; `gh_sync.py` (no-op until `gh auth` works) |
| PostToolUse | Bash with non-zero exit under `hw/` | append to `hw/.advisor/friction.jsonl` |
| PreToolUse | Edit/Write of `hw/*/golden/**` | deny — golden models are frozen; change via explicit user request only |
| SessionStart | — | mode unset: ask once; mode on: inject `hw/PROGRESS.md`; mode off: silent |
| Stop | — | mode on and `hw/` changed: warn if `.sv` changed without a `make sim`; remind to run `hw-advisor` |

## Tracking

- `hw/STATUS.json` — source of truth. Schema:
  ```json
  {"modules": {"<module>": {"stages": {"<stage>": {"state": "todo|in_progress|review|done|blocked",
     "started": "ISO", "finished": "ISO", "gate": {"<criterion>": {"result": "pass|fail|n/a", "evidence": "..."}}}},
     "metrics": {"dv": {"line_cov": 0, "toggle_cov": 0, "func_cov": 0, "tests_run": 0, "tests_pass": 0, "formal": "n/a"},
                 "ppa": {"cells": 0, "area_um2": 0, "fmax_mhz": 0, "power_mw": 0}}}},
   "order": ["grape_pipeline", "huffman_engine", "mtf_cam"],
   "stages": ["prd", "mas", "uarch", "rtl", "dv_testplan", "dv_bringup", "dv_coverage", "dv_signoff", "ppa", "integration"]}
  ```
- `hw/PROGRESS.md` — generated: Mermaid stage-flow diagram per module (nodes coloured by state),
  module × stage matrix, per-stage gate checklists with evidence, metrics table.
- GitHub Issues mirror (when access exists): one issue per module × stage, labels `hw`,
  `module:<m>`, `stage:<s>`; Project board columns = stages.

## Conventions

- Glossary `hw/CONTEXT.md`; ADRs `hw/docs/adr/NNNN-<slug>.md`; lessons `hw/docs/lessons.md`
  (`## <date> — <module>/<stage>`); friction lines `{ts, cmd, exit, tail}`.
- Review findings: `hw/<module>/docs/review_<stage>.md`, rows `id | must/should/nit | location |
  problem | fix`; gate criterion `hw-review findings resolved` (spec) / `agent code review resolved` (RTL).
- Per-module layout: `docs/` (prd, mas, uarch, testplan, ppa, integration, review_*, block_diagram,
  dieshot), `rtl/`, `golden/`, `tb/` (`env.py`, `tests/`, `sequences/`, `unit/`, `vectors/`, `cov/`),
  `formal/`, `synth/` (`yosys.ys`, `area.txt`, `config.json`, `runs/`), `driver/`.
- Test names: `test_smoke`, `test_random`, `test_full_benchmark`, `test_driver`; make variables
  `TESTCASE=`, `SEED=`, `PARAMS=` for design-point sweeps.
- `tools/hw/status.py` CLI: `next <m>` · `show [<m>]` · `set <m> <stage> <state> [--reason]` ·
  `gate <m> <stage> "<criterion>" pass|fail|n/a "<evidence>"` · `metric <m> dv.<k>|ppa.<k> <v>` · `render`.
- Skill edits made by `hw-advisor` are logged to `prompt.txt` (source `hw-advisor`); edits to vendored
  third-party skills are marked as a "project overlay" at the top of that file.

## Make targets (per module, `include ../common/Makefile.cocotb`)

`lint` · `sim` (Verilator, pyuvm) · `sim-icarus` · `waves` (FST) · `cov` (Verilator coverage
report) · `area` (Yosys + sky130 Liberty → `synth/area.txt`) · `formal` (sby) · `openlane` ·
`status` (render PROGRESS.md) · `clean`

## Toolchain (pinned)

OSS CAD Suite nightly **2026-08-26** (`hw/setup.sh`): Verilator ≥ 5.036, Yosys, Icarus, sby,
GTKWave, Surfer. `hw/.venv`: cocotb ~2.0, pyuvm, pytest, cocotbext-axi, pyvcd. sky130_fd_sc_hd
Liberty (tt, 25 °C, 1.8 V). OpenLane 2 via Nix (`--with-openlane`).

## Rubric mapping (project_instructions.md §7)

| Rubric bullet | Produced by |
|---|---|
| Hardware description (Verilog/SV) | RTL stage |
| Inputs and outputs, widths, interfaces, frequency | MAS |
| Hardware architecture (datapath + control) | uArch |
| HW/SW interface (APIs, drivers, MMIO, DMA) | MAS + Integration |
| Acceleration justification + estimate | PRD + Integration |
| Block diagram | MAS |
| Performance/area/power trade-offs | PPA |
