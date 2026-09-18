# huffman_engine — preserved physical-design evidence

`synth/runs/` is gitignored (each OpenLane run is hundreds of MB). These are verbatim copies of the
small report files that the numbers in `docs/ppa.md` and `hw/docs/hardware_report.md` are read from.

- OpenLane 2.3.10, run tag `signoff_confirm`, step `31-openroad-stamidpnr-1` (post-CTS static timing), corner nom_tt_025C_1v80
- clock constraint: 40 ns; config: `synth/config_confirm.json`
- **Fmax: 39.9 MHz = 1/(40 - 14.941) ns** — worst *setup* slack +14.941 ns (`worst_setup_path.rpt`, first path of `max.rpt`; all 1,000 reported worst paths MET). Worst *hold* slack +0.156 ns (`worst_hold_path.rpt`, from `min.rpt`).
- Correction 2026-09-19: an earlier revision of the docs quoted 25.1 MHz; that figure mistook the +0.156 ns **hold** slack for the setup slack.
- copied 2026-09-19 from `hw/huffman_engine/synth/runs/signoff_confirm/31-openroad-stamidpnr-1/`

Files:
- `power.rpt`
- `worst_setup_path.rpt` — first path block of `max.rpt` (setup)
- `worst_hold_path.rpt` — first path block of `min.rpt` (hold)

Regenerate: `. ~/.nix-profile/etc/profile.d/nix.sh && cd hw/huffman_engine && openlane --run-tag <tag> <config>` (stops after post-CTS; no GDS).
