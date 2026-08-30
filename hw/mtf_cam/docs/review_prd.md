# mtf_cam — PRD review findings (hw-review, spec mode)

## Pass 1 — 2026-08-30 (independent reviewer agent)

19 findings: 6 must, 9 should, 4 nit. All resolved; the closing edit is named.

| id | severity | location | problem | resolution |
|---|---|---|---|---|
| R1 | must | K1/K2/F6/§4 | beat packing undefined | F6: byte-packed, TKEEP partial only on the last beat; 42,023 beats; cycle model has a packer that adds no cycles |
| R2 | must | K3, list_model | cycle model credited impossible overlap | model rebuilt as a two-sided simulation (symbol side → item FIFO depth D → drain side); assumptions stated in F7/K3; K3 re-derived: D = 0 1.370, D = 8 1.063, D = 32 1.046 |
| R3 | must | F3/F8/F10 | 20 symbols vs 21 bits vs ERR_RUN contradiction | n ≤ 2^20, ≤ 20 symbols, offending symbol defined; `list_model` raises ERR_RUN; test_random wording fixed |
| R4 | must | F12 | garbled/false overflow bound | BYTES_LIMIT register (≤ 2^30) + ERR_LIMIT; bounds derived |
| R5 | must | F3/F10/F11 | pending run at error; ABORT during post-EOB drain | F10: pending run discarded, partial beat flushed; F11: ABORT during drain → ABORTED, after last handshake → DONE |
| R6 | must | F1/F12/K3 | DONE/CYCLES end and K3 test condition | DONE = last beat handshaken; K3 with tready = tvalid = 1 |
| R7 | should | F1/F10 | EOB authority | EOB = value N_USED + 1; type/value mismatch → ERR_RANK; SW obligation on huffman ALPHABET |
| R8 | should | F4/F7 | tready when idle/init/error; doorbell order | F4 states both |
| R9 | should | K5 | undefined 80–105 ms, no module × | K5: 80.4 ms (§1e) / 110 ms (§3), ≈ 25× |
| R10 | should | K1 vs F1 | one-cycle vs pipelined | K1 = throughput only |
| R11 | should | K1/K2 measured-by | block counters can't isolate | K1 directed run-free stream; K2 testbench beat counter over the 8,157-byte run |
| R12 | should | glossary | missing terms | CONTEXT.md: Used map, N_USED |
| R13 | should | K8/F8 | list capacity parameter | N_LIST (256; 16 for formal) |
| R14 | should | F15/list_model | docstring ≠ code; cycle model unvalidated | `expand` (functional) and `cycles` (cycle model) separated; F15 says where the cycle model is validated |
| R15 | should | K6/K7/K5 | no test rows | §7: `make ppa` and integration rows |
| R16 | nit | F10 | ERR_RANK condition overlapped EOB | value > N_USED + 1 |
| R17 | nit | K3 | 163,100 → 163,098 | fixed |
| R18 | nit | mtf_ref | selector-MTF filter by length | filter by element type (`bytes`) |
| R19 | nit | F11 | ABORT during init | "within 8 cycles in any state (init, …)" |

Open must: **0**.

## Pass 2 — 2026-08-30 (independent reviewer agent, after pass-1 fixes)

R1–R19 verified; every PRD number re-checked against `calibrate.py`; `list_model.cycles` verified
against the F7/K3 assumptions. 1 new finding + 3 notes, all resolved:

| id | severity | location | problem | resolution |
|---|---|---|---|---|
| S1 | must | F10/F11 acceptance | flush beat vs "0 beats after" contradiction | acceptance: ≤ 1 flush beat after the error, BYTES_OUT counts it; F11 says the same for ABORT |
| n1 | nit | F7 vs F4 | "tready drops only when full" | F7 references the F4 states |
| n2 | nit | F11 | BYTES_LIMIT missing from write-while-BUSY | added |
| n3 | nit | F1/F12 vs model | DONE timing off by one in wording | F1: DONE the cycle after the last handshake |

Open must: **0**. Total: 20 findings (2 passes), 0 must open.
