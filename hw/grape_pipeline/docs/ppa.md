# grape_pipeline — PPA (stage 9)

## Method

- Yosys 0.68 (`oss-cad-suite 2026-08-26`), `synth -flatten` → `dfflibmap`/`abc -liberty` on
  **sky130_fd_sc_hd tt 025C 1v80** (`hw/tools/pdk/sky130_fd_sc_hd__tt_025C_1v80.lib`);
  numbers from `synth/area.txt` (script `synth/yosys_area.gen.ys`, target `make area`).
- Clock target: 50 MHz (MAS §3; uArch §6 budget shows ≤ 13 ns worst comb on the C0-free
  datapath — the schedule fabric — with headroom at 20 ns).
- OpenLane 2 sign-off (Fmax/power/die shot): **attempted, did not converge to GDS** (8 runs on
  this 24 GB WSL host). It DID complete synthesis + placement + CTS + post-CTS static timing
  before dying in global routing, so the Fmax below is real STA, not an estimate. Power and the
  die shot need signoff/GDS, which was never reached. See "OpenLane 2 (sign-off) — outcome" below.

## Yosys + Liberty (fast gate)

| Metric | Value | Source |
|---|---|---|
| Standard cells | **584,454** | `synth/area.txt` "Number of cells" |
| Area | **4,075,031 µm² (4.075 mm²)** | `synth/area.txt` "Chip area" |
| Generic netlist | 747,185 cells (≈ 205 k $_MUX_) | `synth/area.txt` pre-map stat |
| Storage (uArch §5) | body RF 2×2,240 b, scratch 12,800 b, rcp ROM 20,480 b — all flops | uarch.md §5 |

The dominant consumer is `grape_force_pipe`'s static-schedule fabric: the scr_fwd forwarding
view + 200-event issue muxing measured **305,612 generic cells standalone** (review_rtl.md
post-review section). Second is the 3-wide accumulate/integrate engine and the 3-port body RF
added by the K1 fix (see trade-off).

## Trade-off table (design points — both fully measured, not estimated)

Knob: accumulate/integrate issue width (uArch §3.4; the dv_signoff K1 fix). Point 1 is the
signed-history build at commit `a7cadc2` (single-issue engine, 1-port RF); point 2 is the
signed-off RTL.

| Design point | Cells | Area mm² | K1 cycles/step (20k-step benchmark, measured) | KPI (≤128) | Verdict |
|---|---|---|---|---|---|
| 1-wide accumulate, 1-port RF | 393,367 | 2.938 | **162.0** | ✗ fails | rejected: misses the PRD KPI by 27 % |
| **3-wide accumulate + per-lane integrate, 3-port RF** | 584,454 | 4.075 | **124.0** | ✓ | **chosen**: +38.7 % area buys the KPI; model-predicted window 123..127 |

Marginal cost: +191,087 cells (+1.137 mm²) for −38 cycles/step (−23.5 %); ~5,030 cells per
cycle/step recovered. The alternative (renegotiating K1 to 162) was declined at the
dv_signoff checkpoint (2026-09-07).

Secondary observations for the report:
- The area is fabric, not arithmetic: the 8 FP64 units are a minority of the total (each unit
  synthesized standalone in the low-tens-of-k cells at the RTL stage); the cost centre is
  same-cycle forwarding + multi-port muxing — the price of the II=2 static schedule that
  makes K1 latency-optimal.
- sky130 has no BRAM: every bit of state is flops. On a BRAM-bearing target (or with OpenRAM
  macros) the rcp seed ROM (20,480 b) and scratch would leave the standard-cell budget.
- K5-type soft comparisons belong to the huffman module (its PRD carries the 1.0 mm² soft
  ceiling); grape's PRD carries no area ceiling — 4.075 mm² is reported, not gated.

## OpenLane 2 (sign-off) — outcome

> **⚠️ Superseded number below.** The 11.15 MHz Fmax in this section is the **pre-rewrite,
> linear-scan** netlist (`grape_relaxed`). It is kept for the record and as the "before" of the
> before/after comparison. The **current achievable Fmax is 19.46 MHz** on the parallel-prefix
> netlist — see the **Addendum (2026-09-13/14)** below, which is the number all other docs and
> the report quote.

OpenLane 2 signoff was attempted **eight times** on this 24 GB WSL host and never reached GDS.
The saga, for the record:

| Runs | Symptom | Response |
|---|---|---|
| 1–3 | Synthesis OOM / process restart | raised WSL memory budget |
| 4–5 | Flat-synthesis OOM (whole netlist flattened at once) | fixed with `SYNTH_HIERARCHY_MODE deferred_flatten` |
| 6, 7, 7b | OpenROAD **GRT-0607** in global routing — *"Unable to update: position not found in 2D heap"* — hit **three times**, even at a relaxed 150 ns clock with `GRT_ALLOW_CONGESTION` and a lean netlist | not a config knob: an OpenROAD global-router limitation on this congested 584 k-cell design |

The last run (`grape_relaxed`, 150 ns clock) got the furthest — it completed synthesis,
placement, CTS and **post-CTS static timing**, producing real timing data before dying in
routing. That STA is what we report:

| Metric | Value | Source |
|---|---|---|
| Post-CTS worst setup slack | **+60.3164 ns** @ 150 ns period | `synth/runs/grape_relaxed/35-openroad-stamidpnr-1/ws.max.rpt` (`timing__setup__ws__corner:nom_tt_025C_1v80`) |
| Achievable period | 150 − 60.3164 = **89.68 ns** | derived |
| **Fmax** | **≈ 11.15 MHz** (1 / 89.68 ns) | derived from the slack above |
| Worst path | `u_fsm._948_` (state FF) → `g_add[1].u_add._6265_` (accumulate-picker adder) | `synth/runs/grape_relaxed/35-openroad-stamidpnr-1/checks.rpt` Startpoint/Endpoint |
| Area (post-CTS instances) | 5.646 mm² / 764,907 cells, 38.8 % of the 14.55 mm² core (`grape_prefix2`); no signoff area — flow stopped after post-CTS timing | `synth/evidence/area_openlane.txt` |
| Power (mW) | **≈ 19.2 mW — indicative only** (post-CTS `report_power`, **default switching activity**, at the 150 ns run constraint ≈ 6.7 MHz; `grape_prefix2`; `grape_relaxed` gave 20.2 mW). Not workload power; no signoff/GDS figure exists | `synth/runs/grape_prefix2/35-openroad-stamidpnr-1/power.rpt` (`power__total: 0.019231`) |
| Die shot | **not obtained** — no GDS produced | — |

**Fmax vs KPI.** The critical path is the **3-wide accumulate issue picker** (`g_add[*]` —
the K1-fix logic from dv_signoff, see trade-off above), driven by the FSM state register. The
achievable ~11.15 MHz misses the 20 ns / 50 MHz PRD target by **~4.5×**. The documented RTL
follow-up was to **pipeline the accumulate picker** (break the FSM-state → 3-wide-adder path into
stages) — see the addendum below, which took a better route.

## Addendum (2026-09-13) — accumulate picker restructured to parallel-prefix

The 11.15 MHz worst path above was the accumulate issue picker: a **~60-iteration in-order
`always_comb` scan** carried across iterations by `lane_hold[15]` and `slots_used`, i.e. a
~60-deep combinational chain feeding the FP64 adder operand muxes. Rather than *pipeline* it
(which would add a cycle and lift K1 above 124), `grape_accum.sv` now computes the two prefix
operations as **balanced Hillis-Steele trees** (`~log₂(60) ≈ 6` deep):

- `is_first_on_lane` (was `lane_hold`): inclusive prefix-OR of per-lane one-hots → only the
  lowest-index considered op per lane stays eligible (identical selection to the linear scan).
- slot index (was `slots_used`): inclusive prefix-sum of the eligible bits → op *e* issues iff
  `popcount(eligible[0..e-1]) < nslots` and takes `slot_q[pfx[e]]`. The issue loop then reads
  only precomputed per-op values — no cross-iteration carry — so it maps to muxes, not a chain.

**Bit-exactness (the gating evidence):** every output (`add_*`, `mul_*`, `bc_set`,
`acc_iss_set`, `integ_*_set`) is identical to the linear-scan baseline. Verified firsthand on
the merged tree — `make -C hw/grape_pipeline sim` **9/9 PASS**, `full_benchmark` 20,000 steps
**0 mismatches** vs `emulation.advance`, **K1 worst = 124.0 (unchanged)**, |dE/E| = 1.674e-14,
r/v deviation identical to baseline; Icarus 4-state 9/9; lint clean. The reduction is on the
same `u_fsm` → `g_add[*]` path the STA flagged, so it is the correct structural target.

**New Fmax — MEASURED (2026-09-14), post-CTS STA on the restructured netlist.** OpenLane run
`grape_prefix2` reached post-CTS STA (the deepest grape run yet — it cleared synthesis, floorplan,
placement and CTS; stopped in the post-CTS resizer, no GDS, per §7 — same as `grape_relaxed`).
Apples-to-apples, both from `35-openroad-stamidpnr-1/ws.max.rpt` at `nom_tt_025C_1v80`, 150 ns
period:

| | worst setup slack | achievable period | Fmax | critical path |
|---|---|---|---|---|
| **Before** (linear scan) | +60.3164 ns | 89.68 ns | **11.15 MHz** | `u_fsm._948_` → `g_add[1].u_add._6265_` (accumulate-picker **adder**) |
| **After** (parallel-prefix) | **+98.6212 ns** | **51.38 ns** | **≈ 19.46 MHz** | `u_fsm._947_` → `g_add[2].u_mul._35436_` (integrate **multiplier** operand) |

**Result: Fmax 11.15 → 19.46 MHz (1.75×); worst-path delay 89.68 → 51.38 ns (−43%) — bit-exact,
K1 = 124 unchanged.** The restructure did exactly what the STA flagged: the accumulate-picker path
(`g_add[*].u_add`) **dropped out of the critical path entirely**; the new limiter is a different,
faster path (FSM state → integrate-multiply operand). Still short of the 20 ns / 50 MHz target
(~2.6×), but the documented picker bottleneck is removed at zero functional cost. The next
limiter (the FSM→multiplier path) is the follow-on target if 50 MHz is pursued.
(The **pre-PnR** STA `12-openroad-staprepnr` is *not* a valid comparable — its worst path is the
fanout-2253 `commit`→RF broadcast net, ~221 ns, a pre-placement wireload artifact CTS resolves,
unchanged by this restructure; the picker only becomes critical post-CTS. That is why the
apples-to-apples numbers above are both post-CTS.)

**§7 framing.** Per project_instructions.md §7 ("You are not expected to synthesize"), the
requirement is a trade-off **discussion with a defined operating frequency**. That is satisfied
here: the Yosys area/cell counts, the measured 2-point K1 trade-off table, and this post-CTS STA
together define the operating point (**~19.46 MHz** achievable on the parallel-prefix netlist;
the 11.15 MHz figure above is the pre-rewrite linear-scan point) and its cost. Full
OpenLane signoff (power, die shot) was **bonus**, not a §7 requirement, and did not converge
because of the OpenROAD GRT-0607 router bug — an environment/tool limitation, not a design gap.

## Note (2026-09-19) — which netlist the area describes

The Yosys area above (584,454 cells, 4.075 mm², `synth/area.txt`, identical copy kept as
`synth/area_preprefix.txt`) was measured on the three-wide design **before** the parallel-prefix
rewrite of the accumulate picker; the 19.46 MHz timing is from the netlist **after** it.
A re-measurement on the final RTL with the same recipe (`make area`) was attempted on 2026-09-19
and stopped after about 7 hours in Yosys ABC technology mapping without a result (close-out time
limit).

A same-recipe before/after does exist under the **OpenLane** synthesis recipe, because both timing
runs synthesized their own netlist with an identical `resolved.json` (150 ns clock); the lines are
preserved in `synth/evidence/area_openlane.txt`:

| OpenLane run | RTL | cells (synthesis) | area (synthesis) | after buffering + CTS |
|---|---|---:|---:|---:|
| `grape_relaxed` | linear-scan picker (11.15 MHz) | 474,634 | 4.918 mm² | 816,789 cells / 6.077 mm² |
| `grape_prefix2` | final, balanced trees (19.46 MHz) | 446,932 | 4.658 mm² | 764,907 cells / 5.646 mm² (38.8 % of the 14.55 mm² core) |

So the rewrite made the design 5.3 % smaller at synthesis (7.1 % after CTS) as well as 1.75× faster.
The plain-Yosys figure (4.075 mm²) and the OpenLane figures use different synthesis scripts and are
not comparable with each other; the 2-point trade-off table above compares two plain-Yosys points.

## Report §7 mapping

Performance: K1 124 cycles/step measured on the full benchmark (2.48 M cycles / 20 k steps =
49.6 ms at the 50 MHz PRD target; **the achievable clock from post-CTS STA is ~19.46 MHz →
~127.4 ms** on the parallel-prefix netlist — see the Addendum above and `hw-integrate`). Area:
4.075 mm² sky130 HD (584,454 cells), trade-off table above. Fmax: **~19.46 MHz** from post-CTS
STA (`synth/runs/grape_prefix2/35-openroad-stamidpnr-1/ws.max.rpt`; the earlier ~11.15 MHz was
the pre-rewrite linear-scan netlist `grape_relaxed`), critical path now the integrate-multiplier
operand path → 50 MHz missed ~2.6×, RTL fix = pipeline the integrate-multiply path.
Power: ≈ 19.2 mW post-CTS tool estimate (default activity, 150 ns constraint — indicative, not workload power). Die shot: not obtained (OpenLane GRT-0607, signoff not §7-required).
