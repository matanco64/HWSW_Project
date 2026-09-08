# grape_pipeline — PPA (stage 9)

## Method

- Yosys 0.68 (`oss-cad-suite 2026-08-26`), `synth -flatten` → `dfflibmap`/`abc -liberty` on
  **sky130_fd_sc_hd tt 025C 1v80** (`hw/tools/pdk/sky130_fd_sc_hd__tt_025C_1v80.lib`);
  numbers from `synth/area.txt` (script `synth/yosys_area.gen.ys`, target `make area`).
- Clock target: 50 MHz (MAS §3; uArch §6 budget shows ≤ 13 ns worst comb on the C0-free
  datapath — the schedule fabric — with headroom at 20 ns).
- OpenLane 2 sign-off (Fmax/power/die shot): **pending toolchain install** (`hw/setup.sh
  --with-openlane` = Nix + flake; needs an interactive install). This section is completed
  when that lands; the gate row records the state honestly.

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

## OpenLane 2 (sign-off) — pending

`synth/config.json` prepared (DESIGN_NAME grape_pipeline, CLOCK_PORT clk, CLOCK_PERIOD 20.0);
run `make -C hw/grape_pipeline openlane` once `hw/setup.sh --with-openlane` has been executed
(interactive Nix install). Then: Fmax = 1/(20 ns − ws), `design__instance__area`,
`power__total`, DRC/LVS counts, and `docs/dieshot_grape_pipeline.png` via klayout — recorded
here and in STATUS metrics.

## Report §7 mapping

Performance: K1 124 cycles/step measured on the full benchmark (2.48 M cycles / 20 k steps =
49.6 ms @ 50 MHz for the compute; SW baseline comparison in `hw-integrate`). Area: 4.075 mm²
sky130 HD, trade-off table above. Power: OpenLane pending.
