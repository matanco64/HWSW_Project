# grape_pipeline — PRD review findings (hw-review, spec mode)

## Pass 1 — 2026-08-28 (independent reviewer agent)

19 findings: 5 must, 9 should, 5 nit. All resolved in the same session; the closing edit is named.

| id | severity | location | problem | resolution |
|---|---|---|---|---|
| R1 | must | PRD-F13, `golden/emulation.py` | emulation model raised on dsq = 0 and computed no IEEE flags — no reference for F13 | `emulation.py` rewritten on numpy float64 with `errstate(all="call")`; returns the flag set; F13 names it as the reference; verified dsq = 0 → {divzero, invalid}, NaN velocities; calibration unchanged (1.055e-10 / 2.638e-12 / 1.9e-14) |
| R2 | must | PRD-F5 vs F10 | per-step bounds unobservable through the interface | F5 restated: bounds at completion (HW-observable) + transitive per-step guarantee via F2 bit-exactness and `calibrate.py`; TB-internal probe optional |
| R3 | must | §2 K1 | 128 cycles/step had no derivation | latency budget added (≈ 106 cycles, itemised, "to be confirmed at uArch") |
| R4 | must | PRD-F7 | out-of-range index / NPAIRS / DT undefined | PRD-F17 added (ERR_PARAM rejection; i == j legal; DT/NSTEPS any value); `test_corner` extended |
| R5 | must | F9–F11 | writes while BUSY, ABORT while idle, ABORT+DOORBELL same cycle undefined | F9: config/state writes while BUSY ignored + ERR_BUSY; F11: idle ABORT no-op, ABORT wins same-cycle |
| R6 | should | F9, F13 | sticky-flag clear mechanism | F12: all sticky flags W1C + reset; doorbell does not clear |
| R7 | should | F15 | reset semantics of data registers | F15: every register to MAS reset value (all zero), software reloads state |
| R8 | should | F11, F12, F10 | abort latency, IRQ on abort, abort as commit point | F11 ≤ K1 + 8 cycles, IRQ as DONE; F10 lists abort |
| R9 | should | F4 vs calibrate vs ADR-0002 | three definitions of the energy number | F4/ADR-0002/calibrate aligned: at completion (1.7e-14) and max over checkpoints (1.9e-14); margin ≥ 50× stated |
| R10 | should | F5 | norm/normaliser unspecified | explicit formula ‖·‖₂ / max(‖·_gold‖₂, 1e-300) |
| R11 | should | §4, K3 | unsourced bus/driver assumptions | assumptions listed explicitly as cycle-model inputs; host = baseline CPU stated |
| R12 | should | F1 | reads as a sequential program | F1: ordering is semantic; concurrency/pipelining allowed if committed state identical |
| R13 | should | F14, K1 | CYCLES edges undefined | F14 defines start/stop edges, no-overflow argument, hold semantics; K1 references it |
| R14 | should | §7 | NSTEPS width and DT range untested | `test_corner`: NSTEPS = 2³² − 1 + abort; `test_random`: DT ∈ [1e-4, 1] |
| R15 | nit | ADR-0001 | byte counts | ADR-0001 → ~340 B in, ~260 B out |
| R16 | nit | emulation docstring | cited F3 for bit-exactness | docstring → PRD-F2 (order per F3) |
| R17 | nit | §8 Q3 | huffman/mtf item in this PRD | trimmed to bus width |
| R18 | nit | F4/F5 | libm platform dependence | calibration platform printed and quoted in §3 |
| R19 | nit | K1, F8 | CYCLES edge consistency | resolved with R13 |

Open must: **0**.

## Pass 2 — 2026-08-28 (independent reviewer agent, after pass-1 fixes)

R1–R19 verified resolved. 4 new findings, all resolved:

| id | severity | location | problem | resolution |
|---|---|---|---|---|
| S1 | must | F17, §5 | rejected doorbell: DONE/IRQ/counters undefined | F17: ERR_PARAM only, no BUSY/DONE/ABORTED/IRQ, CYCLES/STEPS_DONE hold; ERR_PARAM added to §5 |
| S2 | must | F2/F13 | NaN payloads make "0 mismatching bits" unverifiable | F2 NaN rule: HW emits canonical qNaN 0x7FF8…; scoreboard canonicalises emulation NaNs |
| S3 | must | F11 vs F12 | ABORT during the final step | F11: completes normally — DONE asserts, ABORTED does not |
| S4 | should | F5 / ADR-0002 / calibrate | "10×" derivation was false (9.5×) | bounds raised to 2e-9 / 5e-11 (≈ 19×); ADR-0002 and calibrate docstring aligned |

Open must: **0**. Total: 23 findings, 0 must open.
