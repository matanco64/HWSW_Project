# Hardware-flow progress

<!-- GENERATED from hw/STATUS.json by tools/hw/render_progress.py at 2026-09-05 18:20 UTC. Do not edit; update via tools/hw/status.py. -->
_Generated 2026-09-05 18:20 UTC from `hw/STATUS.json` — **do not edit**; see `hw/FLOW.md`._

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
    class dv_testplan,dv_bringup,dv_coverage,dv_signoff,ppa,integration todo
    class prd,mas,uarch,rtl done
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
    class uarch,rtl,dv_testplan,dv_bringup,dv_coverage,dv_signoff,ppa,integration todo
    class prd,mas done
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
| `grape_pipeline` | ✅ | ✅ | ✅ | ✅ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| `huffman_engine` | ✅ | ✅ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| `mtf_cam` | ✅ | ✅ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

⬜ todo · 🔵 in_progress · 🟠 review · ✅ done · ⛔ blocked

## Next up

- `grape_pipeline`: **DV testplan** — todo
- `huffman_engine`: **uArch** — todo (checkpoint — needs human approval)
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
- [x] Yosys synth succeeds (synthesizable subset) — synth/area.txt: 393367 sky130_fd_sc_hd cells, 2938435.7 um^2; yosys.log 0 errors (full flatten, post scr_fwd synthesizability fixes)
- [x] agent code review resolved — docs/review_rtl.md: 16 findings (2 passes), 0 must open

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
| `grape_pipeline` | 0 | 0 | 0 | 0/0 | n/a | 393367 | 2938436 | 0 | 0 |
| `huffman_engine` | 0 | 0 | 0 | 0/0 | n/a | 0 | 0 | 0 | 0 |
| `mtf_cam` | 0 | 0 | 0 | 0/0 | n/a | 0 | 0 | 0 | 0 |
