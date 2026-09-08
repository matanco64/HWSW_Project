# huffman_engine — testplan review

## Pass 1 (2026-09-08, agent)

Scope: `docs/testplan.md` (spec mode, traceability focus) against `docs/prd.md`
(PRD-F1..F16 + errata, §7 acceptance cells, K1/K2), `docs/mas.md` §2/§4/§8 + Amendments,
`docs/uarch.md` §2/§3/§7/§8, `docs/review_rtl.md` (claimed carry-ins
R1/R3/R7/R9/R10/R16/R18/R23/N1/N4/N5/N10), `golden/canonical_model.py` +
`golden/pyflate_ref.py` (both executed by the reviewer — signatures, return shapes and the
benchmark trace verified live), and the grape precedent `hw/grape_pipeline/docs/testplan.md`.
No testplan edits made.

Reviewer-run evidence: `decode_bzip2_symbols(data, bit_pos, lengths_per_table, selectors,
symbols_in_use)` returns `(symbols, end_bit_pos, cycles)` and **appends the EOB symbol to
`symbols` before breaking** (tiny-table run: `syms=[0,1,3]` with EOB=3 last).
`trace_benchmark()` confirms §3's Vectors claim exactly: 1 block, `sym_start_bit` 8,844,
**148,271 trace symbols with the EOB (146 = ALPHABET−1) as the last entry**, BITS
(end − sym_start) = 531,571, per-symbol table ids 0..5, 2,966 selectors, 6 length vectors.

| # | Severity | Location | Finding |
|---|---|---|---|
| T1 | must | §4 "Golden-model interface" (SYMBOLS formula + expected-beats rule) | **Off-by-one on the EOB — the central checker formula is wrong and self-contradictory.** §4 says "SYMBOLS = len(syms) + 1 (EOB beat)" and "Expected beats: TYPE 0 value per symbol, final TYPE 3 EOB". But `decode_bzip2_symbols` **includes the EOB in `syms`** (verified by execution; the loop appends before `break`), and the benchmark trace's 148,271 likewise includes the EOB. Consequences as written: (a) expected SYMBOLS = 148,272 vs the DUT's correct 148,271 — every scoreboard run mis-fails; (b) the K1 check (F-30, `CYCLES/SYMBOLS ≤ 1.1`) uses the wrong denominator — PRD K1 reads the SYMBOLS register (EOB beat included, stretch 153,121/148,271 = 1.033), consistent with uArch 1.0068 = 149,276/148,271, so the golden-side expectation must be `len(syms)`, not `len(syms)+1`; (c) building "TYPE 0 per symbol" from `syms` emits the last element (value ALPHABET−1) as a TYPE 0 beat *and then* a TYPE 3 EOB — one beat too many, and MAS §2 explicitly forbids "TYPE 0 beats never carry the EOB value". Fix: SYMBOLS = len(syms); expected beats = TYPE 0 for syms[:-1], TYPE 3 for syms[-1]. This contradicts §2's own F-12 checker ("SYMBOLS == beats handshaken") — internal inconsistency, not just a doc slip. |
| T2 | must | §2 matrix + §7 (no reset row) | **Reset is never verified.** PRD-F16 ("single clock, synchronous active-low reset", acceptance `test_driver`), PRD-F11's clause "Reset at any time returns to idle with every register zero", and the MAS §8 reset row (STATUS 0, tready/tvalid 0, irq 0, counters 0) have no matrix row, no test, no covergroup. §7's traceability claim "PRD-F1..13 ↔ F-01..13" silently drops PRD-F14/F15/F16 — F16 entirely. Grape's plan (the stated rigor reference) has `test_reset` + `cg_reset` (reset in each FSM state, full readback, re-run bit-exact) as a must row for the analogous requirement — huffman is strictly weaker here. Add a reset feature row (reset in IDLE/PREP/DECODE/DRAIN, full register readback, re-run trace-exact). |
| T3 | must | F-10 (cg_err bins) + F-25 gating | **ERR_SYMBOL (PRD-F10 must clause, MAS §4 bit 13, MAS §8 run-time row) is verified only by the gated, should-priority F-25.** F-10's directed set is `test_errors::{nocode, selector, underrun, limit}` and its cg_err bins are {NOCODE, SELECTOR, UNDERRUN, LIMIT, TABLE} — SYMBOL is absent. F-10 is a must row mapped to PRD-F10, yet its ERR_SYMBOL clause (DEFLATE lit/len ≥ 286, dist ≥ 30, incl. the 284+extra-31 = 258 legality case the PRD names) can only fire in DEFLATE mode (uArch §3.1) and so sits behind the R23 gate at should priority, with §5 pre-authorizing a coverage waiver. Answering the review brief directly: yes, gating `test_deflate` leaves a MUST-priority PRD clause unverified. Either promote the ERR_SYMBOL subset (doorbell + engineered 2-table DEFLATE stream, feasible once R23 resolves) into the must set with an explicit sign-off blocker, or record a justified downgrade in the plan — silence is not a disposition. |
| T4 | must | F-03/F-09 (ERR_TABLE split) | **Doorbell-time ERR_TABLE (length > MAXLEN) has no verifying test.** PRD-F9 lists "any length > MAXLEN (lengths 21..31 in the 5-bit field)" as a doorbell-time rejection (errata: only over-subscription moved to build time; length > MAXLEN *remains* doorbell-time), and MAS §4 bit 10 / uArch §3.2 (invalid bin → ERR_TABLE at doorbell) give the mechanism; MAS §6 even provides the injection hook (`load_lengths(validate=False)`). The matrix covers only the build-time half: F-03's `test_errors::kraft` = over-subscription; F-09's `test_errors::param` = "each ERR_PARAM clause" (a different flag). Nothing injects a 21..31 length; the MAS §8 build-time-ERR_TABLE row's dispositions (BUSY 1→0, no selector consumed, prefetch dropped, CYCLES/BUILD_CYCLES stop at the failing table) are also nowhere itemized as checks. |
| T5 | must | §4 + F-10 checker "ERR_LIMIT emits exactly LIMIT beats" | **The MAS-assigned golden deliverable for ERR_LIMIT is dropped.** MAS 0x110: "the emulation model gets the same check at `hw-dv-testplan`" — this stage. `decode_bzip2_symbols` (verified signature) has **no symbol_limit parameter** and no such check, the plan calls the golden "frozen", and §4 neither schedules the model change nor states how the expected exactly-LIMIT prefix / EOB-at-LIMIT-wins-DONE tie (uArch §2/N3) is derived without it. As written, F-10's ERR_LIMIT checker and the EOB-tie semantics have no golden mechanism. Add the limit-aware decode (or an explicit wrapper in the scoreboard) to the plan as a deliverable. |
| T6 | should | F-09 checker text | **F-09 restates the pre-errata IRQ rule the PRD errata overrode.** Checker: "sticky flag only, no BUSY/DONE/IRQ". PRD errata + MAS §8: on a doorbell-time rejection the ERR_PARAM/ERR_TABLE flag *does* assert `irq` when its IRQ_EN bit is set ("no IRQ" = no DONE interrupt). A checker implementing the row as written mis-fails (or must quietly deviate) whenever the test enables the error mask — which cg_irq coverage should be doing. Spell the errata semantics in the checker cell. |
| T7 | should | §4 error-case interface | **How the "golden prefix" is obtained is unspecified — the model discards it.** The golden raises `ValueError` at the fault (ERR_NOCODE / over-subscription / "selector list exhausted"), and the partial `out` list is a local, lost on raise; an out-of-range selector raises bare `IndexError` (`tables[selectors[i]]`), not a modeled error. §4 says only "errors compare against the golden prefix up to the engineered fault". Workable when the TB itself encoded the stream (it knows the intended prefix), but that reasoning — TB-encoder-derived prefix for engineered faults, exception-type mapping per ERR_* — must be stated, or the model extended to return partial results. |
| T8 | should | F-24 vs open RTL findings N11/N12 | **F-24's checker "zeros per MAS validity rules" collides with the two open, documented DBG deviations.** review_rtl pass 3 leaves N11 (kind-3 index ALPHABET..287 returns residual symtab content, not 0 — MAS says slot 0..ALPHABET−1, out-of-range reads 0) and N12 (DBG reads 0 for the *entire* build vs MAS "live (possibly partial) during a build" + amendment (3) FILL-only zeroing) open as accepted-direction deviations. F-24 as written will fail on N11's index range and, if it tests MAS build-liveness, on N12 — the plan neither predicts these failures nor directs the MAS amendment that would legalize the RTL. State the expected behavior per open finding (test-to-fail + fix, or amend MAS first). §7's claim that F-24 encodes R10/N5 is only true for the resolved halves. |
| T9 | should | header line 6–8 vs §4 R23 gate; F-25 prio | **Internal contradiction on R23, and the gate has no exit condition.** The header says R23 is to be "resolve[d] HERE before any DEFLATE test" — i.e. in this stage — but §4 leaves it unresolved and merely restates the gate, with no owner, no scheduled experiment run, and no criterion for when the gate lifts (the reconciliation recipe itself is good and actionable: known-good gzip fragment vs `decode_deflate_symbols`, amend MAS/uArch). Combined with F-25 at should and §5's pre-authorized waiver, every DEFLATE clause of PRD-F1/F4/F5/F7/F8 (all must-mapped rows) can reach sign-off unverified without any recorded decision. Either run the R23 reconciliation as a testplan-stage action item with a date, or record an explicit descope decision for DEFLATE DV. |
| T10 | should | §2/§7 (PRD-F14/F15 unmapped) | **PRD-F14 and PRD-F15 have no matrix rows — obligations live only as §3 prose.** F14 (independent protocol agents on all four ports, "0 protocol violations across all tests") got a dedicated must row in grape (F-16, with cg_axi bins: BRESP hold, strobe subsets, b2b); here it is a clause inside F-06's checker plus env prose — no coverage, no per-port assertion obligations. F15's two-reference scheme (DUT vs predictor AND predictor vs golden trace, "so a golden error is caught too") is not stated as a scoreboard check anywhere — §3 says "runs the golden decode" (singular); F-01 compares vs trace, F-02 vs canonical_model, but the predictor-vs-trace cross-check that F15's acceptance names is unassigned. Add rows or extend §3/§4 with the explicit double-compare. |
| T11 | should | §2 vs PRD §7 test_corner enumeration | **Several PRD §7-enumerated corner cases have no matrix presence:** 18,002 selectors (bzip2 max, PRD-F8's streamed-capacity rationale), EOB as symbol 0 (PRD-F1 explicitly allows it), the single 1-bit-code incomplete table (legal per PRD-F9; cg_len's len-1 bin implies but does not name it), and SYMBOL_LIMIT = 2^27 *accepted* (F-09 tests the rejects 0 / 2^27+1 only; the legal-max accept is the PRD-listed corner). Also from MAS §8's doorbell-accepted row: "s_sel tready stays 0 until the last table build completes" and counter restart at doorbell have no named check. |
| T12 | should | F-11 cg_irq; grape test_irq precedent | **IRQ verification is a name, not a plan.** `cg_irq` appears in F-11 with no bins, no dedicated test; grape's analogous register block has `test_irq` as a must row (each sticky bit → irq within 2 cycles; W1C drops irq; IRQ_EN mask ×{0,1}; irq == \|(STATUS & IRQ_EN) monitor-checked every cycle). PRD-F10 requires "IRQ within 2 cycles" and MAS §2 defines irq as registered \|(STATUS & IRQ_EN) — both need the grape-style continuous monitor check to be non-vacuous. Define cg_irq bins (each of bits 1,2,8..15 × IRQ_EN) and the per-cycle irq-equation check. |
| T13 | should | §5 coverage goals | **The 90 % line/toggle goal is stated without the exclusions it will need, beyond the two TB wrappers.** With `test_deflate` gated, `huff_deflate.sv` (an entire module) plus the DEFLATE arms of aligner/top sit at ~0 % — §5's waiver clause covers it, but pre-authorizing a waiver for features that are must-mapped PRD clauses (see T3/T9) inverts the burden: the waiver should require the R23 descope decision, not substitute for it. Separately, toggle ≥ 90 % is unreachable on CYCLES_HI's upper bits (2^32+ cycles) and symtab's unused upper regions for small-alphabet tests — grape pre-declared its exclusions (TB wrapper + generated ROM, per-line justification); list the huffman equivalents now rather than at sign-off. |
| T14 | nit | §2 F-03 checker vs F-31 | F-03 asserts `BUILD_CYCLES == ALPHABET+MAXLEN` as a hard per-build check while F-31/K2 specify `≤ 2·ALPHABET+MAXLEN` with equality only "expected" — the uArch implementation detail is promoted to a requirement in one row and a prediction in the other. Harmless today (review confirmed the RTL meets equality) but one refactor away from a spurious must-fail; make F-03 cite the bound and report the measured value. |
| T15 | nit | test naming vs PRD §7 | PRD §7's header says test names are "reused by `hw-dv-testplan`", but the plan renames `test_full_benchmark` → `test_bench_block`, drops `test_driver` (register round-trip delegated to the regs unit TB in F-07/F-08), and splits `test_corner` across `test_errors`/`test_abort`/`test_corner`. Fine engineering, broken paper trail — add a name-mapping line so PRD acceptance cells resolve. |
| T16 | nit | §7 traceability | The carry-in list omits R7 (present in F-13's checker as "aligner lifecycle (R7 regression)") and R3 (present in F-21's own title) — the §7 sentence under-claims what §2 encodes. Also open RTL shoulds R21 (W1C write vs same-cycle set pulse — a directed race case the grape W1C pattern doesn't cover) and R22 (no top-level SVAs; §2's `--assert` armed note presumes SVAs exist to arm) are not carried anywhere. |
| T17 | nit | F-12 / MAS 0x040 | CYCLES_LO/HI is documented non-atomic while BUSY ("stable when BUSY = 0, read LO then HI") — no check exercises a busy-time LO/HI read pair or the idle-time stability rule; cg_counters' {idle, busy} read bins sample reads but assert nothing about coherence. One directed read-pair check in the counters test closes it. |

### Cleared (checked, no finding)

- **Golden call shape (§4)**: 5 positional args match `decode_bzip2_symbols(data, bit_pos,
  lengths_per_table, selectors, symbols_in_use)`; `alphabet` == `symbols_in_use` (EOB =
  ALPHABET−1 both sides); 3-tuple return matches. `trace_benchmark()` provides everything §3's
  Vectors row claims (start_bit 8,844, 148,271 symbols, per-symbol table ids for the F-01
  cadence check, selectors, lengths) — verified by execution. T1 is the only interface error.
- **K1 formula (F-30)**: `CYCLES/SYMBOLS ≤ 1.1` matches PRD K1's register-based definition
  (denominator includes the EOB beat) and uArch §7's 1.0068 = 149,276/148,271; the bring-up
  enforcement (`k1_enforce` on `test_bench_block` only) follows the grape lesson correctly.
  The only K1 hazard is T1's inflated golden-side denominator.
- **Carry-in encoding**: F-21 genuinely pins R3/N4/N10 (entry + 50-boundary stalled-skid, the
  N10 trace), F-22 pins R9/N1 (EOB-lookalike over zero-pad), F-23 pins R1/R18 (backpressured
  error + doorbell-with-parked-beat), F-13 pins R7 (tready rises again). These are the right
  regressions with the right stimuli.
- **F-30/F-31/F-32 realism**: cycle numbers cross-check against uArch §7 (1,004 first-symbol,
  167 build); "—" covergroup cells carry explicit checkers per the grape "no empty cells" rule.
- **Formal list (§6)**: all three properties are small, self-contained, and match the grape
  fsm_arcs precedent; the aligner_cap target is the mechanized U9 proof with bounded state;
  the FLOW "none with reason" fallback is pre-recorded. Feasible as written.
- **OVERFETCH checker (F-12)**: the formula `accepted − ceil((START_BIT+BITS)/32)` (clamped)
  matches MAS 0x054 and the post-N6 RTL; the ≤ 4 architectural bound is carried by the formal
  aligner_cap property rather than the sim checker — acceptable division of labor.

### Summary: 5 must / 8 should / 4 nit

The plan's structure, carry-in regressions, and KPI discipline meet the grape bar. The musts
are concentrated where the plan touches things it did not re-derive: the golden interface
(T1 EOB off-by-one, T5 missing ERR_LIMIT model), and three traceability holes (T2 reset,
T3 ERR_SYMBOL behind the DEFLATE gate, T4 doorbell-time ERR_TABLE). Gate
`hw-review findings resolved` should stay open until T1–T5 are folded in.

## Resolutions (author, same day)

- T1 (must): §4 rewritten — `syms` includes the EOB (execution-verified); SYMBOLS = len(syms),
  K1 denominator 148,271, no TYPE-0 EOB beat. Error prefixes known by construction.
- T2 (must): F-14 reset row (test_reset, cg_reset) + F-15 protocol-agent row added; PRD-F14/15/16
  mapped in §7.
- T3 (must): R23 is the first committed dv_bringup task; test_deflate + ERR_SYMBOL are must;
  the §5 waiver pre-authorization removed.
- T4 (must): F-26 doorbell ERR_TABLE (badlen + DEFLATE 16..20 + kraft bins).
- T5 (must): SYMBOL_LIMIT expectations derived scoreboard-side (first-LIMIT-beats truncation +
  tie rule) — golden stays frozen; mechanism recorded.
- Shoulds accepted as bring-up refinements except the golden-prefix retrieval note (folded into
  T1's construction rule).

### Summary: 0 must open
