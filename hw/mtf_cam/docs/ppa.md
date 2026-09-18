# mtf_cam — PPA (stage 9)

Method, tools and corner, then the gate artefacts: the Yosys+Liberty area (fast
gate), the OpenLane 2 outcome (post-CTS STA — this design actually converged that
far, unlike grape/huffman), and the design-point trade-off study. Every number cites
its file.

## 0. Method

- **Fast gate:** Yosys (OSS CAD Suite, `Yosys 0.68+130`) `synth -top mtf_cam -flatten`,
  `dfflibmap` + `abc -liberty`, `stat -liberty` against **sky130_fd_sc_hd, tt corner,
  25 °C, 1.80 V** (`hw/tools/pdk/sky130_fd_sc_hd__tt_025C_1v80.lib`). Command:
  `make -C hw/mtf_cam area` → `synth/area.txt` (W=8, the signed-off build).
- **Design points (W-sweep):** `make -C hw/mtf_cam area-sweep` re-maps the same RTL at
  **W ∈ {4,8,16}** via `chparam -set W` in `synth/yosys_area_w{4,8,16}.ys` →
  `synth/area_w{4,8,16}.txt`.
- **Per-module attribution:** a non-flattened `synth -top mtf_cam` + `stat -liberty`
  (`synth/yosys_area_permodule.ys`) → `synth/area_permodule.txt` (each block is
  instantiated once under the top, so local areas attribute the design).
- **Sign-off (bonus):** OpenLane 2.3.10 via Nix, `synth/config.json`, CLOCK_PORT `clk`,
  CLOCK_PERIOD 20.0 ns (MAS §6 / uArch §6 target 50 MHz), SYNTH_HIERARCHY_MODE
  deferred_flatten (grape OOM lesson), GRT_ALLOW_CONGESTION.
- **Clock target:** uArch §6 timing budget — 20 ns period / **50 MHz**.
- Requirement source (project_instructions.md §7 / hw-ppa): a trade-off **discussion
  with a defined operating frequency** ("not expected to synthesize"); OpenLane GDS
  sign-off is **bonus**, not a gate.

## 1. Yosys + sky130 Liberty — area and cell counts (fast gate)

Source: `synth/area.txt` (`make area`, W=8, flattened, Liberty-mapped).

| Metric | Value | Source line |
|---|---|---|
| Cells (Liberty-mapped) | **18,814** | `18814 1.87E+05 cells` |
| Cells (generic, pre-map) | 29,611 | first `stat` block (`29611 cells`) |
| Chip area | **187,389.72 µm² = 0.187 mm²** | `Chip area for module '\mtf_cam'` |
| Sequential fraction | **48.66 %** (91,187.46 µm²) | `used for sequential elements` |
| Flip-flops | 3,455 (`dfxtp_1` 1,255 + `edfxtp_1` 2,200) | cell histogram |

`ppa.cells = 18814`, `ppa.area_um2 = 187390`. The design is **storage-dominated but
small**: the 3,455 mapped flops are the 256×8 shift-register CAM (2,048), the item
FIFO, the packer buffer and the config/counter registers. At 0.187 mm² it sits far
under the PRD **soft** K5/K6 area ceiling of 1.0 mm² (5.3× headroom) — see §2.1.

### 1.1 Area by module (trade-off axis)

Source: `synth/area_permodule.txt` (non-flattened, W=8; hierarchical total
**191,807.7 µm²**, seq 48.46 % — ~2.4 % above the flattened 0.187 mm² because
cross-module optimisation is disabled in this attribution pass).

| Module | Area µm² | % of design | Seq. % | Role |
|---|---:|---:|---:|---|
| `mtf_list` | **130,995.6** | **68.3 %** | 51.0 % | **256-entry shift-register CAM** (256×8 = 2,048 flops) + 256:1 rank read-mux + parallel registered move-to-front shift |
| `mtf_regs` | 17,528.1 | 9.1 % | 45.1 % | CAPS/config/status/counter register file (AXI-Lite backing) |
| `mtf_pack` | 12,409.4 | 6.5 % | 23.2 % | W-lane L-vector packer + beat buffer/`cat` |
| `item_fifo` | 12,289.3 | 6.4 % | 60.8 % | D-deep item FIFO ({is_run,n,byte}) |
| `mtf_cam` (glue) | 9,880.7 | 5.2 % | 34.2 % | top wiring, byte→item path, commit/counters, SVAs |
| `axi_lite_if` | 3,278.1 | 1.7 % | 88.6 % | AXI4-Lite → register bus |
| `mtf_run` | 2,956.6 | 1.5 % | 31.8 % | RLE run counter (RUN_W=21) |
| `mtf_expand` | 1,572.8 | 0.8 % | 38.2 % | run/item → W-byte expander |
| `mtf_ctrl` | 897.1 | 0.5 % | 6.7 % | invocation / init-fill FSM |

**Finding.** `mtf_list` alone is **68 % of the design**, and it is **W-invariant** (the
256×8 CAM does not depend on the output-lane count W). Everything the W knob touches —
`mtf_pack` + `mtf_expand` + `item_fifo` datapath width — is a minority of the area. This
is the whole PPA story of a move-to-front CAM: **it is a 2,048-flop array with a 256:1
read-mux, not a datapath.** Because `mtf_list` has no RAM (the parallel move-to-front
shift needs every entry writable each cycle, uArch §3.2), sky130 realises it as flops.

## 2. Trade-off study (design points)

Knob: **output-lane width W** (uArch §3.3; PRD-F8), the parameter the testplan sweeps
for K3 (block cycles/symbol). The dominant CAM area (`mtf_list`, §1.1) is fixed; W scales
the packer/expander/FIFO datawidth against throughput K3 (lower = better). All three
points are **fully measured** (area from `synth/area_w{4,8,16}.txt`; K3 from
`docs/testplan.md §2` `list_model.cycles` at D=8).

| # | W | Cells | Area µm² | Area mm² | K3 cyc/sym (D=8) | K3 ≤ 1.10? | Verdict |
|---|---|---:|---:|---:|---:|:--:|---|
| 1 | 4 | 18,321 | 181,831.9 | 0.182 | **1.175** | ✗ **fails** | rejected — misses the K3 ≤ 1.10 KPI (testplan: "≤1.10 only from W≥8") |
| **2** | **8** | **18,814** | **187,389.7** | **0.187** | **1.063** | ✓ | **chosen** — smallest build that meets K3 ≤ 1.10; the signed-off default |
| 3 | 16 | 22,250 | 207,826.8 | 0.208 | **1.023** | ✓ | over-provisioned — +11 % area for −0.040 cyc/sym over W=8, not needed |

Marginal cost W=8→W=16: **+3,436 cells (+20,437 µm², +10.9 %)** buys only **−0.040
cyc/sym** (1.063→1.023: 3.8 % fewer cycles = a 3.9 % throughput gain). W=8→W=4 saves just **−493 cells
(−5,558 µm², −3.0 %)** but breaks the KPI. **W=8 is the knee**: the CAM floor (0.131 mm²)
dominates, so shrinking the datapath barely moves total area while it does cost the KPI.

- **Fmax is W-independent.** The critical path (§3.1) is inside the W-invariant
  `mtf_list` CAM read/shift, so the operating frequency does not change across these
  points — the W knob trades **area ↔ K3 cycles**, not Fmax. The 37.6 MHz below applies
  to all three points.

### 2.1 K5/K6 soft area ceiling (1.0 mm²)

The PRD carries a **soft, non-gating** 1.0 mm² area target (testplan K6). The chosen
W=8 build lands at **0.187 mm²** — a **5.3× meet**, and even W=16 (0.208 mm²) is 4.8×
under. Unlike the huffman engine (which missed its 1.0 mm² soft ceiling 1.63× because
it is a 34 kbit flop memory), mtf_cam's single large array is only 2,048 flops, so the
soft ceiling is comfortably met with no SRAM-macro follow-up required.

## 3. OpenLane 2 — sign-off attempt (bonus)

OpenLane 2.3.10 (`synth/config.json`, CLOCK_PERIOD 20.0 ns, deferred_flatten) was given
**one time-boxed attempt**. At ~27 k gates mtf_cam is far smaller than grape (584 k,
which hit OpenROAD **GRT-0607** repeatedly) or huffman (151 k, placement non-convergent):
synthesis completed cleanly (config verified in `synth/runs/signoff/resolved.json`, no
warned-and-ignored variables), and the flow ran all the way through floorplan, placement,
**CTS**, and **post-CTS static timing** — the deepest any module in this project has
driven OpenLane. **No GRT-0607 was seen.** RUN_LINTER was set false (the same bundled-
Verilator `BLKLOOPINIT` issue huffman documented; the RTL-stage `make lint` is clean).

**Why it was closed before GDS.** The post-CTS STA (§3.1) is already decisive, and the
**post-CTS timing-driven resizer** (`32-openroad-resizertimingpostcts`) was
**non-convergent**: 730+ repair iterations oscillating WNS ≈ −30 ns / TNS ≈ −51,000 ps,
all pinned on the same endpoint `u_list._22678_/D` (a CAM flop) — the classic
repair-bloat trajectory that drove huffman's placement and grape's routing into trouble.
Pushing on would sink hours upsizing cells against a W-invariant CAM read-mux path for a
near-certain congested route. Per project_instructions.md §7 (OpenLane sign-off is **not**
required — a trade-off discussion with a defined operating frequency suffices), the run
is closed on the real post-CTS STA below.

### 3.1 Operating frequency — OpenROAD post-CTS STA

Worst setup slack at the 20 ns target, propagated (post-CTS) clock,
`Fmax = 1/(period − ws)`. Source:
`synth/runs/signoff/31-openroad-stamidpnr-1/ws.max.rpt`.

| Stage | Worst setup slack (tt) | Achievable period | Fmax | Note |
|---|---:|---:|:--:|---|
| **post-CTS STA** (`31-openroad-stamidpnr-1`) | **−6.5964 ns** | **26.596 ns** | **≈ 37.6 MHz** | **the operating point** — real clock tree |
| pre-CTS STA (`26-openroad-stamidpnr`) | −217.487 ns | 237.5 ns | ≈ 4.2 MHz | ideal/unbuffered-clock wireload artifact, resolved by CTS — not used |

- **Defined operating frequency: ≈ 37.6 MHz (tt, post-CTS).** The 20 ns / 50 MHz uArch
  §6 target is **missed by ~1.33×**. This is a *real* post-CTS number (propagated clock,
  placed cells), stronger evidence than grape's or huffman's — it is an upper bound only
  in that detailed routing would add net RC.
- **Critical path** (`31-openroad-stamidpnr-1/checks.rpt`): startpoint `u_ctrl._238_`
  (`state_q[0]`, the init-fill FSM) → `init_start` → a **`u_list` `mux2` chain** (the
  256-entry CAM) → endpoint `u_list._22678_/D` (a CAM flop). Data arrival ≈ 26.6 ns
  through the shift-register CAM's mux tree. This is exactly the **256-way read-mux of
  the shift-register CAM** that uArch §6 flagged as the worst path (and its S6 caveat
  that the read-mux fanout / wire load across the 2,048-flop array — not the ~18-gate
  logic depth — would dominate). The optimistic ~100 MHz gate-depth stretch in §6
  becomes **37.6 MHz** once the real fanout, CAM wire load and clock tree are placed —
  the caveat, confirmed.
- **Fmax vs K3.** K3 (cycles/symbol) is frequency-independent; at the chosen W=8 the
  full-benchmark block is 157,560 cycles (`testplan.md §2`, K3 = 1.063). At the 50 MHz
  target that is 3.15 ms (PRD K5, ≈ 25× vs stock MTF); at the **measured 37.6 MHz** it is
  **4.19 ms**. The documented RTL follow-up to reach 50 MHz is to **register the CAM
  read-mux** (pipeline `byte_out = list[r]` into a second stage) — a datapath change
  deferred to a future RTL iteration, not a PPA-stage fix, and it is the same block
  (`mtf_list`) that dominates area, so the area and timing follow-ups coincide.

### 3.2 Power

- **Indicative, not a sign-off figure.** OpenROAD `report_power` at post-CTS (tt) reports
  **≈ 13.7 mW** (`31-openroad-stamidpnr-1/power.rpt`, `power__total: 0.013695`): 49.9 %
  sequential + 46.5 % clock + 3.6 % combinational. With a placed clock tree this is more
  meaningful than a pre-PnR estimate, but it uses **default switching activity** (no
  real VCD), so it is indicative only. Per the task, no power number is invented beyond
  this measured post-CTS report; `ppa.power_mw ≈ 13.7` (post-CTS, default activity).
- **Die shot:** **not obtained** — no GDS was produced (run closed before detailed
  routing), same as grape/huffman.

### 3.3 Honest status summary

| Deliverable | Status |
|---|---|
| Yosys+Liberty area + cell counts | **done** (§1: 18,814 cells, 0.187 mm²) |
| OpenLane synthesis | **done** (clean; config verified in resolved.json) |
| OpenLane placement + CTS | **done** (no GRT-0607; deepest run in this project) |
| Fmax | **post-CTS STA** — ≈ 37.6 MHz tt (§3.1); post-CTS resizer non-convergent, closed before routing |
| Area (OpenLane placed) | not reported — use Yosys 0.187 mm² (§1) |
| Power | **post-CTS indicative** ≈ 13.7 mW (§3.2, default activity) |
| Die shot | **not obtained** (no GDS; not §7-required, not invented) |

## 4. Report §7 mapping

| project_instructions.md §7 bullet | This document |
|---|---|
| Performance / area / power trade-offs | §1 (0.187 mm², 18,814 cells), §1.1 (per-module: CAM = 68 %), §2 (W-sweep trade-off table + K5/K6), §3 (OpenLane/STA operating frequency 37.6 MHz + power) |

Performance (K3 = 1.063 cyc/sym at W=8, block 157,560 cycles) is carried in
`docs/testplan.md §2`; the speedup (≈ 25× vs stock MTF) in the PRD K5 / `hw-integrate`.
Operating frequency ≈ 37.6 MHz (post-CTS STA) here in §3.1, critical path the 256-way
CAM read-mux (uArch §6), fix = register the read-mux path.
