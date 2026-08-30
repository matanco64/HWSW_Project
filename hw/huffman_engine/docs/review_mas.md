# huffman_engine — MAS review findings (hw-review, spec mode)

## Pass 1 — 2026-08-30 (independent reviewer agent)

20 findings: 5 must, 10 should, 5 nit. All resolved; the closing edit is named.

| id | severity | location | problem | resolution |
|---|---|---|---|---|
| R1 | must | DBG_SEL/DBG_DATA | 8-bit index cannot reach slots 256..287; ranges undefined | index 16:8; out-of-range/pre-build → 0; live during build |
| R2 | must | ERR_TABLE timing | over-subscription unknowable at doorbell | doorbell BRESP held ≤ 8 cycles for ERR_PARAM/length checks; over-subscription = build-time ERR_TABLE (§8); PRD-F9 errata recorded in prd.md |
| R3 | must | driver `wait_done` | base spins on run-time errors | `HuffmanDriver.wait_done` returns when BUSY = 0, raises per flag; `clear()` 0xFFFE; hw-integrate lifts the rule into the base |
| R4 | must | TKEEP | patterns undefined | all-ones except contiguous-from-lane-0 on TLAST; others = protocol violation |
| R5 | must | DMA model | channels left mid-transfer after DONE/ERR/ABORT | §5 DMA rules: stop/flush all three channels before every doorbell; tready 0 until next doorbell; testbench re-creates source/sink per block |
| R6 | should | buffer end | underrun boundary | §5: peek beyond end = 0, consume → ERR_UNDERRUN; START_BIT ≥ buffer → ERR_UNDERRUN at symbol 0 |
| R7 | should | ABORT during `s_sel` drain | ambiguous | drain stops, DONE (not ABORTED), beats left to the flush |
| R8 | should | LEN entries beyond use | spurious ERR_TABLE | ignored by build and check |
| R9 | should | EOB beat value | undefined | [8:0] = EOB value, [27:12] = 0 (MAS + ADR-0006) |
| R10 | should | SYMBOL_LIMIT semantics | EOB as last beat | ERR_LIMIT only if none of SYMBOL_LIMIT beats was EOB; predictor check at dv_testplan |
| R11 | should | SYMBOL_LIMIT reset | 0 rejected vs PRD default | noted: driver default 2^20 |
| R12 | should | `load_lengths` | needs ALPHABET/MODE; validation blocks corner tests | uses last configure(); `validate` flag |
| R13 | should | LEN DEFLATE layout | formula + HDIST 31/32 | explicit t = 1 formula; entries ≥ ALPHABET + 30 ignored; software drops HDIST 30/31 |
| R14 | should | CYCLES | idle stability | stable when BUSY = 0, read LO then HI |
| R15 | should | diagram | missing SYMBOL_LIMIT/DBG, `sel → lookup`, BITS/OVERFETCH | added |
| R16 | nit | traceability | F2, F15 rows | added |
| R17 | nit | `s_sel` | [7:3], check point | ignored; checked when applied |
| R18 | nit | prefetch during build | unstated | allowed, bounded by the window |
| R19 | nit | LEN latching copy | 8.6 kbit second copy implied | single copy note |
| R20 | nit | 0.41 % | provisional | marked |

Open must: **0**.

## Pass 2 — 2026-08-30 (independent reviewer agent, after pass-1 fixes)

R1–R20 verified; DBG_SEL layout, LEN window arithmetic, BRESP hold, ABORT-during-drain and DMA
rules checked consistent. 3 new findings, all resolved:

| id | severity | location | problem | resolution |
|---|---|---|---|---|
| S1 | must | §8 vs §5 | `s_sel` prefetch during build contradictory | `s_sel` tready stays 0 until the last build completes; only `s_bits` prefetches |
| S2 | must | irq on doorbell rejection vs PRD-F9 | "no IRQ" ambiguity | PRD errata: "no IRQ" = no DONE interrupt; flags assert irq iff IRQ_EN bit set |
| S3 | must | EOB beat TYPE | undefined / ADR ambiguous | EOB = TYPE 3 in both modes; TYPE 0 never carries the EOB value (MAS + ADR-0006) |

Open must: **0**. Total: 23 findings (2 passes), 0 must open.
