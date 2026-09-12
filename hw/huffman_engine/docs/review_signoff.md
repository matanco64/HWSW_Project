# huffman_engine — dv_signoff review (RTL mode)

Deepest adversarial pass over the whole shipped RTL (all 10 rtl/ files + axi_lite_if.sv), by
the sign-off reviewer: full hand-traces of the C0→C1→C2 pipeline, the DEFLATE II=2
length/distance sequence, the stall/credit equation, the selector cadence, the aligner
tail/skip, the limit/EOB/flush interactions, and cross-invocation reset. **Verdict:
sign-off-ready — no must-level defect.** No legal input produces a wrong beat, a hang, or
lost/duplicated data; the SYMBOL_LIMIT/EOB/flush semantics, the DEFLATE extra-bit sequencing,
the stall-credit skid bound, and the canonical-decode index math were all traced correct.

## Findings and dispositions (5, all resolved)

| id | sev | file | problem | disposition |
|---|---|---|---|---|
| S1 | should | huff_out.sv | flush withdrawal has a 1-cycle handshake "race": a beat becoming tvalid the same cycle flush first asserts, with tready=1, transfers instead of being withdrawn | **CONSIDERED, REJECTED (behavior is correct)**: masking the handshake with `!flush_i` was implemented and *failed regression* — `errors_runtime` (ERR_NOCODE) expects SYMBOLS = N valid symbols before the error, and the flush-cycle transfer is exactly that intended valid-beat delivery. On ERR the last valid skid beat must deliver; flush withdraws only the beats not yet handshaked *after* this cycle (it clears the next state v0_n/v1_n). The golden/testplan encode this. Reverted with an in-code rationale; the test suite is the arbiter. |
| S2 | should | huff_deflate.sv / huffman_engine.sv | on truncated/corrupt DEFLATE input, D_EMIT could push a TYPE-2 pair built from zero-padded (underrun) extra bits before ctrl reached S_ERR | **FIXED**: the top's DEFLATE pair-push is gated with `!underrun` (the aligner's sticky underrun is high by D_EMIT if any extra-bit consume overran) — the bad beat is suppressed, ctrl routes to ERR_UNDERRUN |
| S3 | nit | huff_deflate.sv | `rev_extract`'s `pad_zero` guard was dead (mask `{13{!pad_zero\|pad_zero}}` is always all-ones) | **FIXED**: removed; the `(1<<n)-1` mask already zeroes bits ≥ n (lint_off UNUSEDSIGNAL for the deliberately-unread window bits) |
| S4 | nit | huff_deflate.sv | `extra_bits` default was a meaningless placeholder expression | **FIXED**: default `13'd0` |
| S5 | nit | huffman_engine.sv | `c1_eob`/`c1_dist`/`c1_len` had no explicit reset (safe only via the downstream `c1_v` qualifier) | **FIXED**: `&& rst_n` / `rst_n ? … : 0` for defense-in-depth and lint clarity |

## Explicitly checked and cleared (no finding)

SYMBOL_LIMIT/EOB/flush (LIMIT = max total beats incl. EOB; no dropped/dup EOB, no beat past
the stop); DEFLATE consume ordering + `lextra_q`/`dextra_q` latching; ROM index widths (lidx
0..28, didx 0..29, 286/287 & dist 30/31 rejected before use); stall credit (no underflow, skid
never overflows, deflate emit temporally disjoint from c1_v pushes); II=2 interlock (single
dist_issue, no deadlock/double-issue, B8 confirmed); selector 50-cadence + 0-cycle switch +
pending/set_valid boundary (R3/N4/N10); aligner START_BIT/tail/underrun + DEFLATE bit-reverse ×
tkeep; cross-invocation state (doorbell/flush/clear leave no leakage); RESET/CDC (single clock)
/handshake/X-prop (no latch, no comb tvalid←tready, AXI-Lite always responds).

**Musts open: 0.** S2–S5 fixed; S1 considered and rejected (its fix broke valid-beat delivery
on ERR — the test suite caught it, behavior is correct as-is). Re-verified with the full
regression (17/17 both sims) + formal (4/4) after the changes.
