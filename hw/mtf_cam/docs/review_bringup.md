# mtf_cam — dv_bringup review (RTL mode)

Adversarial RTL-mode review of the bring-up diff (commit 2ea7b9b): `tb/env.py`
(MtfEnv + replay MtfScoreboard), `tb/test_mtf_cam.py`, `tb/sequences/smoke.py`, and the
one RTL change in `rtl/mtf_cam.sv` (SVA guard `SIMULATION`→`VERILATOR`).

## Checklist verdicts

| Item | Verdict |
|---|---|
| Reset | ✓ monitors gate on `rst_n`, `is_resolvable` asserts only after reset |
| CDC | ✓ single clock (module header), N/A |
| Width | ✓ only RTL change is a compile guard; no datapath edit |
| X-propagation | ✓ AxisMonitor asserts `is_resolvable` on every accepted beat; Icarus 4-state clean |
| Handshake | ✓ cocotbext-axi source/sink drive valid/ready; monitors passive |
| FSM completeness | ✓ unchanged from RTL stage (reviewed in review_rtl.md) |
| Verkor sequential-read | ✓ no RTL logic changed |
| **Testbench honesty** | ✓ scoreboard calls FROZEN golden `list_model.expand` (READ/CALL only), predictor cross-checked `== mtf_ref.l_vector` per block; every test hard-asserts (`assert`, not a log line) |

## Findings

| id | sev | location | problem | disposition |
|---|---|---|---|---|
| B1 | nit | tb/env.py `report_phase` | shared scoreboard reports `PASS` when `compared == 0` (a test that never streams would pass vacuously) | accepted — every directed test carries its own hard asserts (K1≤1.10 line 185; multiblock MAX_RUN 62/3 lines 142-143; K3 `predictor == mtf_ref.l_vector` line 205 + SYMBOLS_IN/BYTES_OUT/MAX_RUN/K3 lines 222-225), so the vacuous path is never reached; a `compared>0` guard is a future hardening, not a bring-up blocker |

## SVA guard change (the only RTL edit)

`ifdef SIMULATION` → `ifdef VERILATOR` on the concurrent-SVA block. Verified: no other
`ifdef SIMULATION` or unguarded `assert property` remains in `hw/mtf_cam/rtl/` (grep clean);
all 6 protocol assertions (a_ml_stable, a_ml_keep_contig, a_fifo_b_implies_a, a_fifo_room,
a_bytes_budget, a_done_abort_excl) sit under the new guard. Verilator auto-defines `VERILATOR`
so they stay armed via `--assert` (Verilator run green); Icarus's role is the 4-state X-check
via the pyuvm `is_resolvable` asserts, not these. Matches the repo `fp64_rcp_nr`/`fp64_sqrt_srt`
convention.

## Verdict

Testbench compares against `golden/` (never a re-implementation); the R1 (MAX_RUN
per-invocation reset) and R2 (DUT K3 vs model) carry-over tasks from review_rtl.md are both
answered with green tests. **Musts open: 0. Shoulds open: 0.** Ready to record the gate.
