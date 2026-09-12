# mtf_cam — RTL review (RTL mode, stage 4)

Adversarial full-module review of the 8 rtl/ files + axi_lite_if.sv against the approved uArch,
MAS §4, PRD-F1..F16, and the golden. The three uArch-review musts were verified as-built and all
PASS: **M1** (22-bit run sum/compare — ERR_RUN fires on 20×RUNA+RUNB, no wrap), **M2** (2-wide
atomic enqueue, order preserved, 2-slot reservation, no loss/overwrite for 2W/1R), **M3**
(enqueue-after-check — on ERR_RANK neither item enters the FIFO; the UNOPTFLAT combinational loop
is genuinely broken, not lint-silenced). Move-to-front is bit-exact to `list_model.expand`; the
packer's delayed-emit gives the exact-multiple last beat its TLAST; reset/handshake/latch clean.

## Findings

| id | sev | location | problem | disposition |
|---|---|---|---|---|
| R1 | must | mtf_run.sv / mtf_cam.sv | MAX_RUN (0x054) reset only by `!rst_n`, not per invocation — a smaller-max block after a large one reads the stale value; MAS/PRD-F12 say "in the invocation" | **FIXED**: added `inv_clr` to mtf_run (zeroes max_n), wired to `doorbell` in the top; doorbell (IDLE) never coincides with `commit` (DECODE) → race-free |
| R2 | should | mtf_ctrl tready gate vs golden `cycles` | RTL gates `s_sym.tready` on the 2-slot reservation for every DECODE beat; the golden K3 model gates on the beat's actual item need (0 for run beats). DUT stalls ≥ model at the cnt=7 boundary | **OPEN — dv_bringup entry criterion**: measure the DUT's actual K1/K3 at bring-up; if ≤ 1.10 the 2-slot reservation is fine (reviewer expects small delta), else reconcile. Golden is frozen; the RTL 2-slot reservation is the safe/correct behavior |
| R3 | nit | INIT_CYCLES | author's "257 at N_USED=256" concern | **CLEARED by review**: the doorbell-cycle counter reset cancels the busy-wait detection cycle → INIT_CYCLES = N_USED = 256 ≤ 256. No change |
| R4 | nit | mtf_ctrl doorbell | doorbell doesn't pipe_flush the FIFO/expander; relies on the empty-at-IDLE invariant (which holds) | optional SVA `doorbell |-> fifo_empty`; deferred |
| R5 | nit | mtf_list abort-in-INIT | a stray fill continues after abort-in-INIT but is overridden by the next init_start (benign) | optional tidy; deferred |

Musts open: **0** (R1 fixed, re-linted clean). R2 tracked to dv_bringup; R3–R5 non-blocking.
