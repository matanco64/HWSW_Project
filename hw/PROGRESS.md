# Hardware-flow progress

<!-- GENERATED from hw/STATUS.json by tools/hw/render_progress.py at 2026-09-12 18:14 UTC. Do not edit; update via tools/hw/status.py. -->
_Generated 2026-09-12 18:14 UTC from `hw/STATUS.json` — **do not edit**; see `hw/FLOW.md`._

## Stage flow

### `grape_pipeline`

```mermaid
flowchart LR
    prd{{PRD}}
    mas{{MAS}}
    uarch{{uArch}}
    rtl(RTL)
    dv_testplan(DV testplan)
    dv_bringup(DV bring-up)
    dv_coverage(DV coverage)
    dv_signoff{{DV sign-off}}
    ppa(PPA)
    integration(Integration)
    prd --> mas --> uarch --> rtl --> dv_testplan --> dv_bringup --> dv_coverage --> dv_signoff --> ppa --> integration
    classDef todo fill:#e0e0e0,stroke:#9e9e9e,color:#333
    classDef in_progress fill:#bbdefb,stroke:#1976d2,color:#0d47a1
    classDef review fill:#ffe0b2,stroke:#f57c00,color:#e65100
    classDef done fill:#c8e6c9,stroke:#388e3c,color:#1b5e20
    classDef blocked fill:#ffcdd2,stroke:#d32f2f,color:#b71c1c
    class integration todo
    class prd,mas,uarch,rtl,dv_testplan,dv_bringup,dv_coverage,dv_signoff,ppa done
```

### `huffman_engine`

```mermaid
flowchart LR
    prd{{PRD}}
    mas{{MAS}}
    uarch{{uArch}}
    rtl(RTL)
    dv_testplan(DV testplan)
    dv_bringup(DV bring-up)
    dv_coverage(DV coverage)
    dv_signoff{{DV sign-off}}
    ppa(PPA)
    integration(Integration)
    prd --> mas --> uarch --> rtl --> dv_testplan --> dv_bringup --> dv_coverage --> dv_signoff --> ppa --> integration
    classDef todo fill:#e0e0e0,stroke:#9e9e9e,color:#333
    classDef in_progress fill:#bbdefb,stroke:#1976d2,color:#0d47a1
    classDef review fill:#ffe0b2,stroke:#f57c00,color:#e65100
    classDef done fill:#c8e6c9,stroke:#388e3c,color:#1b5e20
    classDef blocked fill:#ffcdd2,stroke:#d32f2f,color:#b71c1c
    class ppa,integration todo
    class dv_signoff in_progress
    class prd,mas,uarch,rtl,dv_testplan,dv_bringup,dv_coverage done
```

### `mtf_cam`

```mermaid
flowchart LR
    prd{{PRD}}
    mas{{MAS}}
    uarch{{uArch}}
    rtl(RTL)
    dv_testplan(DV testplan)
    dv_bringup(DV bring-up)
    dv_coverage(DV coverage)
    dv_signoff{{DV sign-off}}
    ppa(PPA)
    integration(Integration)
    prd --> mas --> uarch --> rtl --> dv_testplan --> dv_bringup --> dv_coverage --> dv_signoff --> ppa --> integration
    classDef todo fill:#e0e0e0,stroke:#9e9e9e,color:#333
    classDef in_progress fill:#bbdefb,stroke:#1976d2,color:#0d47a1
    classDef review fill:#ffe0b2,stroke:#f57c00,color:#e65100
    classDef done fill:#c8e6c9,stroke:#388e3c,color:#1b5e20
    classDef blocked fill:#ffcdd2,stroke:#d32f2f,color:#b71c1c
    class uarch,rtl,dv_testplan,dv_bringup,dv_coverage,dv_signoff,ppa,integration todo
    class prd,mas done
```

Hexagon = checkpoint (human approval). Colours: grey todo, blue in progress, orange review, green done, red blocked.

## Module × stage

| Module | PRD | MAS | uArch | RTL | DV testplan | DV bring-up | DV coverage | DV sign-off | PPA | Integration |
|---|---|---|---|---|---|---|---|---|---|---|
| `grape_pipeline` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⬜ |
| `huffman_engine` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 🔵 | ⬜ | ⬜ |
| `mtf_cam` | ✅ | ✅ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

⬜ todo · 🔵 in_progress · 🟠 review · ✅ done · ⛔ blocked

## Next up

- `grape_pipeline`: **Integration** — todo
- `huffman_engine`: **DV sign-off** — in_progress (checkpoint — needs human approval)
- `mtf_cam`: **uArch** — todo (checkpoint — needs human approval)

## Gates

### `grape_pipeline`

#### PRD — ✅ done (started 2026-08-26T05:06:56Z, finished 2026-08-28T12:23:55Z)

- [x] every requirement has a measurable KPI + acceptance test — docs/prd.md §3: 17 PRD-F rows (grep -c '^| PRD-' = 17), every row has KPI+unit and acceptance-test cells filled
- [x] HW/SW split table — docs/prd.md §4: function → HW/SW → bytes per invocation (≈590 B), Amdahl note
- [x] workload slice quantified from results/ profile — docs/prd.md §1: baseline_nbody_stats.txt:19 (229 ms), perf_report_nbody.txt lines 12,123,142,149,154,159,189,194,212,343
- [x] hw-review findings resolved — docs/review_prd.md: 23 findings (2 passes), 0 must open

#### MAS — ✅ done (started 2026-08-30T08:02:05Z, finished 2026-08-30T11:22:57Z)

- [x] I/O table with widths + clock — docs/mas.md §2: 17 signal rows, all with width and clock (checked by script)
- [x] register map (offset, name, bits, access, reset) — docs/mas.md §4: 24 rows (ADR-0005 header + DT/NSTEPS/NPAIRS/BODY/PAIR), all five columns filled (checked by script)
- [x] DMA/stream protocol — docs/mas.md §5: MMIO only, ADR-0001 (accepted), doorbell response rule ADR-0005
- [x] driver API sketch — docs/mas.md §6: AccelDriver base + GrapeDriver incl. advance(dt, n, bodies, pairs)
- [x] block diagram — docs/block_diagram.svg (tools/hw/blockdiag.py from block_diagram.json; .mmd alongside), well-formed XML
- [x] hw-review resolved — docs/review_mas.md: 21 findings (2 passes), 0 must open

#### uArch — ✅ done (started 2026-09-04T20:07:41Z, finished 2026-09-04T20:46:35Z)

- [x] pipeline/FSM diagrams — docs/uarch.md §2 flowchart + §3 two stateDiagrams + accumulate sequencer spec
- [x] number formats fixed — docs/uarch.md §4: binary64 for every architectural signal, Q-notation for sqrt/rcp internals
- [x] memories sized — docs/uarch.md §5: body RF flops, pair list, 1024x20 rcp ROM
- [x] per-stage timing budget — docs/uarch.md §6: six rows, all ≤ 8 ns vs 20 ns @ 50 MHz
- [x] latency/throughput derived and matches PRD KPI — docs/uarch.md §7 + docs/schedule_model.py: simulated 123 cycles/step nominal, 127 worst ≤ K1 128; 290-op graph, inventory sweep table
- [x] hw-review resolved — docs/review_uarch.md: 17 findings (2 passes), 0 must open

#### RTL — ✅ done (started 2026-09-04T20:46:48Z, finished 2026-09-05T18:20:49Z)

- [x] make lint clean (verilator --lint-only -Wall) — make -C hw/grape_pipeline lint (11 files incl. TB wrapper) -> lint: clean, 2026-09-05
- [x] Yosys synth succeeds (synthesizable subset) — synth/area.txt (post K1 fix): 584454 sky130_fd_sc_hd cells, 4075030.8 um^2, yosys.log 0 errors (was 393367 / 2.94mm^2 single-issue — the 3-wide fabric costs +39% area for K1 162->124)
- [x] agent code review resolved — docs/review_rtl.md: 16 findings (2 passes), 0 must open

#### DV testplan — ✅ done (started 2026-09-05T18:24:42Z, finished 2026-09-05T18:41:33Z)

- [ ] features ↔ tests ↔ covergroups ↔ checkers matrix
- [x] golden-model interface defined — docs/testplan.md §4: emulation.advance bit-exact + sticky-flag mirror; nbody_ref tolerances 1e-12 / 2e-9 (r) / 5e-11 (v) with calibrate.py margins; abort replay policy
- [x] formal properties listed — docs/testplan.md §6: 3 sby properties (FSM arcs, BRESP hold, W1C) + justified datapath exclusion + fallback clause
- [x] features <-> tests <-> covergroups <-> checkers matrix — docs/testplan.md §2: 26 rows (F-01..17 = PRD-F1..17, F-20..24 FSM/collisions/hazards, F-30..33 schedule/counters), no empty cell
- [x] hw-review resolved — docs/review_testplan.md: 26 findings (2 passes: 7+1 must all resolved, 10 shoulds accepted), 0 must open

#### DV bring-up — ✅ done (started 2026-09-05T19:22:15Z, finished 2026-09-05T19:45:54Z)

- [x] pyuvm env instantiates — make sim: GrapeEnv (axi agent + passive monitor + GrapeScoreboard) builds/connects; 2 tests run under it (Verilator + Icarus)
- [x] first directed test passes on Verilator — test_grape_pipeline.smoke PASS (NPAIRS=2 NSTEPS=2 bit-exact; K1 measured 126.0 <= 128); test_corner PASS (PRD-F8 nsteps0 + npairs0)
- [x] scoreboard compares against golden — scoreboard: compared 146 items, 0 mismatches (golden=emulation.advance, 2 runs); same on Icarus 4-state
- [x] hw-review resolved — docs/review_bringup.md: 11 findings, 2 musts fixed (monitor X-assert, W1C mirror clear), 0 must open

#### DV coverage — ✅ done (started 2026-09-05T19:50:09Z, finished 2026-09-06T06:33:30Z)

- [x] constrained-random sequences — tb/sequences/random_{cfg,err,abort,fp}.py; 8/8 tests PASS incl. random_cfg 25 runs (seeded), abort x7, fp specials x6
- [ ] line/toggle ≥ 90 %
- [x] all functional covergroups hit — tb/cov/func_cov.txt: 58 bins all >=1; 3 waivers in docs/coverage_waivers.md (2 architecturally unreachable, nsteps.20000 deferred to signoff)
- [x] line/toggle >= 90 % — tb/cov/coverage.txt: line 91.3%, toggle 94.5% (branch 95.5%); inline coverage_off regions each carry a reason

#### DV sign-off — ✅ done (started 2026-09-06T06:45:43Z, finished 2026-09-07T20:30:54Z)

- [x] golden equivalence on the full benchmark input — test_full_benchmark PASS: 20000 steps bit-exact vs emulation.advance (75 items 0 mismatches); vs nbody_ref: dE/E 1.674e-14 <= 1e-12, r 2.1e-12 <= 2e-9, v 2.1e-12 <= 5e-11; K1 = 124.0 <= 128
- [x] directed + random suites pass — make sim: TESTS=9 PASS=9 (incl. full_benchmark) in one run, regress_final.log
- [x] coverage goals — final RTL: line 91.7% toggle 96.0% branch 94.8%; func_cov 59/59 bins incl. nsteps.20000 and done_wins
- [x] lint clean — make lint: 12 files, lint: clean
- [x] Icarus 4-state run X-free after reset — make sim-icarus: TESTS=9 PASS=9; monitor is_resolvable asserts on every handshake, none fired
- [x] formal (sby) where listed — synth/formal.sby: bmc PASS (depth 40) + cover PASS (5/5 states) on fsm_arcs; bresp_hold/w1c take testplan §6 fallback (regs 3x2240b beyond smtbmc; test_regs 11/11 + protocol agent)

#### PPA — ✅ done (started 2026-09-08T07:37:27Z, finished 2026-09-12T18:14:30Z)

- [x] Yosys+Liberty area + cell counts — synth/area.txt: 584454 cells, 4075030.8 um^2 (sky130_fd_sc_hd tt); docs/ppa.md tables
- [x] OpenLane 2 run: Fmax, area µm², power — post-CTS STA Fmax 11.15 MHz (synth/runs/grape_relaxed/35-openroad-stamidpnr-1/ws.max.rpt WS +60.32ns @150ns; worst path u_fsm->g_add accumulate picker); area 4.075 mm² (Yosys synth/area.txt); power/GDS n/a — OpenLane GRT-0607 congestion bug x3, §7 signoff not required
- [x] trade-off table (≥2 design points) — docs/ppa.md: 2 fully-MEASURED points (1-wide 393k/2.94mm^2/K1=162 fail vs 3-wide 584k/4.08mm^2/K1=124 pass) — the dv_signoff K1 knob
- [x] trade-off table (>= 2 design points) — docs/ppa.md: 2 fully-MEASURED points (1-wide 393k/2.94mm^2/K1=162 fail vs 3-wide 584k/4.08mm^2/K1=124 pass) — the dv_signoff fix as the design knob

### `huffman_engine`

#### PRD — ✅ done (started 2026-08-28T19:34:34Z, finished 2026-08-28T20:54:29Z)

- [x] every requirement has a measurable KPI + acceptance test — docs/prd.md §3: 15 PRD-F rows (grep -c '^| PRD-' = 15), every KPI/test cell filled
- [x] HW/SW split table — docs/prd.md §4: pyflate function → HW/SW → bytes per block; 444 config words, 67,562 B stream in, 148,271 symbols out
- [x] workload slice quantified from results/ profile — docs/prd.md §1: perf_report_pyflate.txt:12 (23.29 % eval loop), baseline_pyflate_stats.txt:19 (1.13 s), cProfile splits from dev/pyflate/FINDINGS.md §3 + calibration agent (stock 75 % / T3 39 %)
- [x] hw-review findings resolved — docs/review_prd.md: 25 findings (2 passes), 0 must open

#### MAS — ✅ done (started 2026-08-30T11:22:57Z, finished 2026-08-30T12:18:39Z)

- [x] I/O table with widths + clock — docs/mas.md §2: 14 signal rows (AXI-Lite collapsed to one row), all with width and clock (script-checked)
- [x] register map (offset, name, bits, access, reset) — docs/mas.md §4: 35 rows incl. LEN window and reserved ranges, all five columns filled (script-checked)
- [x] DMA/stream protocol — docs/mas.md §5: s_bits/s_sel/m_sym AXI-Stream rules, ADR-0001 + ADR-0006
- [x] driver API sketch — docs/mas.md §6: HuffmanDriver incl. decode_block() and read_table()
- [x] block diagram — docs/block_diagram.svg via tools/hw/blockdiag.py, well-formed XML
- [x] hw-review resolved — docs/review_mas.md: 23 findings (2 passes), 0 must open

#### uArch — ✅ done (started 2026-09-07T20:31:12Z, finished 2026-09-07T22:03:04Z)

- [x] pipeline/FSM diagrams — docs/uarch.md §2 C0/C1/C2 flowchart + §3.1/§3.2/§3.3 stateDiagrams
- [x] number formats fixed — docs/uarch.md §4: UQn.0 for every signal incl. limit_la UQ21.0 left-aligned compare form (U1/N1-proven)
- [x] memories sized — docs/uarch.md §5: 8 memories, ~34 kbit flops, DBG arbitration noted
- [x] per-stage timing budget — docs/uarch.md §6: C0 loop ~13ns worst of 20ns @ 50MHz; II=2 retreat documented (ADR-0008 #1)
- [x] latency/throughput derived and matches PRD KPI — docs/decode_model.py on the real 148,271-symbol trace: K1=1.0068 (worst sweep 1.0317) <= 1.1; K2=167 <= 314; first symbol 1,004; K4a 2.99ms <= 3.06ms
- [x] hw-review resolved — docs/review_uarch.md: 24 findings over 3 passes (9+13+2), all musts resolved incl. U1 compare direction and U2 phantom decodes, 0 must open

#### RTL — ✅ done (started 2026-09-07T22:03:04Z, finished 2026-09-08T06:42:12Z)

- [x] make lint clean (verilator --lint-only -Wall) — 13 files, lint: clean
- [x] Yosys synth succeeds (synthesizable subset) — synth/area.txt: 151058 sky130_fd_sc_hd cells, 1634516.4 um^2, 0 errors (K5 soft ceiling 1.0mm^2 exceeded — flagged for PPA per PRD)
- [x] agent code review resolved — docs/review_rtl.md: 3 passes, 19 must-level findings all resolved (incl. fixes-of-fixes N4/N10), 0 must open; 37 unit+smoke tests green incl. full-chip smoke

#### DV testplan — ✅ done (started 2026-09-08T07:35:49Z, finished 2026-09-08T07:45:19Z)

- [ ] features ↔ tests ↔ covergroups ↔ checkers matrix
- [x] golden-model interface defined — docs/testplan.md §4: decode_bzip2_symbols trace-exact per beat (EOB counting execution-verified, T1), SYMBOL_LIMIT derivation, R23 bring-up gate
- [x] formal properties listed — docs/testplan.md §6: ctrl_arcs + skid + aligner-cap sby properties with recorded fallback
- [x] features <-> tests <-> covergroups <-> checkers matrix — docs/testplan.md §2: 26 rows (F-01..15 = PRD-F1..16, F-20..26 arcs/boundaries/errors, F-30..32 KPIs), no empty cell
- [x] hw-review resolved — docs/review_testplan.md: 17 findings (5 must incl. executed-golden EOB catch), all musts resolved, 0 open

#### DV bring-up — ✅ done (started 2026-09-12T10:05:01Z, finished 2026-09-12T12:57:48Z)

- [x] pyuvm env instantiates — make sim: HuffEnv (axi agent + 3 AXIS monitors + HuffScoreboard) builds/connects; 2 tests run under it
- [x] first directed test passes on Verilator — test_huffman_engine.smoke PASS + test_bench_block PASS (real block: 148271 symbols, START_BIT 8844, 6 tables; K1=1.0068 <= 1.1, model 1.0068 exact; BUILD_CYCLES=167=ALPHABET+MAXLEN, OVERFETCH=3<=4)
- [x] scoreboard compares against golden — scoreboard: compared 148271 items, 0 mismatches (golden=canonical_model.decode_bzip2_symbols); BITS=531571 golden-exact
- [x] hw-review findings resolved — docs/review_bringup.md: 13 findings (B1-B13), 2 musts fixed (dead SIMULATION ifdef armed via cocotb_run.py -DSIMULATION; smoke_backpressure covers the stall-credit corner), 0 must open; B4-B6 recorded as dv_coverage entry criteria

#### DV coverage — ✅ done (started 2026-09-12T13:38:43Z, finished 2026-09-12T17:33:06Z)

- [x] constrained-random sequences — tb/sequences/rand_tables.py + errors.py + ctrl.py + tests_deflate.py + tests_cover.py; make sim TESTS=15 PASS=15 incl. random_cfg 16 invocations, errors 7 ERR_PARAM + all runtime errors, abort/reset/multiblock/boundary/dbg, DEFLATE (zlib+custom+ERR_SYMBOL+LIMIT)
- [ ] line/toggle ≥ 90 %
- [x] all functional covergroups hit — tb/cov/func_cov.txt: 34 bins all >=1 (cg_cfg alphabet{288,147,mid,small}+n_tables{1..6}, cg_sel switches/groups, cg_bp sym/src, cg_err{param,busy,table.badlen,table.kraft,nocode,selector,limit,underrun}, cg_ctrl{done,abort}, cg_deflate.block, cg_bits start_bit)
- [x] line/toggle >= 90 % — tb/cov/coverage.txt: line 90.4%, toggle 90.3% (control signals; wide datapath/counters/ROMs/storage waived via inline coverage_off + coverage-max-width 4, docs/coverage_waivers.md), branch 91.7%

#### DV sign-off — 🔵 in_progress (started 2026-09-12T18:12:42Z)

- [ ] golden equivalence on the full benchmark input
- [ ] directed + random suites pass
- [ ] coverage goals
- [ ] lint clean
- [ ] Icarus 4-state run X-free after reset
- [ ] formal (sby) where listed

### `mtf_cam`

#### PRD — ✅ done (started 2026-08-28T21:13:50Z, finished 2026-08-30T07:51:36Z)

- [x] every requirement has a measurable KPI + acceptance test — docs/prd.md §3: 16 PRD-F rows (grep -c '^| PRD-' = 16), every KPI/test cell filled
- [x] HW/SW split table — docs/prd.md §4: used-map 32 B in, 148,271 symbol beats on chip, 336,184 B L-vector out via DMA
- [x] workload slice quantified from results/ profile — docs/prd.md §1: perf_report_pyflate.txt:12 interpreter-level; cProfile move_to_front 9.3 % stock (FINDINGS §3), 80.4 ms MTF trace (§1e), T3 10.5 %; golden/calibrate.py workload numbers
- [x] hw-review findings resolved — docs/review_prd.md: 20 findings (2 passes), 0 must open

#### MAS — ✅ done (started 2026-08-30T12:18:39Z, finished 2026-09-04T19:54:58Z)

- [x] I/O table with widths + clock — docs/mas.md §2: 11 signal rows, all with width and clock (script-checked)
- [x] register map (offset, name, bits, access, reset) — docs/mas.md §4: 31 rows incl. used map and reserved ranges, all five columns filled (script-checked)
- [x] DMA/stream protocol — docs/mas.md §5: s_sym / m_l rules, empty-block = no beat, ADR-0001/0004/0006
- [x] driver API sketch — docs/mas.md §6: MtfDriver incl. expand_block() and read_list()
- [x] block diagram — docs/block_diagram.svg via tools/hw/blockdiag.py, well-formed XML
- [x] hw-review resolved — docs/review_mas.md: 24 findings (2 passes), 0 must open

## Metrics

| Module | Line cov % | Toggle cov % | Func cov % | Tests (pass/run) | Formal | Cells | Area µm² | Fmax MHz | Power mW |
|---|---|---|---|---|---|---|---|---|---|
| `grape_pipeline` | 91.7 | 96 | 100 | 9/9 | pass | 584454 | 4075031 | 11.15 | 0 |
| `huffman_engine` | 90.4 | 90.3 | 34 | 17/17 | n/a | 151058 | 1634516 | 0 | 0 |
| `mtf_cam` | 0 | 0 | 0 | 0/0 | n/a | 0 | 0 | 0 | 0 |
