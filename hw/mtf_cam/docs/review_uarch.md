# mtf_cam — uArch review (spec mode)

Adversarial spec review against PRD (K1–K8, F1–F16), MAS (§2/§4/§5/§8), the golden
`list_model.cycles` (reproduced), and ADR-0004/0006. Pass 1: 12 findings (3 must, 6 should, 3
nit). All resolved in the current uarch.md.

## Findings and dispositions

| id | sev | § | problem | disposition |
|---|---|---|---|---|
| M1 | must | §4/§6 | 21-bit run adder can't represent the k=20 RUNB addend (2²¹); the reachable "20×RUNA then RUNB" partial sum wraps below 2²⁰ so ERR_RUN is silently missed and n is corrupted | **FIXED**: run sum + `>2^20` compare are **22-bit**; only a validated n ≤ 2²⁰ is stored in the 21-bit field (§4 row + shift-and-add note + §6 row) |
| M2 | must | §5/§7/§8 | K3 = 1.063 depends on the golden enqueuing 2 items in one cycle for a run-terminating symbol, but §5 declared a 1-write-port FIFO → with 1W, ~192 k cycles, K3 ≈ 1.30 > 1.10, KPI busted | **FIXED**: item FIFO specified **2-wide write port** (atomic RUN+MTF_BYTE push); FIFO-full gate reserves 2 slots (§2 "atomic 2-wide enqueue", §5, §8) |
| M3 | must | §2/§3.1/§8 | overlapped drain could handshake a pending run's bytes to `m_l` in the 1–4-cycle window before an ERR_RANK freeze, violating PRD-F10 "run pending at ERR_RANK → discarded" | **FIXED**: **enqueue-after-check** — both items enqueue only after the terminating symbol passes the per-symbol error checks in the same cycle; on ERR_RANK neither item enters the FIFO, so no run byte can reach `m_l` (§2) |
| S1 | should | §3.2/§7 | INIT fill described as a linear 0..255 walk (≤256 cyc) but §7/MAS use N_USED (145) | **FIXED**: fill is a **priority encoder emitting one used byte/cycle** → INIT_CYCLES = N_USED (§3.2) |
| S2 | should | §3.1/§8 | ERR_LIMIT's in-flight-bytes counter never defined | **FIXED**: added the `UQ31.0` in-flight byte counter to §5 (width/reset/update: +item-bytes at enqueue, −TKEEP-popcount at handshake) |
| S3 | should | §1/§2/§4 | "TKEEP all ones except the last beat" mis-drives the exact-multiple case — the benchmark's final beat is full (336,184 = 42,023×8) and must still carry TLAST | **FIXED**: §4 tkeep row + §1 mtf_pack state the last beat is contiguous-from-lane-0 **including all-ones exact-multiple**, TLAST on whichever beat is last |
| S4 | should | §10 | K8/F5 coverage thin — three invariants, the N_LIST=16 induction parametrisation, and the 256 bounded check not stated | **FIXED**: §10 PRD-F5 row enumerates invariants (i)/(ii)/(iii), N_LIST=16 unbounded induction, ≥20 bounded on 256 |
| S5 | should | §10 | K2 and K7 had no traceability row | **FIXED**: K2 → §3.3 expander, K7 → OpenLane report-only added |
| S6 | should | §6 | read-mux timing counts gate depth only, omits 256-way fanout/wire load | **FIXED**: §6 caveat added; K4 is PPA-measured |
| N1 | nit | §3.1/§8 | ≤4/≤8-cycle latency bounds not derived | noted — the ≤4 is the C0→flag pipeline depth, ≤8 the abort→drain-flush depth; folded into §8 wording (M3 clarified the per-symbol check is combinational-before-enqueue, not the flag-visibility latency) |
| N2 | nit | §1 | MAS 0x054 "run discarded at error does not count toward MAX_RUN" not restated | accepted as MAS-authoritative; MAX_RUN updates only on a committed (enqueued) run item, consistent with M3's enqueue-after-check |
| N3 | nit | §1/§3.1 | item `kind` encoding + ABORT-while-IDLE no-op undrawn | kind: 0 = MTF_BYTE, 1 = RUN (1-bit); ABORT-while-IDLE is a no-op (PRD-F11), consistent with §3.1 IDLE having no abort arc |

## Verdict

Pass 1 found 3 must (M1 width bug, M2 the headline-KPI FIFO-port structural gap, M3 the
error-discard race) and 9 should/nit. All must-level defects are resolved with small, concrete
spec edits (an extra adder bit; a 2-wide FIFO write port with a 2-slot full reservation; an
enqueue-after-check gate). The design's core decisions — shift-register CAM for 1 sym/cycle, the
two-sided item-FIFO for K3, the run-ordering rule — survived the review intact. **Musts open: 0.**
Ready for the checkpoint.
