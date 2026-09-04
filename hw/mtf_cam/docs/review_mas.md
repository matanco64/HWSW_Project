# mtf_cam — MAS review findings (hw-review, spec mode)

## Pass 1 — 2026-08-30 (independent reviewer agent)

20 findings: 5 must, 9 should, 6 nit. All resolved; the closing edit is named.

| id | severity | location | problem | resolution |
|---|---|---|---|---|
| R1 | must | flush vs stalled `m_l` | 8-cycle bound impossible under back-pressure | flag/BUSY within bound regardless of tready; partial beat held valid until handshaken; BYTES_OUT on handshake; CYCLES at flag |
| R2 | must | ERR_LIMIT bytes | symbol-side vs drain-side ambiguity | checked at item production incl. queued bytes; item not enqueued; SYMBOLS_IN frozen at that beat |
| R3 | must | FIFO at ERR/ABORT | contents unspecified | FIFO, expander state, pending run discarded; only the partial beat flushed |
| R4 | must | chained failure | deadlock on either module's error | chained driver aborts the other module, then flushes; early huffman doorbell tolerated |
| R5 | must | `s_sym` contract | RUNA/RUNB and EOB-by-value cases missing | row rewritten with the full value map |
| R6 | should | ERR_PARAM | N_USED > N_LIST | added |
| R7 | should | TYPE 3 without TLAST | unspecified | TLAST ignored on TYPE 3 |
| R8 | should | [27:12]/[31:28] | unspecified | ignored |
| R9 | should | SYMBOL_LIMIT boundary | EOB as last beat | huffman rule copied |
| R10 | should | error timing | no bound | ≤ 4 cycles after the handshake, irq +1 |
| R11 | should | `expand_block` encoding | implied | raw values; replay source makes beats; chained path passes huffman beats |
| R12 | should | which ERR_* raise | undefined | listed |
| R13 | should | MAX_RUN / SYMBOLS_IN | units, EOB counted | defined |
| R14 | should | empty-block DONE | no bound | the cycle after the EOB handshake |
| R15 | nit | IRQ_EN bits 7:3 | undefined | reserved |
| R16 | nit | CAPS 31:25 | undefined | reserved 0 |
| R17 | nit | TKEEP=0 lanes | undefined | 0 |
| R18 | nit | DBG_DATA during init | undefined | live, partial |
| R19 | nit | bus traffic vs PRD | 14 vs 12 words | MAS supersedes |
| R20 | nit | INIT_CYCLES vs model | drift | target N_USED + c ≤ 4; model uses measured |

Open must: **0**.

## Pass 2 — 2026-08-30 (independent reviewer agent, after pass-1 fixes)

R1–R20 verified. 4 new findings (exposed by the R1/R2/R4/R20 rewrites), all resolved:

| id | severity | location | problem | resolution |
|---|---|---|---|---|
| S1 | must | pending flush beat vs stopped sink | stale beat into the next block; `expand_block` race | accepted doorbell / reset withdraws a pending beat; driver drains the sink before reading BYTES_OUT |
| S2 | must | ERR_LIMIT byte check | packer bytes omitted → BYTES_OUT could exceed the limit | check counts all accepted-but-not-handshaken bytes |
| S3 | must | chained abort | huffman may hold a stale `m_sym` beat | huffman MAS amendment + ADR-0006 chaining rule: producers withdraw un-handshaken beats on ERR/ABORT/doorbell |
| S4 | must | INIT_CYCLES ≤ 260 vs 256 | contradiction with §5 and PRD-F4 | INIT_CYCLES = doorbell → `tready` rising, ≤ 256 |
| n1 | should | PRD-F9 "no IRQ" | ambiguous vs ADR-0005 | PRD errata recorded |

Open must: **0**. Total: 24 findings (2 passes), 0 must open.
