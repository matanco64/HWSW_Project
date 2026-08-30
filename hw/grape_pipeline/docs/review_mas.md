# grape_pipeline — MAS review findings (hw-review, spec mode)

## Pass 1 — 2026-08-30 (independent reviewer agent)

18 findings: 4 must, 11 should, 3 nit. All resolved; the closing edit is named.

| id | severity | location | problem | resolution |
|---|---|---|---|---|
| R1 | must | §4/§5/§8 vs `axi_lite_regs.sv` | shared cell cannot do W1C, WP, ignore-while-BUSY, sparse SLVERR, delayed BRESP | §4.1 "Delta to the shared cell": `axi_lite_if.sv` handshake-only cell with a simple register bus + `wr_resp_hold`; per-module decoder |
| R2 | must | BODY read-back | idle read semantics undefined | §4 intro: pending while idle, committed snapshot while BUSY, committed copied to pending at DONE/ABORTED |
| R3 | must | driver `advance()` | benchmark pairs are body tuples, not indices | `advance()` maps by identity (i = first, j = second); mass not written back; PAIR row names b1/b2 |
| R4 | must | PAIR fields | 4-bit fields truncate bad indices | PAIR i = 7:0, j = 15:8; any ≥ N_BODIES → ERR_PARAM; driver validates too |
| R5 | should | responses | ignored/RO/reserved writes | OKAY for in-map ignored writes; reserved words listed RAZ/WI; unmapped → SLVERR |
| R6 | should | CYCLES while BUSY | atomicity | live, no atomicity guarantee while BUSY; stable when idle |
| R7 | should | `irq` | registered? IRQ_EN while high | §8: registered copy, 1-cycle; IRQ_EN clear drops irq, STATUS untouched |
| R8 | should | CTRL same-write cases | undefined | §8 rows: idle both → nothing; BUSY both → ABORT + ERR_BUSY; ABORT at accept cycle |
| R9 | should | ABORT bound | missing | §8: within K1 + 8 cycles; traceability F11 |
| R10 | should | writable while BUSY | implicit | §4 intro: only STATUS W1C, IRQ_EN, CTRL |
| R11 | should | reset wording vs ID | contradiction | §3: RW/W1C/counters → 0; ID/VERSION constants |
| R12 | should | §5 "measured" | estimate presented as measured; PRD Q4 open | marked estimate (4 cycles/transaction); K1 unchanged sentence |
| R13 | should | `wait_done` | semantics | polls STATUS; raises only on timeout or ERR_PARAM/ERR_BUSY since start; FP_* returned |
| R14 | should | block diagram | missing irq/status path, abort, double buffer | edges added (`regs → cpu` STATUS/irq, `doorbell / abort`), body block "working + committed", §7 text aligned |
| R15 | should | subnormal flag | no bit reserved | STATUS bit 16 FP_DENORMAL reserved; IRQ_EN 16:1 |
| R16 | nit | NPAIRS width | 3:0 | 7:0 |
| R17 | nit | reset mid-transaction | unstated | §3 |
| R18 | nit | non-existent paths | — | marked "created by hw-integrate / hw-review" |

Open must: **0**.

## Pass 2 — 2026-08-30 (independent reviewer agent, after pass-1 fixes)

R1–R18 verified (R15 half-resolved → S1). 3 new findings, all resolved:

| id | severity | location | problem | resolution |
|---|---|---|---|---|
| S1 | must | driver `clear()` | default mask missed bit 16 | `0x1FFFE`, "all sticky bits 16:1" |
| S2 | must | §4 while-BUSY rule | spanned reserved/unmapped words | rule restricted to listed RW configuration registers |
| S3 | must | header gap 0x018–0x03C | unlisted → SLVERR vs ADR | reserved row added; ADR-0005 wording allows listed-unmapped SLVERR |

Open must: **0**. Total: 21 findings (2 passes), 0 must open.
