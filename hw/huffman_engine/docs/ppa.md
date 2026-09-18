# huffman_engine — PPA (stage 9)

Method, tools and corner, then the three gate artefacts: the Yosys+Liberty area
(fast gate), the OpenLane 2 outcome (or the STA fallback, honestly reported like
grape), and the design-point trade-off study. Every number cites its file.

## 0. Method

- **Fast gate:** Yosys (OSS CAD Suite nightly 2026-08-26) `synth -top huffman_engine
  -flatten`, `dfflibmap` + `abc -liberty`, `stat -liberty` against **sky130_fd_sc_hd,
  tt corner, 25 °C, 1.80 V** (`hw/tools/pdk/sky130_fd_sc_hd__tt_025C_1v80.lib`).
  Command: `make -C hw/huffman_engine area` → `synth/area.txt`.
- **Per-module attribution:** a second, non-flattened `synth -top huffman_engine`
  + `stat -liberty` per submodule → `synth/area_permodule.txt` (each block is
  instantiated once under the top, so local areas sum to the design).
- **Sign-off (bonus):** OpenLane 2.3.10 via Nix, SYNTH_HIERARCHY_MODE deferred_flatten (grape
  OOM lesson). Two configs: `synth/config.json` (CLOCK_PERIOD 20.0 ns = MAS K3 50 MHz — placement
  non-convergent) and **`synth/config_confirm.json` (40 ns, FP_CORE_UTIL 35)** which converged
  through post-CTS STA (the reported operating point, §3 — relaxing the clock is grape's lesson).
- **Clock target:** MAS §6 timing budget, K3 ≥ 50 MHz (20 ns period).
- Requirement source (project_instructions.md §7 / hw-ppa): a trade-off **discussion
  with a defined operating frequency**; OpenLane GDS sign-off is bonus, not a gate.

## 1. Yosys + sky130 Liberty — area and cell counts (fast gate)

Source: `synth/area.txt` (`make area`, flattened, Liberty-mapped).

| Metric | Value | Source line |
|---|---|---|
| Cells | **151,058** | `Number of cells` |
| Chip area | **1,634,516 µm² = 1.634 mm²** | `Chip area for module '\huffman_engine'` |
| Sequential fraction | **54.44 %** (889,783 µm²) | `used for sequential elements` |
| Flip-flops | 33,228 (`dfxtp_1` 10,791 + `edfxtp_1` 22,437) | cell histogram |

`ppa.cells = 151058`, `ppa.area_um2 = 1634516`. The design is **storage-dominated**:
over half the area is registers (the symtab + table register sets + length window,
uArch §5, ≈ 34 kbit of flops), matching the "control/storage-heavy comparator
cascade" characterisation.

### 1.1 Area by module (trade-off axis)

Source: `synth/area_permodule.txt` (non-flattened; hierarchical total 1,733,396 µm²
— ~6 % above the flattened 1.634 mm² because cross-module optimisation is disabled
in this attribution pass).

| Module | Area µm² | % of design | Seq. % | Role |
|---|---:|---:|---:|---|
| `huff_tables` | **1,163,561** | **67.1 %** | 61 % | symtab (1,728×10b) + 6 table register sets + active-set mux |
| `huff_regs` | **483,470** | **27.9 %** | 41 % | length window (6×288×5b = 8.6 kbit) + counters + config + FSM regs |
| `huff_builder` | 28,780 | 1.7 % | 71 % | PREFIX/FILL build datapath |
| `huff_decoder` | 22,420 | 1.3 % | **0 %** | 20×21b comparator cascade + priority encode (pure combinational) |
| `huff_aligner` | 14,643 | 0.8 % | 29 % | 64b window + barrel shifter + FIFO |
| `huffman_engine` (glue) | 10,460 | 0.6 % | 34 % | top wiring, stall fan-out, SVAs |
| `axi_lite_if` | 3,278 | 0.2 % | 89 % | AXI4-Lite → register bus |
| `huff_deflate` | 2,919 | 0.2 % | 35 % | DEFLATE resolve + extra bits |
| `huff_out` | 2,506 | 0.1 % | 68 % | output skid, withdrawal |
| `huff_selector` | 748 | <0.1 % | 51 % | 50-symbol selector FSM |
| `huff_ctrl` | 611 | <0.1 % | 43 % | invocation FSM |

**Finding.** `huff_tables` + `huff_regs` = **95 % of the design**, and both are
storage. The actual decode logic — the comparator cascade `huff_decoder` — is only
**1.3 %** and carries **zero** sequential area. This is the whole PPA story of a
canonical-Huffman engine: it is a memory, not a datapath.

## 2. Trade-off study (design points)

Knob: **how the per-table/symbol storage is realised** — the dominant area axis
identified in §1.1. The RTL bakes six table register sets + a flop symtab
(`SYMTAB_DEPTH = 1728`, `huff_tables.sv`) for the signed-off **0-cycle selector
switch** (PRD-F1, uArch §3.3); the K1 = 1.0068 throughput is invariant across these
points (storage organisation, not the decode loop). Point 1 is fully measured;
points 2–3 are projections from the measured per-module storage area.

| # | Design point | Area | K1 cyc/sym | K5 (≤1.0 mm²) | Verdict |
|---|---|---:|---:|:--:|---|
| **1** | **As-built:** flop symtab + 6 register sets, sky130_fd_sc_hd | **1.634 mm²** (measured, §1) | **1.0068** (`decode_model.py`) | **miss** (1.63×) | signed-off; 0-cycle switch, no macros needed |
| 2 | Symtab (17.3 kbit) + length window (8.6 kbit) in **SRAM macros** | ≈ **0.75 mm²** std cells + 2 SRAMs (proj.) | 1.0068 (symtab read already a registered C1 stage) | **meets** | needs an SRAM compiler — **not in the sky130 HD open flow** |
| 3 | **2** table register sets instead of 6 (re-derive on switch) | ≈ 1.53 mm² (proj.; −~0.1 mm² of table-set flops) | **>1.1** (build stall per 50-symbol switch) | miss | **rejected** — breaks the K1 KPI and PRD-F1 0-cycle switch |

### 2.1 K5 soft-ceiling discussion (1.0 mm²)

The PRD carries a **soft** K5 area target of 1.0 mm²; the design lands at **1.634 mm²
(1.63×)**. This is expected and it is a *storage* miss, not a logic miss:

- **54.44 % of the area is sequential** (889,783 µm²). The combinational decode
  datapath is negligible (`huff_decoder` 1.3 %, 0 % seq).
- The storage is (uArch §5): symtab **1,728 × 10 b = 17.3 kbit**, length window
  **6 × 288 × 5 b = 8.6 kbit**, six table register sets (limit_la/first_code/base/
  eob) **≈ 6.4 kbit**, count bins **1.1 kbit** — ≈ **34 kbit of flip-flops**. At
  sky130 HD (~20–30 µm² per flop bit) that alone is ~0.7–1.0 mm².
- **What it would take to hit 1.0 mm²:** move the symtab (17.3 kbit) and the length
  window (8.6 kbit) — the two large, single-port-friendly arrays — out of standard-
  cell flops into **compiled SRAM macros** (point 2). On a target with an SRAM
  compiler or FPGA BRAM they become one/two small dense blocks and the standard-cell
  budget drops to the decode + control + the six table register sets (kept as flops
  for the 0-cycle active-set mux), projecting **under 1.0 mm²**.
- **Why we did not:** **sky130_fd_sc_hd in this open flow has no BRAM/SRAM macro** —
  the flow is standard cells only, so every array is flops. The 1,728×10b symtab +
  6×20-entry table params therefore consume the standard-cell budget by construction.
  K5 is a *soft* ceiling for exactly this trade-off discussion; the achievable path
  (SRAM macros) is documented above and is the concrete area-reduction follow-up.

## 3. OpenLane 2 — sign-off attempt (bonus)

OpenLane 2.3.10 (deferred_flatten) was run on this 24 GB WSL host. Unlike grape (which OOM'd
in synthesis until `deferred_flatten` and then hit OpenROAD **GRT-0607** three times), huffman
at 151 k cells is ~4× smaller: **synthesis completed cleanly**, all yosys/netlist checkers
passed. The one config adjustment was `RUN_LINTER: false` — OpenLane's bundled Verilator 5.018
rejects a `BLKLOOPINIT` construct (delayed array write in a for-loop) that the project's pinned
Verilator ≥ 5.036 accepts (the RTL-stage `make lint` is clean); the design RTL was unchanged.

**Two runs, and the key lesson.** The first run (`signoff2`, `synth/config.json`, **20 ns**
clock) reached only **pre-PnR STA** before global placement went **non-convergent** — 2,200+
Nesterov iterations, overflow stuck at ~0.29, the timing-driven resizer bloating HPWL 5→8.8×10⁹
chasing an impossible 20 ns target. That is the same repair-bloat trajectory that drove grape
into GRT-0607. **The fix (grape's lesson) is to relax the clock so the resizer is not chasing an
unachievable target:** a second run (`signoff_confirm`, `synth/config_confirm.json`, **40 ns**
clock, FP_CORE_UTIL 35) **converged cleanly through floorplan, placement, CTS and post-CTS STA**
— the same depth mtf_cam reached — with **no setup or hold violations**. The number below is that
**post-CTS STA**, which *supersedes* the earlier pre-PnR estimate.

> **The pre-PnR 8.9 MHz was a high-fanout-net wireload artifact, not the real timing.** At
> pre-PnR the worst path's ~111 ns arrival was dominated by a single high-fanout net
> (`u_regs._86086_/Q` driving thousands of `u_build` pins) with no clock tree and unbuffered
> net RC — the OpenLane `violator_list` at global placement shows this net as the top offender.
> This is the **same class of artifact as grape's pre-PnR fanout-2253 broadcast net (~221 ns)**.
> Once CTS buffers that net into a tree (post-CTS), the real timing emerges — and it is
> **faster**, not slower, than the pre-PnR estimate. So huffman moves from *pre-placement* to
> *post-CTS* evidence, matching grape and mtf_cam.

Per project_instructions.md §7 (OpenLane GDS sign-off is **not** required — a trade-off
discussion with a defined operating frequency suffices), the run is closed on the post-CTS STA
below (it went one step further, into the post-CTS resizer + global routing, then stopped —
same as grape/mtf; no GDS).

### 3.1 Operating frequency — OpenROAD post-CTS STA

Worst **setup** slack at the **40 ns** constraint, propagated post-CTS clock,
`Fmax = 1/(period − ws)`. Source: `synth/runs/signoff_confirm/31-openroad-stamidpnr-1/max.rpt`
(setup) and `min.rpt` (hold); the worst path of each is preserved in the tracked folder
`synth/evidence/` (`worst_setup_path.rpt`, `worst_hold_path.rpt`, `power.rpt`).

| Stage | Worst setup slack (tt) | Achievable period | **Fmax** | Note |
|---|---:|---:|:--:|---|
| **post-CTS STA** (`31-openroad-stamidpnr-1`, 40 ns) | **+14.941 ns** | **25.06 ns** | **≈ 39.9 MHz** | **the operating point** — all 1,000 reported worst setup paths MET; hold met (worst +0.156 ns) |
| post-CTS STA, looser run (`signoff_relaxed`, 120 ns) | +88.43 ns | 31.57 ns | ≈ 31.7 MHz | same netlist source, looser constraint: the timing-driven resizer does less work, so the estimate is lower — brackets the result |
| pre-PnR STA (`signoff2/08-staprepnr`, 20 ns) | −91.886 ns | 111.886 ns | ≈ 8.9 MHz | **superseded** — high-fanout wireload artifact (see box above) |

> **Correction (2026-09-19).** An earlier revision of this section reported **25.1 MHz**, derived
> from "+0.156 ns worst register-to-register slack". That +0.156 ns is the worst **hold** slack
> (`min.rpt`), misread as a setup slack; the worst **setup** slack is +14.941 ns (`max.rpt`). The
> critical path and the "269,517 paths" count quoted there were wrong for the same reason. The
> figures in this section are re-derived from `max.rpt` directly and the evidence is preserved in
> `synth/evidence/`. (Coincidence to beware: the achievable *period* is 25.06 ns.)

- **Defined operating frequency: ≈ 39.9 MHz (tt, post-CTS, 40 ns constraint).** The 20 ns /
  50 MHz K3 target is **missed by ~1.25×** (not the ~5.6× the pre-PnR artifact suggested). This
  is a post-CTS number (propagated clock, placed cells, no setup or hold violations); it is an
  estimate in that the constraint (40 ns) is looser than the result (25 ns) — a tighter
  constraint changes how hard the resizer works (a 27 ns confirmation run, `signoff_tight`, is
  recorded below when complete) — and detailed routing would add net RC.
- **Critical path** (post-CTS setup): startpoint `u_regs._86212_` (a `huff_regs` length/count
  register) → endpoint `u_align._3147_` (a `huff_aligner` window register), slack +14.941 ns.
  The same `huff_regs` start register led the pre-PnR critical path; once CTS buffered the
  `huff_tables` build net the limiter is the `huff_regs → huff_aligner` control path. The
  documented RTL follow-up to reach 50 MHz remains to **pipeline the table build** and
  **register the wide control fan-out from `huff_regs`** — the same storage blocks that dominate
  area, so area and timing follow-ups coincide.

### 3.2 Power

- **Post-CTS indicative.** OpenROAD `report_power` at post-CTS (tt, 40 ns run) reports
  **≈ 283 mW** (`signoff_confirm/31-openroad-stamidpnr-1/power.rpt`, `power__total: 0.28315`):
  51 % internal + 49 % switching. With a placed clock tree this is far more meaningful than the
  pre-PnR estimate, but it uses **default switching activity** (no real VCD) at the run's 40 ns
  (40 ns = 25 MHz) run constraint, so it is indicative only and scales with clock (the looser 120 ns
  `signoff_relaxed` run reported ≈ 98 mW at its 8.3 MHz constraint — consistent, power ∝ freq).
  `ppa.power_mw ≈ 283` (post-CTS, default activity, 40 ns).
- **Die shot:** **not obtained** — no GDS was produced (run closed after post-CTS, before
  detailed routing), same as grape/mtf.

### 3.3 Honest status summary

| Deliverable | Status |
|---|---|
| Yosys+Liberty area + cell counts | **done** (§1: 151,058 cells, 1.634 mm²) |
| OpenLane synthesis | **done** (clean; passed all checkers) |
| OpenLane placement + CTS | **done** (`signoff_confirm`, 40 ns; converged, 0 setup violations) |
| Fmax | **post-CTS STA** — ≈ 39.9 MHz tt (§3.1, 40 ns constraint); supersedes the pre-PnR 8.9 MHz artifact |
| Area (OpenLane placed) | not reported — use Yosys 1.634 mm² (§1) |
| Power | **post-CTS indicative** ≈ 283 mW (§3.2, default activity, 40 ns) |
| Die shot | **not obtained** (no GDS; not §7-required, not invented) |

## 4. Report §7 mapping

| project_instructions.md §7 bullet | This document |
|---|---|
| Performance / area / power trade-offs | §1 (1.634 mm², 151,058 cells), §1.1 (per-module), §2 (trade-off table + K5), §3 (OpenLane/STA operating frequency) |

Performance (K1 = 1.0068 cyc/sym) is carried in `docs/uarch.md §7` and the speedup in
`docs/integration.md §3`; Fmax operating point in §3 here.
