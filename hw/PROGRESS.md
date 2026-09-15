# Hardware-flow progress

<!-- GENERATED from hw/STATUS.json by tools/hw/render_progress.py at 2026-09-15 15:00 UTC. Do not edit; update via tools/hw/status.py. -->
_Generated 2026-09-15 15:00 UTC from `hw/STATUS.json` — **do not edit**; see `hw/FLOW.md`._

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
    class prd,mas,uarch,rtl,dv_testplan,dv_bringup,dv_coverage,dv_signoff,ppa,integration done
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
    class prd,mas,uarch,rtl,dv_testplan,dv_bringup,dv_coverage,dv_signoff,ppa,integration done
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
    class prd,mas,uarch,rtl,dv_testplan,dv_bringup,dv_coverage,dv_signoff,ppa,integration done
```

Hexagon = checkpoint (human approval). Colours: grey todo, blue in progress, orange review, green done, red blocked.

## Module × stage

| Module | PRD | MAS | uArch | RTL | DV testplan | DV bring-up | DV coverage | DV sign-off | PPA | Integration |
|---|---|---|---|---|---|---|---|---|---|---|
| `grape_pipeline` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `huffman_engine` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `mtf_cam` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

⬜ todo · 🔵 in_progress · 🟠 review · ✅ done · ⛔ blocked

## Next up

- `grape_pipeline`: all stages done
- `huffman_engine`: all stages done
- `mtf_cam`: all stages done

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

#### Integration — ✅ done (started 2026-09-12T18:19:16Z, finished 2026-09-12T18:19:22Z)

- [x] register map ↔ driver model consistent — driver/check_regmap.py -> 0 differences (15 rows vs docs/mas.md §4, ID_VALUE 0x47525031); driver/test_driver.py -> ALL 4 PASS (full advance = 2,480,000 cycles)
- [x] cycle-accurate speedup estimate vs results/baseline_* — docs/integration.md §3: T=231ms (results/baseline_nbody_stats.txt), f=0.95, cycles=2.48M (124 cyc/step), Fmax — Amdahl 3.78-4.45x @50MHz PRD target, ~1.0x @ achievable 11.15 MHz (accumulate-picker path); ideal 20x, sensitivity rows
- [x] report §7 bullets mapped — docs/integration.md §4: 7 §7 bullets each mapped to a file/section (rtl/, mas §2/§3/§6/§7, uarch, prd+integration §3, ppa)

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

#### DV sign-off — ✅ done (started 2026-09-12T18:12:42Z, finished 2026-09-12T18:59:21Z)

- [x] golden equivalence on the full benchmark input — test_bench_block PASS: the entire benchmark (interpreter.tar.bz2 = 1 bzip2 block, 148271 symbols, START_BIT 8844, 6 tables) trace-exact vs canonical_model (148271 beats, 0 mismatches); BITS 531571, K1=1.0068<=1.1; multi-block contract via test_multiblock
- [x] directed + random suites pass — make sim: TESTS=17 PASS=17 FAIL=0 (smoke, backpressure, bench_block, random_cfg/busy, errors_reject/runtime, abort, reset, multiblock, sel_boundary, dbg, first_latency, deflate, deflate_all_codes, deep_tree, cover_fill)
- [x] coverage goals — dv_coverage gate: func 34/34, line 90.4%, branch 91.7%, toggle 90.3% (control-subset, coverage_waivers.md)
- [x] lint clean — make lint: clean (12 files)
- [x] Icarus 4-state run X-free after reset — make sim-icarus: TESTS=17 PASS=17; AXIS/AXI monitors assert is_resolvable on every handshake+beat field after reset, none fired
- [x] formal (sby) where listed — synth/formal.sby: ctrl_arcs (FSM arcs+termination) + skid (no loss/dup, PRD-F6) BMC+cover 4/4 PASS; aligner 128b-cap property takes testplan §6 documented fallback (aligner unit TB 13/13 + AXIS protocol agent)
- [x] hw-review findings resolved — docs/review_signoff.md: 5 findings (S1-S5), 0 must; S2 (DEFLATE underrun beat suppression) + S3/S4 (dead code) + S5 (explicit c1 reset) fixed, S1 considered+rejected (fix broke ERR valid-beat delivery, caught by regression); re-verified 17/17 both sims + formal 4/4

#### PPA — ✅ done (started 2026-09-12T19:01:55Z, finished 2026-09-12T19:41:16Z)

- [x] Yosys+Liberty area + cell counts — synth/area.txt: 151,058 cells; Chip area 1,634,516 um2 (1.634 mm2); 54.44% sequential
- [x] OpenLane 2 run: Fmax, area µm², power — OpenLane 2.3.10 one attempt: synthesis clean, reached pre-PnR STA + global placement. Fmax pre-PnR tt ~8.9 MHz (ws -91.886ns @ 20ns, synth/runs/signoff2/08-openroad-staprepnr/nom_tt_025C_1v80/max.rpt); crit path table-build/symtab (u_regs->u_tab). Area Yosys 1.634 mm2; power/die shot not obtained (no GDS, non-convergent placement, §7-optional, not invented). docs/ppa.md §3
- [x] trade-off table (≥2 design points) — docs/ppa.md §2: 3 design points (flop symtab as-built 1.634 mm2 / SRAM-macro symtab / 2-vs-6 table sets) + per-module area breakdown synth/area_permodule.txt (huff_tables 67% + huff_regs 28%)
- [x] trade-off table (>= 2 design points) — docs/ppa.md 2 Trade-off: 3 design points (flop symtab as-built / SRAM-macro symtab / 2-vs-6 table sets) + per-module area breakdown synth/area_permodule.txt
- [x] OpenLane 2 run: Fmax, area um2, power — OpenLane 2.3.10 one time-boxed attempt: synthesis clean + all checkers passed (better than grape OOM); reached OpenROAD pre-PnR STA + global placement. Fmax from pre-PnR STA synth/runs/signoff2/08-openroad-staprepnr/nom_tt_025C_1v80/max.rpt: ws -91.886ns @ 20ns -> ~8.9 MHz tt (pre-placement, upper bound); crit path u_regs->u_tab (table-build/symtab mux, not decode cascade). Area = Yosys 1.634 mm2 (OpenLane not placed). Power/die shot not obtained (no GDS; placement non-convergent, closed per proj_instructions.md §7); power not invented. docs/ppa.md §3

#### Integration — ✅ done (started 2026-09-12T19:41:55Z, finished 2026-09-12T19:42:07Z)

- [x] register map ↔ driver model consistent — driver/check_regmap.py -> 0 differences (20 rows vs docs/mas.md §4, ID 0x48554631); driver/test_driver.py -> ALL 5 DRIVER TESTS PASS (regmap, ID, cycle-model==decode_model.py, decode_block golden sink, ERR_PARAM)
- [x] cycle-accurate speedup estimate vs results/baseline_* — docs/integration.md §3: T=1.13s (baseline_pyflate_stats.txt:19), f=0.496 (prd.md §1 Huffman+bit-reader slice), HW 149,276 cyc (decode_model.py, K1=1.0068), Amdahl S≈1.97x @50MHz (ideal 1.98x); clock-insensitive 1.89-1.97x across 5-50 MHz
- [x] report §7 bullets mapped — docs/integration.md §4: 7 project_instructions.md §7 bullets each mapped to a path (RTL/MAS/uArch/driver/PRD+integration/block_diagram/ppa)

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

#### uArch — ✅ done (started 2026-09-12T19:01:12Z, finished 2026-09-12T20:14:50Z)

- [x] pipeline/FSM diagrams — docs/uarch.md §2 dataflow flowchart + §3 invocation/expander stateDiagrams + §3.2 list-CAM datapath
- [x] number formats fixed — docs/uarch.md §4: UQ8.0 rank/byte, UQ22.0 run sum (21b stored), UQ31.0 in-flight bytes, counters per MAS §4
- [x] memories sized — docs/uarch.md §5: 256x8 shift-register CAM (2048 flops), item FIFO Dx30b 2W/1R, packer Wx8, no macros
- [x] per-stage timing budget — docs/uarch.md §6: 6 rows, worst = 256:1 list read mux ~6-8ns < 20ns @ 50MHz; K4 PPA-measured
- [x] latency/throughput derived and matches PRD KPI — docs/uarch.md §7 + docs/schedule_model.py: golden list_model.cycles reproduces K3=1.063 @ W8/D8 <=1.10, D-sweep + W-table match PRD; K1 latency <=8
- [x] hw-review resolved — docs/review_uarch.md: 12 findings, 3 must (M1 run-adder width, M2 FIFO 2W port for K3, M3 enqueue-after-check) all fixed, 0 must open

#### RTL — ✅ done

- [x] make lint clean (verilator --lint-only -Wall) — make -C hw/mtf_cam lint: clean, 9 files incl axi_lite_if
- [x] Yosys synth succeeds (synthesizable subset) — yosys read_verilog -sv + synth -top mtf_cam: 0 errors, no latches, ~30k generic cells
- [x] agent code review resolved — docs/review_rtl.md: R1-R5, 1 must (MAX_RUN per-invocation reset) FIXED (inv_clr wired to doorbell), 0 must open; R2 -> dv_bringup

#### DV testplan — ✅ done (started 2026-09-12T20:48:21Z, finished 2026-09-12T20:54:17Z)

- [ ] features ↔ tests ↔ covergroups ↔ checkers matrix
- [x] golden-model interface defined — docs/testplan.md §2: mtf_ref golden (==libbzip2) + list_model.expand predictor + list_model.cycles K3 model; DUT-vs-predictor per beat, predictor-vs-golden per block; numbers reproduced (145/147, 148271 syms, 336184 B, 42023 beats, K3 1.063)
- [x] formal properties listed — docs/testplan.md §3: 3 mtf_list invariants (permutation/lookup/shift) N_LIST=16 induction + 256 bounded, + handshake props (formal/*.sby)
- [x] features <-> tests <-> covergroups <-> checkers matrix — docs/testplan.md §1: 29 rows (F1-F16 + K1-K8 + F-20..24), no empty cell
- [x] hw-review resolved — spot-review: matrix complete/no empty cells, golden reproduced-by-execution, R2 (K3 model-vs-DUT) -> F-21 bring-up task, R1 MAX_RUN -> F-22 multiblock, W=4 K3>1.10 correctly PPA-only per F8

#### DV bring-up — ✅ done (started 2026-09-12T21:17:23Z, finished 2026-09-12T21:22:18Z)

- [x] pyuvm env instantiates — make sim: MtfEnv (AxiLiteAgent + s_sym source + m_l sink + 2 AXIS monitors + MtfScoreboard) build/connect complete; 6 tests run under it on Verilator + Icarus
- [x] first directed test passes on Verilator — make sim TESTCASE=smoke PASS (used {65,66,67,68}, L=AAABCB); TESTS=6 PASS=6 FAIL=0 (smoke, smoke_backpressure, backpressure, multiblock, k1, full_benchmark)
- [x] scoreboard compares against golden — scoreboard PASS: compared 336184 items over 1 block, 0 mismatches (golden=list_model.expand, cross-checked == mtf_ref.l_vector); docs/review_bringup.md 1 finding 0 must open

#### DV coverage — ✅ done (started 2026-09-12T22:22:27Z, finished 2026-09-13T06:13:57Z)

- [x] constrained-random sequences — tb/sequences/random_streams.py (seeded, SEED= logged, golden-round-tripped); make sim TESTCASE=test_random PASS; full suite 16/16 PASS (10 new: random, corner, driver, err_underrun/rank/eob/limit, run_max, reset, xinv)
- [ ] line/toggle ≥ 90 %
- [x] all functional covergroups hit — tb/cov/func_cov.txt: 129 bins across 21 testplan covergroups, every bin >= 1; waived cg_caps.w_4/w_16/n_list_16, cg_k2/k3.w_4/w_16, cg_k3.gt_1p10 (separate param builds / failure-only bin, testplan F-08/K2/K3); cg_fml deferred to formal at dv_signoff
- [x] line/toggle >= 90 % — make cov (COVERAGE_MAX_WIDTH=4) firsthand: line 92.0% (104/113), toggle 93.8% control-subset (720/768), branch 96.8% (184/190); wide-datapath toggle waived (mtf_list 256x8 CAM, 256-bit used_map, lifetime counters) per docs/coverage_waivers.md — huffman precedent; 9 uncovered lines are unreachable defensive RTL (FSM default, fill else-arm, abort+doorbell corner, SVA decls)

#### DV sign-off — ✅ done (started 2026-09-13T06:15:12Z, finished 2026-09-13T15:10:24Z)

- [x] golden equivalence on the full benchmark input — test_full_benchmark PASS (in make sim 16/16): 148,271 symbols -> L-vector 336,184 B byte-exact vs golden list_model.expand (predictor pre-checked == mtf_ref.l_vector), scoreboard 0 mismatches; BYTES_OUT=336,184 INIT_CYCLES=145 MAX_RUN=8,157
- [x] directed + random suites pass — make sim firsthand: TESTS=16 PASS=16 FAIL=0 (smoke, backpressure x2, multiblock, k1, full_benchmark, random, corner, err_underrun/rank/eob/limit, run_max, reset, xinv, driver)
- [x] coverage goals — dv_coverage gate: line 92.0% toggle 93.8% (control-subset) branch 96.8%; func_cov 129 bins across 21 testplan covergroups all >=1 (docs/coverage_waivers.md)
- [x] lint clean — make lint firsthand: all rtl + axi_lite_if, -Wall, lint: clean, 0 warnings
- [x] Icarus 4-state run X-free after reset — make sim-icarus firsthand: TESTS=16 PASS=16; monitor is_resolvable asserts on every AXIS/AXI handshake, none fired -> no X after reset
- [x] formal (sby) where listed — make formal firsthand: 7/7 tasks PASS. K8: (a) 3 list invariants proven UNBOUNDED k-induction @ N_LIST=16; (b) N_LIST=256 permutation preservation across 24 move cycles (bmc256moves, MEETS PRD-K8 depth>=20) via fill-abstraction (valid post-fill start collapses the 256-deep encoder; concrete 8-entry canonical occupancy, moves free -- sound because move logic is value-agnostic, non-vacuity via famoves_cover + mutation test); (c) general permutation depth 6 (bmc). Unbounded-at-256 honestly not achievable (SAT-hard), not faked. Details docs/review_signoff.md + synth/formal.sby
- [x] hw-review findings resolved — docs/review_signoff.md: RTL-mode over final rtl/+tb/+formal/; 0 must open; stale-worktree R1 (INIT_CYCLES) reconciled non-applicable via nused256; formal non-vacuous (CEX-driven + slang frontend avoids bind-vacuity)

#### PPA — ✅ done (started 2026-09-13T15:11:59Z, finished 2026-09-13T15:35:00Z)

- [x] Yosys+Liberty area + cell counts — synth/area.txt (reproduced firsthand via make area): 18,814 sky130_fd_sc_hd cells, 187,389.72 um^2 (0.187 mm^2) @ W=8; mtf_list CAM = 68% (W-invariant); per-module in area_permodule.txt
- [x] OpenLane 2 run: Fmax, area µm², power — OpenLane converged through post-CTS STA (no GRT-0607, deepest run in project): synth/runs/signoff/31-openroad-stamidpnr-1/ws.max.rpt worst setup slack -6.5964 ns @ 20ns tt -> 26.596 ns -> Fmax ~37.6 MHz; critical path = mtf_list CAM read-mux (confirms uArch §6); power ~13.7 mW post-CTS indicative; closed before GDS (resizer non-convergent, time-boxed per §7)
- [x] trade-off table (≥2 design points) — docs/ppa.md §2: 3 design points W=4/8/16 (18,321/18,814/22,250 cells; 181,832/187,390/207,827 um^2; K3 1.175/1.063/1.023) -> W=8 chosen (smallest meeting K3<=1.10); 5.3x under 1.0mm^2 soft ceiling

#### Integration — ✅ done (started 2026-09-13T15:35:33Z, finished 2026-09-13T15:51:57Z)

- [x] register map ↔ driver model consistent — driver/check_regmap.py firsthand: 0 differences (18 rows, driver == mas.md §4 == rtl/mtf_regs.sv, ID 'MTF1'); driver/test_driver.py: ALL 5 driver-model tests PASS (regmap, id/caps, full_expand, err_param, err_busy); tb/test_driver_model.py RTL-cosim 0 mismatches; make sim still 16/16
- [x] cycle-accurate speedup estimate vs results/baseline_* — docs/integration.md §3: T=1.12s (baseline_pyflate_stats.txt), f=0.1344 (move_to_front share), t_hw=158,441 cyc / 37.6 MHz = 4.214 ms -> Amdahl S~1.15x, ideal 1/(1-f)=1.155x; reconciles with PRD K5 stage-level ~25x (25x on a 13.4% slice = 1.148x end-to-end)
- [x] report §7 bullets mapped — docs/integration.md §4 rubric map: all 7 project_instructions.md §7 bullets each mapped to file+section; §5 has report_pyflate.txt paste text

## Metrics

| Module | Line cov % | Toggle cov % | Func cov % | Tests (pass/run) | Formal | Cells | Area µm² | Fmax MHz | Power mW |
|---|---|---|---|---|---|---|---|---|---|
| `grape_pipeline` | 91.7 | 96 | 100 | 9/9 | pass | 584454 | 4075031 | 19.46 | 0 |
| `huffman_engine` | 90.4 | 90.3 | 34 | 17/17 | 4 | 151058 | 1634516 | 8.9 | 0 |
| `mtf_cam` | 92 | 93.8 | 129 | 16/16 | pass | 18814 | 187390 | 37.6 | 13.7 |
