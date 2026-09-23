# mtf_cam — preserved physical-design evidence

`synth/runs/` is gitignored (each OpenLane run is hundreds of MB). These are verbatim copies of the
small report files that the numbers in `docs/ppa.md` and `hw/docs/hardware_report.md` are read from.

**Operating point (met constraint).** OpenLane 2.3.10, run tag `signoff_tight`, step
`31-openroad-stamidpnr-1` (post-CTS static timing), corner nom_tt_025C_1v80
- clock constraint: 27 ns; config: `synth/config_tight.json`
- worst setup slack **+0.3066 ns**, worst hold slack +0.1950 ns — timing met
- **Fmax: 37.46 MHz = 1/(27 − 0.3066) ns**
- critical path `u_ctrl._238_` → `u_list._22678_/D` (the same CAM-flop endpoint as the 20 ns run)
- power estimate 10.2 mW (default switching activity at the 27 ns constraint; indicative)
- copied 2026-09-24 from `hw/mtf_cam/synth/runs/signoff_tight/31-openroad-stamidpnr-1/`

Files: `tight27_ws.max.rpt`, `tight27_ws.min.rpt`, `tight27_power.rpt`,
`tight27_worst_setup_path.rpt` (first path block of checks.rpt).

**Earlier run (constraint not met), kept as the second evidence point.** Run tag `signoff`,
same step and corner
- clock constraint: 20 ns; config: `synth/config.json`
- worst setup slack **−6.5964 ns**: the design *failed* its 50 MHz constraint; the
  back-computed 1/(20 + 6.5964) ns = 37.6 MHz agrees with the met-constraint run within 0.4 %
- copied 2026-09-19 from `hw/mtf_cam/synth/runs/signoff/31-openroad-stamidpnr-1/`

Files: `ws.max.rpt`, `power.rpt` (13.7 mW at the 20 ns constraint), `worst_setup_path.rpt`.

Regenerate: `. ~/.nix-profile/etc/profile.d/nix.sh && cd hw/mtf_cam && openlane --run-tag <tag> <config>` (stops after post-CTS; no GDS).
