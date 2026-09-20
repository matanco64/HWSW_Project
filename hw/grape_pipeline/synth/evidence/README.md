# grape_pipeline — preserved physical-design evidence

`synth/runs/` is gitignored (each OpenLane run is hundreds of MB). These are verbatim copies of the
small report files that the numbers in `docs/ppa.md` and `hw/docs/hardware_report.md` are read from.

- OpenLane 2.3.10, run tag `grape_prefix2`, step `35-openroad-stamidpnr-1` (post-CTS static timing), corner nom_tt_025C_1v80
- clock constraint: 150 ns; config: `synth/config.json (CLOCK_PERIOD overridden to 150 for this run; see runs/<tag>/resolved.json locally)`
- **Fmax: 19.46 MHz = 1/(150 - 98.6212) ns**
- copied 2026-09-19 from `hw/grape_pipeline/synth/runs/grape_prefix2/35-openroad-stamidpnr-1/`

Files:
- `ws.max.rpt`
- `power.rpt`
- `worst_setup_path.rpt` — first path block of checks.rpt
- `area_openlane.txt` — cell count and area of the pre-rewrite (`grape_relaxed`) and final (`grape_prefix2`) netlists under the identical OpenLane recipe: synthesis `stat.rpt` lines and the post-CTS `or_metrics_out.json` values
- `ws.max.before_prefix_rewrite.rpt` — run grape_relaxed, the 11.15 MHz linear-scan netlist, for the before/after in docs/ppa.md

Regenerate: `. ~/.nix-profile/etc/profile.d/nix.sh && cd hw/grape_pipeline && openlane --run-tag <tag> <config>` (stops after post-CTS; no GDS).
