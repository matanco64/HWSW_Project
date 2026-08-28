# huffman_engine — PRD review findings (hw-review, spec mode)

## Pass 1 — 2026-08-28 (independent reviewer agent)

20 findings: 7 must, 8 should, 5 nit. All resolved; the closing edit is named.

| id | severity | location | problem | resolution |
|---|---|---|---|---|
| R1 | must | F5, §5 | DEFLATE distance 15-bit cannot hold 32,768 | F5/§5: distance 16-bit (1..32768) |
| R2 | must | F9 | ERR_TABLE rejected legal incomplete/empty DEFLATE tables | F9: ERR_TABLE = over-subscribed only; incomplete + empty distance table legal; `canonical_model.Table` Kraft check changed; `test_deflate`/`test_corner` cases added |
| R3 | must | F9/F1 | no error for lit 286/287, dist 30/31; 284+31 unstated | F10: ERR_SYMBOL; 284+31 → 258 (as pyflate); `canonical_model` raises ERR_SYMBOL |
| R4 | must | F9 | post-error state undefined | F10: BUSY=0, DONE=0, flag + IRQ, no TLAST, counters frozen |
| R5 | must | F12/F9 | "never reads past" vs over-fetch; MAXLEN peek at buffer end undefined | F4: zero padding after TLAST, OVERFETCH ≤ 4 beats; ERR_UNDERRUN = consumed bit beyond last received; cycle-model docstring states the padding |
| R6 | must | F7/F8/F1 | DEFLATE table mapping and MAXLEN 15 unstated | F7: table 0 lit/len, table 1 dist, selectors ignored; F3/F8: MAXLEN 20/15 |
| R7 | must | F10 | semantics delegated to grape, ABORT during build/stall unstated | F11 written out in full: 8-cycle ABORT (decode/stall), 16-cycle (build), reads-while-BUSY, same-cycle rule, ABORT after EOB |
| R8 | should | F14, calibrate | prefix-only DEFLATE comparison, no end-bit, no multi-block/stored | `calibrate.py`: exact per-block equality + end bit; Z_FULL_FLUSH multi-block stream and a stored stream added; table keys by creation order (id() recycling bug found and fixed) |
| R9 | should | K4a, §1 | 75 % slice mixed cum/self and included MTF | §1 rebuilt from self-time: module slice 49.6 %, loop 79.9 %; K4a vs Huffman-only, K4b with `mtf_cam` cycles |
| R10 | should | K1 | cycle-model assumptions asserted | K1 lists them (serial builds, switch 1, refill 0, extra bits 0) as uArch items |
| R11 | should | K2 | build timing contradiction | K2: builds after the accepted doorbell, per table, first beat ≤ N_TABLES × K2 + 16 |
| R12 | should | F9 ERR_PARAM | missing range checks; doorbell-time selector scan | F9 lists ALPHABET < 3, NSELECTORS 0/> 18002, lengths > MAXLEN; selector range checked at first use (F10) |
| R13 | should | F8 | 18,002-entry on-chip selector window = 54 kbit flops | selectors streamed on `s_sel` (F7/F8/§5/§6) — **design change, flagged for approval** |
| R14 | should | F12/F11 | next START_BIT formula | F13: START_BIT + BITS, header re-parsed by software; BITS relative |
| R15 | should | F3 | length range and canonical rule source | F2/F3: lengths 0..MAXLEN, RFC 1951 §3.2.2 |
| R16 | nit | §1/K4a | "software loop" label | K4a/K4b relabelled |
| R17 | nit | F7/§4 | inconsistent denominators, packing ambiguity | §4: 640 bus cycles / 153 k; "packed continuously, 6 per word, table-major" |
| R18 | nit | F5 vs §8 | beat width fixed vs open | F5: "≥ 9 bit; encoding per MAS" |
| R19 | nit | F1 | golden raises where HW flags | F10 states it |
| R20 | nit | §7 | alphabet ranges per mode | `test_random` ranges per mode |

Open must: **0**.

## Pass 2 — 2026-08-28 (independent reviewer agent, after pass-1 fixes)

R1–R20 verified resolved; every PRD number re-checked against `calibrate.py`. 5 new findings,
all consequences of streaming the selectors (R13); all resolved:

| id | severity | location | problem | resolution |
|---|---|---|---|---|
| S1 | must | F7, calibrate | "297 selector beats" was the retired AXI-Lite packing | F7: 2,966 `s_sel` beats; calibrate prints AXI-Lite lengths + control words (157, 0.41 %) and `s_sel` beats separately |
| S2 | must | F7/F9/F10/F6 | NSELECTORS vs `s_sel` TLAST undefined; `s_sel` stall missing | NSELECTORS register removed; TLAST is the only terminator; surplus beats drained before DONE; ERR_SELECTOR when TLAST already consumed; F6 covers `s_sel.tvalid`; `test_corner` cases |
| S3 | must | F12 vs F7 | overflow claim false at SYMBOL_LIMIT = 2^32; SYMBOL_LIMIT = 0 unhandled | SYMBOL_LIMIT valid 1..2^27 (ERR_PARAM otherwise); F12 overflow bound restated |
| S4 | must | F11 | "reads while BUSY return latched values" covered STATUS/counters | F11: configuration registers latched, STATUS + counters live |
| S5 | must | F7/F8/F9 DEFLATE | second alphabet's placement and DEFLATE parameter checks unstated | F7: table 0 = indices 0..ALPHABET−1 (257..288), table 1 = next 30; EOB = 256; F9: ERR_PARAM for MODE=1 with N_TABLES ≠ 2 or ALPHABET < 257 |

Open must: **0**. Total: 25 findings (2 passes), 0 must open.
