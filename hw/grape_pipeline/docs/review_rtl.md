# grape_pipeline — RTL review findings (hw-review, RTL mode)

## Pass 1 — 2026-09-05 (independent reviewer agent)

12 findings: 5 must, 4 should, 3 nit. All resolved (commits 729f41b, 7acd842, 94bf481).

| id | severity | area | problem | resolution |
|---|---|---|---|---|
| R1 | must | force_pipe shadow capture | ev_pair/ev_tag held only the LAST of up to 6 events/cycle — every unit's result captured into the wrong scratch slot | per-unit issue capture arrays (add/mul/sqrt/rcp_iss_p/t) written in the event loop |
| R2 | must | force_pipe operand timing | table schedules consumers at parent_issue+LAT, the retire cycle — scratch not yet written | scr_fwd same-cycle forwarding view over all four result buses; operand reads use it |
| R3 | must | accum scoreboard index | field = comp+3 → field[1:0] cleared the wrong (body,comp), one bit never cleared → hang | add_sh_c component array used in clear and bypass compare |
| R4 | must | accum all_done | integrate-MUL retires uncounted → all_done unreachable → S_RUN hang (every config) | MUL retires count; all_done = acc_done ∧ muls done ∧ adds issued ∧ retired == 6·NPAIRS+30 |
| R5 | must | accum chain bypass | scoreboard bypass issued with the PRE-retire operand (working-bank write is registered) | byp_data: retiring unit's result muxed into add_a_o with clr_bypass |
| R6 | should | integrate gating | global retired_acc_all gate = the phase gating uArch §3.1 rejects (K1 risk) | per-lane: acc_done ∧ !busy_bc[lane] |
| R7 | should | regs CTRL strobes | doorbell/abort acted on wstrb=0 writes | qualified by wr_strb_i[0] |
| R8 | should | axi_lite_if wr_err | re-sampled every held cycle; one-cycle pulse lost under hold | captured once per transaction (wr_err_seen) |
| R9 | should | test_regs docstring | stale "kept red" note (bug already fixed) | updated |
| R10 | nit | acc_total width | 4-bit NPAIRS truncation | commented: safe under ERR_PARAM cap |
| R11 | nit | sqrt/rcp shadow latch | pair/tag latched without valid | folded into R1 per-unit capture |
| R12 | nit | IRQ_EN bit 16 | writable but dead | documented (reserved until the subnormal decision) |

Checklist verdicts (pass 1): top PASS · force_pipe FAIL→fixed · accum FAIL→fixed · body_rf PASS ·
step_fsm PASS · regs PASS+R7/R12 · axi_lite_if PASS+R8 · fp64 units PASS (unit-tested elsewhere).
Verilator whole-module lint: clean, no UNOPTFLAT. Operand order vs `emulation.py` verified correct
(v_i − dx·b2m then v_j + dx·b1m, i-then-j).
