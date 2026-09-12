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
| Area (post-place, µm²) | not reported — OpenLane never reached signoff; use Yosys 4.075 mm² (§ Yosys) | — |
| Power (mW) | **not obtained** — needs signoff/GDS, never reached | — |
| Die shot | **not obtained** — no GDS produced | — |

**Fmax vs KPI.** The critical path is the **3-wide accumulate issue picker** (`g_add[*]` —
the K1-fix logic from dv_signoff, see trade-off above), driven by the FSM state register. The
achievable ~11.15 MHz misses the 20 ns / 50 MHz PRD target by **~4.5×**. The documented RTL
follow-up is to **pipeline the accumulate picker** (break the FSM-state → 3-wide-adder path into
stages); that is a datapath change deferred to a future RTL iteration, not a PPA-stage fix.

**§7 framing.** Per project_instructions.md §7 ("You are not expected to synthesize"), the
requirement is a trade-off **discussion with a defined operating frequency**. That is satisfied
here: the Yosys area/cell counts, the measured 2-point K1 trade-off table, and this post-CTS STA
together define the operating point (~11.15 MHz achievable on this netlist) and its cost. Full
OpenLane signoff (power, die shot) was **bonus**, not a §7 requirement, and did not converge
because of the OpenROAD GRT-0607 router bug — an environment/tool limitation, not a design gap.

## Report §7 mapping

Performance: K1 124 cycles/step measured on the full benchmark (2.48 M cycles / 20 k steps =
49.6 ms at the 50 MHz PRD target; **but the achievable clock from post-CTS STA is ~11.15 MHz →
~225 ms** — both quoted in `hw-integrate`). Area: 4.075 mm² sky130 HD, trade-off table above.
Fmax: ~11.15 MHz from post-CTS STA (`synth/runs/grape_relaxed/35-openroad-stamidpnr-1/ws.max.rpt`),
critical path the accumulate picker → 50 MHz missed ~4.5×, RTL fix = pipeline the picker.
Power/die shot: not obtained (OpenLane GRT-0607, signoff not §7-required).
