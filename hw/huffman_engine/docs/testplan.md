# huffman_engine — DV testplan (stage 5)

Inputs: `docs/prd.md` (PRD-F1..F13, K1 ≤ 1.1 cyc/sym, K2 ≤ 2·ALPHABET+MAXLEN), `docs/mas.md`
§2/§4/§8 + Amendments, `docs/uarch.md` (review-hardened), `rtl/` (built; 37 unit+smoke tests),
`golden/` (frozen: `pyflate_ref.trace_benchmark()`, `canonical_model.decode_bzip2_symbols/
decode_deflate_symbols`). RTL-review carry-ins: R23 (DEFLATE byte-order spec question —
resolve HERE before any DEFLATE test), R16 (DEFLATE limit counting), K1 measured on the REAL
6-table benchmark at bring-up (hw-dv-bringup rule, grape lesson). `--assert` armed.

## 1. Feature list

`F-01..F-13` ↔ PRD-F1..F13. Added: `F-20..F-25` (FSM arcs, MAS §8 rows, RTL-review boundary
regressions), `F-30..F-32` (KPI/counter properties).

## 2. Matrix

| Feature | Test (directed / random sequence) | Covergroup + bins | Checker | Prio | Status |
|---|---|---|---|---|---|
| F-01 one block, selector cadence (PRD-F1) | `test_smoke` (1 table, tiny alphabet); `test_bench_block` (real benchmark block) | `cg_cfg`: n_tables {1..6}, alphabet {3,4,50,147,288}; `cg_sel`: switch count {0,1,many}, same-table-consecutive bin | scoreboard: m_sym symbol stream == golden trace (table_id, code_len, symbol) EXACT per beat; selector cadence via trace table_ids | must | todo |
| F-02 canonical decode (PRD-F2) | `test_bench_block`; `test_random` (`seq_rand_tables`: random Kraft tables + random symbol streams encoded by the TB) | `cg_len`: decoded length {1..20} each; len-20 and len-1 adjacency bins | golden `canonical_model` decode of the same window sequence; unit decoder TB already exact | must | todo |
| F-03 HW table build (PRD-F3) | every test (builds implicit); `test_errors::kraft` | `cg_build`: alphabet bins, N_TABLES bins, BUILD_CYCLES read | BUILD_CYCLES == ALPHABET+MAXLEN (K2 row); ERR_TABLE on over-subscription; DBG reads vs golden Table (kinds 0..3) | must | todo |
| F-04 s_bits framing, START_BIT, BITS (PRD-F4) | `test_smoke` (START_BIT 0/word±1); `test_bench_block` (real 8,844) | `cg_bits`: start_bit {0, mod32=0, ±1, ~9k}, tkeep tail {1,2,3,4 bytes} | BITS == sum of consumed code bits (golden trace end − start); framing via aligner unit TB + protocol agent | must | todo |
| F-05 m_sym beat encoding / ADR-0006 (PRD-F5) | all tests (checked per beat); `test_chain_contract` (withdrawal visible to a stub sink) | `cg_beat`: TYPE {0,3} (bzip2), value ranges, TLAST | beat fields vs golden trace symbol; EOB beat = TYPE 3, value ALPHABET−1, TLAST | must | todo |
| F-06 backpressure lossless (PRD-F6) | `test_random` with random tready/tvalid gaps on all three streams | `cg_bp`: stall source {m_sym, s_bits, s_sel} × duration {1,2..10,long} | stream exactness under all gap patterns (scoreboard unchanged); tvalid !comb on tready (protocol agent) | must | todo |
| F-07/F-08 config + capacities (PRD-F7/F8) | `test_random` (random legal configs); capacity corners in `test_bench_block` (147/20/6) + `test_corner::alphabet_288` | `cg_cfg` crosses | round-trips (regs unit TB); decode exactness per config | must | todo |
| F-09 doorbell rejection (PRD-F9) | `test_errors::param` (each ERR_PARAM clause incl. SYMBOL_LIMIT 0 / 2^27+1, DEFLATE N_TABLES≠2) | `cg_err`: each ERR_PARAM clause | sticky flag only, no BUSY/DONE/IRQ, counters hold, reject-fix-accept | must | todo |
| F-10 run-time errors (PRD-F10) | `test_errors::{nocode, selector, underrun, limit}` — directed streams engineering each | `cg_err`: {NOCODE, SELECTOR (range + exhausted), UNDERRUN (mid-code + PREP), LIMIT, TABLE}; error-at-symbol bins {0, mid, near-EOB} | stop at the offending symbol: SYMBOLS/BITS exact to the golden prefix; withdrawal (no beat past the error); ERR_LIMIT emits exactly LIMIT beats (drain-style, uArch N3) | must | todo |
| F-11 control semantics (PRD-F11) | `test_abort` (PREP/DECODE/DRAIN aborts incl. after-EOB-handshake DONE-wins); `test_errors::busy_writes` | `cg_ctrl`: CTRL combos × state; abort-in {PREP, DECODE, DRAIN-pre-EOB, DRAIN-post-EOB}; `cg_irq` | bounds ≤ 8/16 cycles (cycle-stamped); MAS §8 disposition rows; sticky/W1C/irq pin (grape pattern) | must | todo |
| F-12 counters (PRD-F12) | all; `test_bench_block` for CYCLES/K1 | `cg_counters`: CYCLES, SYMBOLS, BITS, BUILD_CYCLES, OVERFETCH read {idle, busy} | SYMBOLS == beats handshaken; CYCLES inclusive; OVERFETCH == accepted − ceil((START_BIT+BITS)/32) (clamped) | must | todo |
| F-13 multi-block (PRD-F13) | `test_multiblock`: two invocations on one buffer, second START_BIT = prev + BITS (+ SW header math from the golden trace) | `cg_b2b`: {reuse-buffer, new-tables, stale-sticky-survives} | both blocks trace-exact; aligner lifecycle (R7 regression: tready rises again) | must | todo |
| F-20 ctrl FSM arcs (uarch §3.1) | union of directed tests | `cg_fsm`: every arc incl. PREP∥SKIP orderings (build-first, skip-first), DRAIN rescue | FSM monitor: legal arcs only | must | todo |
| F-21 selector boundaries (R3/N4/N10 regressions) | `test_sel_boundary`: skid-empty at symbol 0 and at a 50-boundary (DMA stalled), exhaustion, out-of-range at boundary | `cg_sel` boundary bins {entry, 50k-refill, exhausted} | 50 symbols per set exactly (trace table_ids); stall-not-corrupt; ERR_SELECTOR cases | must | todo |
| F-22 aligner tail/underrun (R9/N1) | `test_errors::underrun` (code straddling last bit; EOB-lookalike over zero-pad) | `cg_bits` tail bins {exact-end, mid-code, pad-match} | ERR_UNDERRUN (never a phantom beat, never a false EOB/DONE) | must | todo |
| F-23 skid/withdrawal (ADR-0006, R1/R18) | `test_chain_contract` (backpressured error; doorbell with parked beat) | `cg_beat` withdrawal bin | un-handshaken beat never observable; SYMBOLS excludes it; ERR_LIMIT exempt (beats = LIMIT) | must | todo |
| F-24 DBG window (MAS 0x114/0x118, R10/N5) | `test_dbg`: all kinds × in/out-of-range × pre-build | `cg_dbg`: kind × validity | kinds 0..3 vs golden Table; zeros per MAS validity rules | should | todo |
| F-25 DEFLATE mode (PRD-F5/F7 DEFLATE clauses; R16/R23) | `test_deflate`: fixed-Huffman stream + a dynamic one via `decode_deflate_symbols`; **R23 (byte-order reconciliation) is the FIRST dv_bringup task** — a committed schedule, not a waiver (review T3) | `cg_deflate`: {literal, length+extra bins, distance+extra bins, EOB-256, invalid-286/7} | golden DEFLATE trace exact; TYPE 1/2/3 beats; **ERR_SYMBOL (STATUS bit 13 — the only source; must)** | must | todo |
| F-26 doorbell ERR_TABLE: length > MAXLEN / DEFLATE bins 16..20 (MAS bit 10, uArch N14/N9) | `test_errors::badlen` (field 21..31 written; DEFLATE table with a 16..20 length) | `cg_err`: {TABLE.badlen, TABLE.deflate16_20, TABLE.kraft} | sticky ERR_TABLE at the doorbell, no BUSY; reject-fix-accept | must | todo |
| F-30 K1 on the real block (KPI; bring-up rule) | `test_bench_block` at bring-up (not deferred!) | `cg_counters` K1 bin {≤1.1, >1.1} | CYCLES/SYMBOLS ≤ 1.1 with builds+skip included (model: 1.0068); enforced | must | todo |
| F-31 K2 (KPI) | every build | — (checked) | BUILD_CYCLES ≤ 2·ALPHABET+MAXLEN; == ALPHABET+MAXLEN expected | must | todo |
| F-32 first-symbol latency (PRD-F1 window) | `test_bench_block` (cycle-stamp first beat) | — | ≤ max(N_TABLES·K2, ⌈START_BIT/32⌉) + margin 8 (uArch §7 1,004) | should | todo |
| F-14 mid-run synchronous reset (PRD-F16, MAS §8 reset row) | `test_reset` (reset in PREP / DECODE / DRAIN; grape pattern) | `cg_reset`: state at reset {prep, decode, drain} | post-reset full readback at reset values; streams tready/tvalid drop ≤ 1 cycle; re-run trace-exact | must | todo |
| F-15 independent protocol agents (PRD-F14) | all tests (cocotbext-axi AXI-Lite + AxiStream monitors on s_bits/s_sel/m_sym) | `cg_axi`: resp codes, strobe subsets, tkeep patterns | protocol assertions independent of the drivers (grape monitor pattern) | must | todo |

## 3. Env plan (pyuvm)

- **Tests** (`tb/tests/`): `test_smoke`, `test_bench_block`, `test_random`, `test_errors`,
  `test_abort`, `test_sel_boundary`, `test_multiblock`, `test_chain_contract`, `test_dbg`,
  `test_deflate` (gated). `HuffBaseTest` extends common `base_test`.
- **Env** `HuffEnv`: shared `axi_lite_agent` (with the grape-built passive monitor);
  `stream_agent` instances driving `s_bits` and `s_sel` (masters with gap injection) and
  monitoring `m_sym`; `HuffScoreboard` (replay-style, grape pattern): mirrors config writes,
  runs the golden decode at doorbell, compares every `m_sym` beat in order (trace-exact
  policy), checks sticky STATUS via a full mirror (BUSY-fall completion — grape S1 lesson),
  counters incl. the OVERFETCH formula.
- **Sequences** (`tb/sequences/`): `seq_program` (config + lengths window), `seq_stream`
  (bit-packer: encodes a symbol list into beats from a table — the TB's encoder, checked
  against `canonical_model` round-trip), `seq_rand_tables`, `seq_abort_at`, `seq_gaps`.
- **Vectors**: the benchmark block's beats/selectors/lengths dumped once from
  `trace_benchmark()` into `tb/vectors/` (start_bit 8,844; 148,271 symbols).
- **ConfigDB**: `dut`, `clk_period_ns` (20), `golden` (canonical_model + pyflate_ref),
  `k1_enforce` (True for `test_bench_block` only — grape pattern).

## 4. Golden-model interface

Per accepted doorbell the scoreboard calls (bzip2):
```python
syms, end_bit, _ = canonical_model.decode_bzip2_symbols(stream_bytes, start_bit,
                                                        lengths_per_table, selectors,
                                                        alphabet)
```
- **`syms` INCLUDES the EOB as its last element** (review T1, verified by execution: the
  benchmark's 148,271 symbols end with 146 = ALPHABET−1). Expected beats: TYPE 0 for
  `syms[:-1]`, then ONE TYPE 3 beat for `syms[-1]` (value ALPHABET−1, TLAST) — a TYPE 0 beat
  never carries the EOB value (MAS §2). Compare per beat, in order, exact.
- BITS expected = `end_bit − start_bit`; **SYMBOLS = len(syms)** (the EOB beat is the last
  element, not an extra); K1 denominator = 148,271 on the benchmark. Errors compare against a
  known prefix: directed error streams are CONSTRUCTED so the pre-fault symbol list is known
  by construction (the golden raises and discards partial output — review should-fix).
- The benchmark input for sign-off: every symbol of the block in `interpreter.tar.bz2`'s
  trace (`trace_benchmark()`), plus the multi-block contract via START_BIT arithmetic.
- **SYMBOL_LIMIT (T5)**: the frozen golden takes no limit argument — the scoreboard derives
  the expectation itself: expected beats = the first LIMIT beats of the full golden stream;
  if beat LIMIT is the EOB, expect DONE (tie rule, uArch §2/N3), else ERR_LIMIT with exactly
  LIMIT beats emitted. No golden change needed (golden/ stays frozen; the MAS 0x110 note's
  "model gets the same check" is satisfied by this derivation — recorded as the mechanism).
- **R23 gate (DEFLATE)**: before any DEFLATE test, reconcile ADR-0008 #2 / the aligner's
  MSB-first ingest with RFC 1951's LSB-first bit packing against
  `canonical_model.decode_deflate_symbols` on a known-good gzip fragment; amend MAS/uArch
  with the outcome. Until then `test_deflate` stays gated (DEFLATE has no KPI and no
  benchmark input; PRD-F5 DEFLATE clauses are verified by that test when it lands).

## 5. Coverage goals

Line/toggle ≥ 90 % over `rtl/*.sv` minus the two `_tb_top` wrappers (excluded as non-DUT);
functional bins of §2 all hit; exclusions inline `coverage_off` with reasons (grape
discipline). DEFLATE paths are NOT pre-waived: R23 resolves at bring-up (F-25) and the
DEFLATE bins close at coverage like every other group.

## 6. Formal properties

| Property | File | Note |
|---|---|---|
| ctrl FSM arcs + DONE/ERR/ABORT reach IDLE | `formal/ctrl_arcs.sv` | grape fsm_arcs pattern; BMC+cover |
| output skid: no beat loss/dup under valid/ready (incl. flush exemption) | `formal/skid.sv` | small, self-contained |
| aligner occupancy invariant (accepted−consumed ≤ 128) | `formal/aligner_cap.sv` | the U9 proof, mechanized |

Fallback per FLOW ("none with reason") if smtbmc chokes: the aligner/skid unit TBs plus the
protocol agent stand in; record at sign-off.

## 7. Traceability

PRD-F1..13 ↔ F-01..13; PRD-F14 ↔ F-15; PRD-F15 = the golden itself (§4, frozen);
PRD-F16 ↔ F-14; MAS §8 rows ↔ F-09/F-10/F-11/F-23/F-26 + F-14 (reset row); uArch §3 arcs ↔ F-20/F-21;
RTL-review carry-ins ↔ F-21 (N4/N10), F-22 (R9/N1), F-23 (R1/R18), F-24 (R10/N5), F-25
(R16/R23); K1/K2 ↔ F-30/F-31 (measured at bring-up on the real block — the grape sign-off
lesson, now a skill rule).
