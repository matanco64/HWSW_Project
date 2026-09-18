# mtf_cam — preserved physical-design evidence

`synth/runs/` is gitignored (each OpenLane run is hundreds of MB). These are verbatim copies of the
small report files that the numbers in `docs/ppa.md` and `hw/docs/hardware_report.md` are read from.

- OpenLane 2.3.10, run tag `signoff`, step `31-openroad-stamidpnr-1` (post-CTS static timing), corner nom_tt_025C_1v80
- clock constraint: 20 ns; config: `synth/config.json`
- **Fmax: 37.6 MHz = 1/(20 + 6.5964) ns**
- copied 2026-09-19 from `hw/mtf_cam/synth/runs/signoff/31-openroad-stamidpnr-1/`

Files:
- `ws.max.rpt`
- `power.rpt`
- `worst_setup_path.rpt` — first path block of checks.rpt

Regenerate: `. ~/.nix-profile/etc/profile.d/nix.sh && cd hw/mtf_cam && openlane --run-tag <tag> <config>` (stops after post-CTS; no GDS).
