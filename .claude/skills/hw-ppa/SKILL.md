---
name: hw-ppa
description: Measure performance, power and area of a signed-off accelerator module with Yosys+sky130 and OpenLane 2, and write the trade-off study (stage 9 of hw/FLOW.md). Use when hw-flow reaches ppa or the user asks for area, Fmax, power, a die shot, or a design-point comparison.
---

# hw-ppa — stage 9, PPA

Inputs: signed-off `rtl/`, `docs/uarch.md` (parameters = design knobs, timing budget), `docs/prd.md`
KPI. Outputs: `hw/<module>/docs/ppa.md`, `hw/<module>/synth/` (`yosys.ys`, `area.txt`,
`config.json`, `runs/`), die shot PNG for the presentation. Toolchain: `hw/FLOW.md` "Toolchain"
(sky130_fd_sc_hd tt 25 °C 1.8 V; OpenLane 2 via `hw/setup.sh --with-openlane`).

## Procedure

1. `python3 tools/hw/status.py set <module> ppa in_progress`.
2. **Fast gate — Yosys + Liberty.** `make -C hw/<module> area` runs `synth/yosys.ys`
   (`read_verilog -sv`, `synth -top <module>_top`, `dfflibmap`/`abc -liberty`, `stat -liberty`)
   → `synth/area.txt`: cell count, cell-type histogram, area µm². Record `ppa.cells`,
   `ppa.area_um2`.
3. **Design points.** Choose ≥ 2 parameter sets from `uarch.md` knobs (e.g. `grape_pipeline`: NR
   iterations 1 vs 2, pipeline depth; `huffman_engine`: 2 vs 6 table register sets, comparator
   width; `mtf_cam`: shift-register CAM vs RAM+shift). Run step 2 per point with
   `make area PARAMS="-D..."`; keep each `area_<point>.txt`.
4. **Sign-off numbers — OpenLane 2.** Write `synth/config.json` (`DESIGN_NAME`, `VERILOG_FILES`,
   `CLOCK_PORT`, `CLOCK_PERIOD` from MAS, `FP_CORE_UTIL`). Run `make -C hw/<module> openlane`
   (= `openlane synth/config.json`). Read `synth/runs/<run>/final/metrics.json`:
   `timing__setup__ws` → Fmax = 1/(period − ws); `design__instance__area`; `power__total`
   (from the STA/power step); DRC/LVS counts. Record `ppa.fmax_mhz`, `ppa.power_mw`.
5. **Die shot.** `final/gds` rendered with klayout (`klayout -z -rd input=... -r
   tools/hw/dieshot.py`) or OpenLane's `openlane --last-run --flow ... view`; save
   `docs/dieshot_<module>.png`.
6. **Write `docs/ppa.md`**: method (tools, corner, clock); Yosys table; OpenLane table; trade-off
   table (design point | cells | area µm² | Fmax | power | KPI cycles/step or sym/cycle |
   verdict); the chosen point and why; utilisation and routing notes; mapping to report §7
   "performance/area/power trade-offs" bullet. Every number cites its file.
7. Record gate rows; `set ... done`.

## Gate (FLOW.md row 9)

| Criterion | Evidence |
|---|---|
| Yosys+Liberty area + cell counts | `synth/area.txt` (`Chip area` and `Number of cells` lines) |
| OpenLane 2 run: Fmax, area µm², power | `synth/runs/<run>/final/metrics.json` keys quoted |
| trade-off table (≥ 2 design points) | `docs/ppa.md §Trade-off` — row count |

```
cd "$(git rev-parse --show-toplevel)"
python3 tools/hw/status.py gate <module> ppa "<criterion>" pass "<evidence>"   # ×3
python3 tools/hw/status.py metric <module> ppa.<cells|area_um2|fmax_mhz|power_mw> <v>
python3 tools/hw/status.py set <module> ppa done
```
