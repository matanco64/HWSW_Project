# HW-design agent skills and open-source RTL toolchain — survey and recommendation

Date: 2026-08-25. Scope: what Claude Code skills/plugins exist for Verilog/SystemVerilog work, what
arXiv:2603.08716 ("Design Conductor") contributes, which simulation/verification tools an agent
should drive on Ubuntu 24.04 / WSL2, and what to adopt for `hw/` (huffman_engine, mtf_cam,
grape_pipeline). Nothing was installed; this file is the only change.

## TL;DR

- **The paper (Design Conductor, Verkor, arXiv 2603.08716) releases no skills, prompts, or benchmark.**
  It is a closed-system report; only "VerCore RTL source and scripts ... will be publicly available"
  (no URL yet). Its transferable lessons are methodological: per-module testbenches before
  integration, a golden reference model driving an integration testbench, VCD-to-CSV debugging in
  Python, and specs written in "extremely deliberate, tight, and verifiable/measurable" form.
- **Skills worth adopting (project-level, `.claude/skills/`):**
  1. `londey/claude-skill-verilog` (MIT, 178 installs) — concise SV style + Verilator lint/sim +
     Yosys-compatibility rules. Best fit, no plugin machinery.
  2. `codejunkie99/gateflow-plugin` skills `gf-cocotb` and `tb-best-practices` (BSL-1.1,
     non-commercial/educational use permitted) — cocotb Makefile/runner templates and TB patterns.
  Skip: `mindrally/skills@systemverilog`/`@fpga` (generic Vivado-flavoured bullet lists, no tool
  workflow), `babyworm/rtl-agent-team` (99 agents / 97 skills — far too heavy), `veriflow-cc`
  (installs globally into `~/.claude`, opinionated 4-stage pipeline).
- **Toolchain: Verilator + cocotb (pytest runner) + Yosys `stat` for area; iverilog fallback.**
  Nothing is installed on this machine. Ubuntu 24.04 apt ships Verilator 5.020, which is **below
  cocotb 2.0's minimum of Verilator 5.036**, and Yosys 0.33 (old). Install the **YosysHQ OSS CAD
  Suite** tarball instead (bundles yosys, sby+solvers, verilator, iverilog, cocotb, gtkwave, surfer,
  slang) and `pip install "cocotb~=2.0"` in a venv.
- **Instructor approval (project_instructions.md §7):** HDL must be Verilog/SystemVerilog/PyXHDL.
  Plain SystemVerilog RTL is in-scope. cocotb (Python testbench) is *verification*, not the HDL, so
  it should be fine, but state this explicitly in the report; if in doubt ask. Do **not** use
  Amaranth/Chisel/SpinalHDL for the accelerator RTL without approval.

## 1. arXiv 2603.08716 — Design Conductor (Verkor)

Source: https://arxiv.org/abs/2603.08716 , full text https://arxiv.org/html/2603.08716v1 ,
PDF https://arxiv.org/pdf/2603.08716 (v1 dated 11 Mar 2026; authors Ravi Krishna, Suresh Krishna,
David Chin, "The Verkor Team"; contact team@verkor.io).

- Claim: an autonomous agent ("Design Conductor", DC) built a RISC-V RV32I+Zmmul CPU ("VerCore"),
  5-stage in-order, from a 219-word requirements doc to GDSII in 12 hours: 1.48 GHz on ASAP7,
  CoreMark 3261, 2,809 um^2 excluding cache.
- Flow (Sec. 2-3): requirements ingestion -> design proposal -> design review (manual trace-through)
  -> per-module implementation + testbench ("DC always builds per-module testbenches and fixes
  module functionality to ensure that these testbenches pass before proceeding") -> integration
  test against Spike ISA simulator as golden reference ("confirm the design's architectural state
  and memory transactions match those reported by Spike") -> debug via VCD ("typically converts
  VCDs to CSV files and uses its inherent Python abilities") -> PPA loop with OpenROAD flow scripts.
- Architecture: memory system, context-management module, sub-agents managed by a "DC Core",
  worker servers syncing to a central DB; "many tens of billions of tokens consumed".
  LLM vendor/model is **not named**.
- Artifacts released: **none at time of writing** — no GitHub link in the paper (only
  eembc.org/coremark and riscv-isa-sim links). Statement: "The VerCore RTL source and scripts
  necessary to rebuild the GDSII will be publicly available." No skills, prompts, or benchmark suite.
- Reported model weaknesses (Sec. 5) that we should design our workflow around: models "reason
  about Verilog, which is an event-driven language, as if it were sequential code"; they
  "underestimate the complexity of work"; results depend on specs being "extremely deliberate,
  tight, and verifiable/measurable" (e.g., explicit CPI targets).
- Not verified: whether the code has since been published (no repo found via search on 2026-08-25).

Related agentic-RTL papers surfaced by search (not read in depth): "Architect in the Loop Agentic
Hardware Design and Verification" https://arxiv.org/pdf/2512.00016 ; "Trace2Skill"
https://arxiv.org/pdf/2605.21810 ; "Verilog-Evolve" https://arxiv.org/pdf/2605.26498 .

## 2. Existing Claude Code skills / plugins for RTL

Registry queries run: `npx -y skills@latest find verilog|systemverilog|rtl|cocotb|fpga`
(`find rtl` returns mostly right-to-left text skills — noise). Repo metadata from api.github.com.

| Skill / plugin | License, stars, last push | What it actually contains | Verdict |
|---|---|---|---|
| `londey/claude-skill-verilog` https://github.com/londey/claude-skill-verilog (SKILL.md: https://raw.githubusercontent.com/londey/claude-skill-verilog/master/SKILL.md) | MIT, 18 stars, 2026-04; 178 installs on skills.sh | Single SKILL.md: lowRISC-derived style (`always_ff` = simple NBAs only, logic in `always_comb`, `default_nettype none`, explicit widths, Q-notation for fixed point), `verilator --lint-only -Wall`, `verilator --binary --assert --timing`, a **Yosys-compatibility table** (no `return` in functions, no interfaces/modports, no `unique case`, flatten packed-array ports), FSM/CDC/RAM-inference/SVA sections | **Adopt.** Directly matches our Verilator+Yosys plan; Q-notation is useful for the nbody rsqrt datapath. |
| `codejunkie99/Gateflow-Plugin` https://github.com/codejunkie99/Gateflow-Plugin (skills under `plugins/gateflow/skills/*/SKILL.md`) | BSL-1.1 (non-commercial/educational use granted; converts to Apache-2.0 on 2028-01-30), 110 stars, 2026-05 | Full plugin: `gf` orchestrator, `gf-sim` (Verilator `--binary -Wall --trace`, PASS/FAIL parsing), `gf-cocotb` (cocotb Makefile + `cocotb_tools.runner` pytest example + `cocotbext-axi` AXI-Lite master snippet), `tb-best-practices` (layered TB, self-checking TB, scoreboard, transaction class), `gf-lint`, `gf-formal` (SymbiYosys), `gf-synth` (Yosys), board/pinmap DB, IP library (fifo, axi4lite_slave, ...) | **Adopt two skills only** (`gf-cocotb`, `tb-best-practices`). Whole plugin is FPGA-board oriented and emits `GATEFLOW-RESULT` blocks meant for its own orchestrator. Note the `gf-cocotb` template uses `Clock(..., units="ns")` — cocotb 2.0 renamed this to `unit=`; verify against https://docs.cocotb.org when using. |
| `mindrally/skills@systemverilog`, `@fpga` https://github.com/Mindrally/skills | Apache-2.0, 239 stars; ~950 installs each | Cursor-rule conversions: generic bullets (Vivado XDC, ILA, AXI bursts, "use `reg []` for RAM"). No commands, no tool workflow. | Skip; high install count reflects the collection, not RTL quality. |
| `babyworm/rtl-agent-team` https://github.com/babyworm/rtl-agent-team | MIT, 49 stars, active (2026-08-23) | Marketplace plugin: 99 agents + 97 skills, 6-phase pipeline (Research -> Arch -> uArch -> RTL -> Verify -> Design Note), `rat-setup` tool audit (verilator, cocotb, verible/slang, yosys+sby), optional `systemverilog-lsp` (slang-server) | Too heavy for a two-module course project; worth reading its `rtl-coding-conventions.md`/`rtl-verification-gate.md` rules later for ideas. The slang LSP sub-plugin could be handy. |
| `bjwanneng/veriflow-cc` https://github.com/bjwanneng/veriflow-cc | no license file, 48 stars, 2026-08 | `/vf-rtl` 4-stage pipeline (spec+golden_model.py -> codegen -> iverilog/cocotb verify -> lint+yosys), installs into `~/.claude/` via `install.py`; includes `vcd2table.py`, `synth_score.py`, formal via sby | Skip as a whole (global install, no license); its "spec.json + golden_model.py first" stage mirrors what we plan by hand. |
| `Fzhiyu1/chipforge-plugin` https://github.com/Fzhiyu1/chipforge-plugin | MIT, 4 stars, 2026-01 | Icarus-based sim, VCD->WaveJSON, "knowledge graph" | Skip (iverilog-only, stale). |
| `bjwanneng/verilog-generator`, `jwd83/skills@system-verilog-expert`, `chuanseng-ng/digital-chip-design-agents` | 1 star / 1 star / repo not found via API | Verilog-2005 generator with self-check; misc | Skip. |

Also seen but not evaluated: `rh42-ic/vibe-coding@synthesizable-systemverilog-best-practices`,
`1zkay/lint_agent@verilog-lint-triage`, `midstall/claude-for-hardware@fpga-bringup` (3 installs each).
Lists: https://github.com/travisvn/awesome-claude-skills , https://github.com/ComposioHQ/awesome-claude-skills
(neither has a dedicated hardware section as of the search).

## 3. Open-source toolchain survey (Ubuntu 24.04 / WSL2)

| Tool | What it is | Install | SystemVerilog support | Fit with Python golden model |
|---|---|---|---|---|
| **Verilator** https://verilator.org/guide/latest/ | Compiles Verilog/SV into a C++ model ("not a traditional simulator but a compiler"); mostly **two-state** (X -> value per `--x-assign`); `--timing` enables delays/event controls; `--binary` builds a runnable sim; `--lint-only -Wall` is the best free SV linter. Docs cover 5.050. | apt: `sudo apt install verilator` (=5.020 on 24.04 — too old for cocotb 2.0); docs say distro packages "almost never have the most recent Verilator version"; prefer OSS CAD Suite or git build (https://verilator.org/guide/latest/install.html) | Large synthesizable + testbench subset of IEEE 1800-2023; "class support is limited", assertions/covergroups "partially" supported (https://verilator.org/guide/latest/languages.html) | Excellent via cocotb (VPI); fastest for long trace diffs (pyflate symbol streams, nbody steps). |
| **Icarus Verilog** https://steveicarus.github.io/iverilog/ | Event-driven 4-state interpreter (`iverilog` compiles, `vvp` runs). | `sudo apt install iverilog` (12.0 on 24.04) | `-g2012` "enables the IEEE1800-2012 standard, which includes SystemVerilog"; docs: "Actual SystemVerilog support is ongoing" (https://steveicarus.github.io/iverilog/usage/command_line_flags.html). In practice: `logic`, `always_ff/comb`, packed structs, enums, `unique case` mostly OK; interfaces/classes weak. | Good via cocotb (cocotb supports Icarus 11.0+); 10-100x slower than Verilator. Use as 4-state cross-check for X-propagation/reset bugs. |
| **cocotb 2.0.1** https://docs.cocotb.org/en/stable/ | Python coroutine testbenches driving any VPI/VHPI simulator; pytest-integrated Python runner (`cocotb_tools.runner.get_runner`, still marked experimental). | `sudo apt-get install make python3 python3-pip libpython3-dev; pip install "cocotb~=2.0"` (https://docs.cocotb.org/en/stable/install.html) | Sim-limited; supports Icarus 11+, Verilator **5.036+** (https://docs.cocotb.org/en/stable/simulator_support.html) | **Ideal**: the same Python golden model (pyflate's Huffman/MTF, nbody's `advance`) can be imported directly into the test and compared per-transaction; `cocotbext-axi` gives an AXI-Lite master for the MMIO register file. |
| **Yosys** https://yosyshq.readthedocs.io/projects/yosys/ | RTL synthesis framework ("GCC of hardware synthesis"); `read_verilog -sv` + `synth` + `stat` gives cell/LUT/FF counts for area estimates; `synth_ice40`/`synth_ecp5` for FPGA-flavoured numbers, or `abc -liberty` with a Liberty file for ASIC-ish gate counts. | apt 0.33 (old); OSS CAD Suite nightly | "full support for the synthesizable subset of Verilog-2005"; SV via `-sv` is limited (interfaces/`return`/packed multi-dim ports problematic — see londey table). The `slang`-based frontend (`yosys -m slang; read_slang`, project https://github.com/povik/yosys-slang, now "sv-elab") is bundled in OSS CAD Suite and, per its README, integrated into Yosys from 0.67 (not independently verified). | N/A; produces the area/frequency-tradeoff numbers §7 asks for. Not a timing tool — for a rough Fmax use `synth_ice40`/`synth_ecp5` + nextpnr `--timing-allow-fail` report (optional). |
| **OpenLane / sky130** | Full RTL->GDS flow (Yosys + OpenROAD). | Docker-based; heavy | via Yosys | Optional stretch for a real um^2 area number; not required (project explicitly non-tapeout). |
| **GTKWave** https://gtkwave.sourceforge.net/ | Wave viewer; VCD/EVCD, FST, LXT, GHW. 3.3.128 stable; also on Flathub. | `sudo apt install gtkwave` (needs WSLg GUI) | n/a | For human debugging; the agent should instead parse VCD in Python (per the paper) — e.g. `pyvcd`/`vcdvcd` — or use cocotb's own logging. |
| **Surfer** https://gitlab.com/surfer-project/surfer | Modern Rust wave viewer (VCD/FST/GHW), web build and VS Code extension exist. | in OSS CAD Suite; prebuilt binaries | n/a | Nicer in WSL than GTKWave; details of install page not fetched (GitLab page returned only metadata) — unverified. |
| **SymbiYosys (sby)** https://symbiyosys.readthedocs.io/en/latest/install.html | Front-end for formal (BMC/k-induction) over Yosys; solvers: Yosys+sby required, Boolector recommended, Z3/Yices optional. | OSS CAD Suite (recommended by docs), or `pip install symbiyosys`+solvers | Open-source flow uses Yosys SV parser (limited SVA: immediate + simple `assert property` in `always @*`); full SVA needs Tabby CAD | Optional: prove MTF CAM invariants (permutation property) or FIFO/handshake safety in the DMA descriptor FSM — good report material, small cost. |
| **VUnit** https://vunit.github.io/ | Python-driven unit-test runner for VHDL/SV. | `pip install vunit_hdl` | Simulator list (https://vunit.github.io/cli.html): ModelSim/Questa, GHDL, NVC, Incisive, Riviera, ActiveHDL — **no Verilator/Icarus** | Not usable with our free simulators for SV. Skip. |
| **SVUnit** https://github.com/svunit/svunit | SV unit-test framework. | env-var setup scripts | Simulators: ius, questa, modelsim, riviera, vcs — **no Verilator/Icarus** listed | Skip. |
| **OSS CAD Suite** https://github.com/YosysHQ/oss-cad-suite-build | Nightly tarball bundling yosys, slang, sby + solvers (boolector, yices, z3, bitwuzla), verilator, iverilog, cocotb, gtkwave, surfer, nextpnr, ghdl. | download, extract, `export PATH="<loc>/oss-cad-suite/bin:$PATH"`; no system packages needed | — | **Recommended install path**: one archive gives Verilator >= 5.036 for cocotb 2.0 and a current Yosys. Caveat: it ships its own Python; keep cocotb tests in a project venv and let cocotb find the suite's `verilator`/`iverilog` on PATH (verify the two Pythons do not conflict — unverified on WSL). |

Machine state (checked 2026-08-25): `verilator`, `iverilog`, `yosys`, `gtkwave`, `vvp`, `sby`
all **absent**; `cocotb` not importable; Python 3.12.3, numpy 1.26.4, Ubuntu 24.04.3. apt
candidates: verilator 5.020-1, iverilog 12.0-2build2, yosys 0.33-5build2, gtkwave 3.3.116.
`gh` CLI and `poppler-utils` also absent.

PyXHDL (the third allowed HDL): https://github.com/davidel/pyxhdl — Python AST -> VHDL-2008 /
SystemVerilog-2012 generator (`pip install git+https://github.com/davidel/pyxhdl.git`). Not
recommended: tiny ecosystem, none of the skills above know it, and it adds a generator layer between
the agent and the simulator errors.

## 4. Recommendation

### 4.1 Skills to install (project-level, committed; run from repo root)

```bash
# 1. Style + Verilator/Yosys workflow (MIT). Single-skill repo, so no -s needed:
npx skills add londey/claude-skill-verilog -a claude-code --copy
# 2. cocotb templates + testbench patterns from GateFlow (BSL-1.1, educational use OK):
npx skills add codejunkie99/Gateflow-Plugin -a claude-code --copy -s gf-cocotb -s tb-best-practices
```
`-s` repeated per skill (not comma-separated); `--copy` rather than symlink so the files are
vendored and the repo stays self-contained (the existing `skills-lock.json` already records
mattpocock skills this way). If `npx skills add` cannot resolve the nested plugin path, copy the
two SKILL.md files from `plugins/gateflow/skills/<name>/SKILL.md` into
`.claude/skills/<name>/SKILL.md` manually and keep the license header. Then write **one project
skill of our own**, `.claude/skills/hw-verify/SKILL.md`, that pins our conventions: run
`make -C hw/<module> lint sim area`, compare against `golden/`, and never mark a module done without
the cocotb run passing (this is the "verification gate" both the paper and rtl-agent-team insist on).

Not installing: `mindrally/*`, `babyworm/rtl-agent-team`, `veriflow-cc` (reasons in §2). Revisit
`babyworm`'s `systemverilog-lsp` (slang-server) if lint feedback in-editor becomes useful.

### 4.2 Toolchain

Primary: **Verilator (>= 5.036) + cocotb 2.0 + Yosys**, iverilog as 4-state fallback, sby optional.
Install via OSS CAD Suite tarball (not apt, because apt Verilator 5.020 < cocotb minimum) plus
`python3 -m venv .venv && pip install "cocotb~=2.0" pytest cocotbext-axi`. Verify with
`verilator --version`, `yosys -V`, `cocotb-config --version`. Optional GUI: GTKWave via WSLg or Surfer.

Why cocotb rather than SV testbenches: pyflate and nbody golden models are Python (already in
`benchmarks/`), so the scoreboard can call them directly and diff symbol streams / trajectories;
Verilator gives the speed for full-file traces; iverilog catches X-propagation Verilator hides.
Cost: co-simulation overhead and the Verilator-version constraint; mitigated by the runner API.

### 4.3 Proposed `hw/` layout (mirrors product definition -> interface -> architecture -> RTL -> TB)

```
hw/
  README.md                 # existing overview
  common/
    Makefile.cocotb         # shared: SIM?=verilator, lint/sim/area/waves targets
    rtl/                    # shared cells: skid buffer, axi_lite_regs.sv, valid/ready fifo
  huffman_engine/
    docs/spec.md            # product definition, HW/SW interface (MMIO map, DMA descriptor), block diagram
    rtl/*.sv                # bit_aligner, len_compare, symbol_ram, selector_fsm, top
    golden/huffman_ref.py   # thin wrapper over benchmarks/ pyflate code -> symbol trace
    tb/test_huffman.py      # cocotb: streams a real .bz2/.gz block, diffs symbol stream
    tb/vectors/             # small captured inputs + expected traces
    Makefile                # include ../common/Makefile.cocotb
    synth/yosys.ys          # read_verilog -sv; synth; stat -> area.txt
  mtf_cam/      (same shape; golden = MTF list model; sby/ optional: permutation invariant)
  grape_pipeline/ (same shape; golden = nbody advance(); tb diffs positions/energy with tolerance;
                   docs/spec.md fixes number formats in Q-notation)
```
Makefile targets per module: `lint` (`verilator --lint-only -Wall`), `sim` (cocotb, `SIM=verilator`
default, `SIM=icarus` override), `waves` (`WAVES=1`), `area` (yosys `stat`), `formal` (sby, optional).
Keep `docs/spec.md` measurable (throughput target, latency, clock) per the paper's spec lesson.

### 4.4 Items needing instructor approval / to state in the report (§7)

- RTL in SystemVerilog: allowed as written ("Verilog, SystemVerilog or PyXHDL"). No approval needed.
- cocotb/Python testbenches, Verilator, Yosys: verification/synthesis *tools*, not an HDL; §7 does
  not restrict tools. State the choice explicitly; ask only if the instructor expects SV testbenches.
- Any use of Amaranth/Migen/Chisel or GateFlow's pre-built IP (`plugins/gateflow/ip/*`, BSL-1.1)
  inside the accelerator would need approval and license citation; plan is to write our own RTL.
- Third-party skill text lives in `.claude/skills/` and must be logged in `prompt.txt` per §10 when
  its instructions shape generated RTL (the auto-logging hook covers prompts, not skill content).

## 5. Things not verified

- Whether Verkor has published VerCore since March 2026 (no repo found).
- Surfer install details (GitLab page fetch returned only metadata); yosys-slang "integrated in
  Yosys 0.67" claim (from its README summary only); OSS CAD Suite Python vs. system venv coexistence
  under WSL2; whether `npx skills add ... -s gf-cocotb` resolves the nested `plugins/gateflow/skills`
  path (the registry lists `codejunkie99/gateflow-plugin@gf-cocotb`, so it should).
- `chuanseng-ng/digital-chip-design-agents` repo metadata (API returned nothing).
