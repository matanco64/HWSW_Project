# Hardware plan — all steps

Flow: `PRD → MAS → uArch → RTL → DV[testplan → bring-up → coverage closure → sign-off] → PPA → HW/SW integration`
(defined in [FLOW.md](FLOW.md)). Live status: [PROGRESS.md](PROGRESS.md) (generated from `STATUS.json`).
Run a module through its next stage with `/hw-flow <module>`.

Legend: ☐ todo · ☑ done · ◆ human checkpoint (design review / sign-off)

## Phase 0 — Infrastructure

- [x] Research: agent skills + toolchain (`research/hw-agent-skills-and-toolchain.md`)
- [x] Research: algorithms — nbody/GRAPE, pyflate bzip2+DEFLATE (`research/hw-algorithms-*.md`)
- [x] Import skills: `claude-skill-verilog`, `gf-cocotb`, `tb-best-practices`
- [x] Toolchain: `./hw/setup.sh` → OSS CAD Suite (Verilator ≥ 5.036, Yosys, Icarus, sby), `hw/.venv` (cocotb 2.0, pyuvm), sky130 Liberty
- [x] Scaffold: `hw/common/` (Makefile.cocotb, shared RTL cells, pyuvm base classes), three module skeletons
- [x] Tracking: `hw/STATUS.json`, `tools/hw/status.py`, `render_progress.py`, `gh_sync.py`
- [x] Hooks: SV lint on edit, STATUS render, friction log, golden guard, progress injection, stop reminder
- [x] Skills: `hw-flow`, `hw-prd`, `hw-mas`, `hw-uarch`, `hw-rtl`, `hw-dv-testplan`, `hw-dv-bringup`, `hw-dv-signoff`, `hw-ppa`, `hw-integrate`, `hw-review`, `hw-status`, `hw-advisor`
- [x] **Gate:** smoke test — `make -C hw/common lint sim cov area` green on `skid_buffer`; `PROGRESS.md` renders; every hook verified with a synthetic payload
- [ ] Optional: `./hw/setup.sh --with-openlane` → `openlane --version`; smoke design to GDS

## Phase 1 — Lockstep PRD + MAS (all three modules)

**Resume here:** `/hw-flow grape_pipeline` (MAS #1 of the lockstep round; shared bus/clock/driver ADRs). Live state: `hw/PROGRESS.md`.

Shared decisions taken once and recorded as ADRs under `hw/docs/adr/`: bus (AXI-Lite MMIO + DMA
descriptors vs streaming), clock target, driver model, block-diagram conventions, number-format policy.

| Step | grape_pipeline | huffman_engine | mtf_cam |
|---|---|---|---|
| PRD (`hw-prd`, grilled) | ☑ 2026-08-28 | ☑ 2026-08-28 | ☑ 2026-08-30 |
| `hw-review` spec pre-read | ☑ 23 findings | ☑ 25 findings | ☑ 20 findings |
| ◆ PRD design review | ☑ approved | ☑ approved | ☑ approved |
| MAS (`hw-mas`) + block diagram | ☐ | ☐ | ☐ |
| `hw-review` spec pre-read | ☐ | ☐ | ☐ |
| ◆ MAS design review | ☐ | ☐ | ☐ |

PRD agenda seeds (from research): grape_pipeline — KPI = cycles/step (serial 20,000-step chain),
FP64 datapath, energy-tolerance oracle, pair-list input; huffman_engine — KPI = symbols/cycle,
bzip2 + DEFLATE modes, table build in HW from code lengths; mtf_cam — 1 sym/cycle, chained
RUNA/RUNB expander, L-vector output. Inverse BWT is a documented non-target.

## Phase 2 — Module by module: `grape_pipeline` → `huffman_engine` → `mtf_cam`

Per module, in order (repeat the block three times):

- [ ] uArch (`hw-uarch`): pipelines, FSMs, number formats, memories, timing budget → `hw-review` → ◆ uArch review
- [ ] RTL (`hw-rtl`): `rtl/*.sv`, `make lint` clean, Yosys synth OK → agent code review (`hw-review` RTL mode)
- [ ] DV testplan (`hw-dv-testplan`): features ↔ tests ↔ covergroups ↔ checkers; golden-model interface; formal properties
- [ ] Golden model: instrument `benchmarks/bm_*` code → trace dumps into `golden/` (then frozen by hook)
- [ ] DV bring-up (`hw-dv-bringup`): pyuvm env, first directed test green on Verilator
- [ ] DV coverage closure (`hw-dv-signoff`): constrained-random, line/toggle ≥ 90 %, all covergroups hit
- [ ] ◆ DV sign-off: full-benchmark golden equivalence, Icarus X-free, formal where listed, lint clean
- [ ] PPA (`hw-ppa`): `make area` (Yosys + sky130) → OpenLane 2 → `docs/ppa.md` with ≥ 2 design points
- [ ] Integration (`hw-integrate`): driver model, speedup estimate vs baseline, report §7 mapping
- [ ] `hw-advisor` retro after each gate → `hw/docs/lessons.md`

Module-specific design points to carry through uArch → PPA:

- **grape_pipeline:** rsqrt option (ROM+NR vs SRT sqrt + NR reciprocal vs full FP64 units); one pipe
  vs replicated; optional fixed-point-position variant for area comparison.
- **huffman_engine:** comparator cascade (baseline) vs 2-level LUT (comparison point); 6 vs 2 table
  register sets; aligner width.
- **mtf_cam:** shift-register CAM vs RAM + rank counters; sby proof of the permutation invariant.

## Phase 3 — PPA sign-off

- [ ] OpenLane 2 runs for all three modules; Fmax, area µm², power in `docs/ppa.md`
- [ ] Trade-off tables (performance vs area vs frequency vs power) per module
- [ ] Die shots for the presentation

## Phase 4 — Report and presentation feed

- [ ] Map each module's docs to rubric §7 bullets (see FLOW.md "Rubric mapping") and into
      `report_nbody.txt` / `report_pyflate.txt` section 5
- [ ] `PROGRESS.md` snapshots + Mermaid diagrams reused in slides
- [ ] Stretch: scaled-n nbody demo — software Barnes–Hut/FMM tree walk feeding the pair-list engine;
      report the crossover
- [ ] Stretch: DEFLATE LZ77 copy engine (32 KB window) if area allows
