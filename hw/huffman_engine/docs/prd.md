# huffman_engine — PRD (Product Requirements Document)

Status: **approved** 2026-08-28 (PRD checkpoint). Stage 1 of `hw/FLOW.md`.
Vocabulary: `hw/CONTEXT.md`. Decisions: ADR-0001 (bus family, proposed), ADR-0003 (decoder
architecture + HW/SW boundary, accepted). Research: `research/hw-algorithms-pyflate.md`;
software findings: `dev/pyflate/FINDINGS.md` (Matan). Interview record: `prompt.txt` 2026-08-28
(rounds Q1–Q12). All numbers below are printed by `golden/calibrate.py`.

## 1. Purpose and workload slice

`huffman_engine` is a memory-mapped, stream-attached canonical-Huffman decoder that replaces the
per-symbol decode loop of pyflate (`dev/pyflate/t0_stock.py::decode_huffman_block` →
`HuffmanTable.find_next_symbol`, and the `RBitfield` bit reader) for bzip2 blocks, and the
equivalent DEFLATE symbol decode (`gzip_main`) for gzip streams. Per invocation it consumes the
raw compressed bit stream of one block from a start bit offset, builds its Huffman tables from
code lengths delivered by software, follows the selector list, and emits the symbol stream to
`mtf_cam` (bzip2) or to memory.

**Workload slice** — benchmark input `benchmarks/bm_pyflate/data/interpreter.tar.bz2`:
67,562 B (540,496 bits), **1 bzip2 block**, 6 tables, alphabet 147, **148,271 Huffman symbols**
(89,837 MTF literals + 58,433 RUNA/RUNB + EOB), 2,966 selectors, symbol codes = 531,571 bits =
98.35 % of the stream, mean **3.585 bits/symbol**, lengths used 2..15 (never 16–20).

Profile shares (`results/perf_report_pyflate.txt` is interpreter-level: `_PyEval_EvalFrameDefault`
23.29 % l.12; the function-level split comes from cProfile, `dev/pyflate/FINDINGS.md` §3 and the
calibration agent's run on this machine):

Self-time (tottime) shares, stock pyflate, cProfile of one decode (calibration agent, this machine):

| Stage | Functions | Self time | Replaced by |
|---|---|---|---|
| Huffman symbol decode | `find_next_symbol` 12.0 % | 12.0 % | **huffman_engine** |
| bit reader | `snoopbits`, `readbits`, `_mask`, `needbits`, `_more`, `_read`, `read` | 37.6 % | **huffman_engine** |
| MTF | `move_to_front` 11.4 % | 11.4 % | `mtf_cam` |
| block loop body (selector walk, RUNA/RUNB, list appends) | `decode_huffman_block` self 18.9 % | 18.9 % | huffman_engine (selectors) + `mtf_cam` (runs) |
| inverse BWT | `bwt_reverse`, `bwt_transform`, `sorted` | 15.7 % | software (non-target) |
| RLE4, join, MD5, headers | rest | ~4 % | software |

So **this module's slice = 49.6 %** (decode + bit reader) and the **Huffman+MTF loop = 79.9 %** of
stock (0.372 s local; VM 3.10: 1.13 s, `results/baseline_pyflate_stats.txt:19`). In Matan's T3
(landed `run_benchmark.py`, 0.119 s local, VM pending) the loop is fused: `decode_huffman_block`
≈ 39 % (Huffman + MTF + runs, not separable), inverse BWT ≈ 37 %, RLE4 + rest ≈ 12 %. The inverse
BWT is a deliberate non-target (ADR-0003, §6); the Amdahl chain stock → T3 → T3 + HW is K4.

## 2. KPIs

| KPI | Unit | Requirement | Stretch | Measured by |
|---|---|---|---|---|
| K1 sustained decode rate over the benchmark block, doorbell → DONE (table builds, selector switches, refills included) | cycles/symbol | **≤ 1.10** (block ≤ 163,100 cycles); provisional — confirmed or tightened at uArch (Yuval, Q3) | 1.033 = cycle model 153,121 / 148,271 (assumptions: serial builds 6 × 314, switch = 1 cycle, refill = 0, extra bits = 0 — each to be confirmed at uArch) | `CYCLES / SYMBOLS` registers, `test_full_benchmark` |
| K2 table build, per table, from accepted doorbell (tables are built serially after the doorbell; first symbol after N_TABLES × K2) | cycles/table | **≤ 2 × ALPHABET + MAXLEN** (= 314 for 147/20 ⇒ ≤ 1,884 before the first beat, 1.27 % of the block) | overlap builds with the last configuration writes | `BUILD_CYCLES` register; doorbell → first `m_sym` beat ≤ N_TABLES × K2 + 16 in `test_driver` |
| K3 clock, sky130_fd_sc_hd tt_025C_1v80 | MHz | **≥ 50** | 100 (reported design point) | `make ppa` STA |
| K4a block decode time of this module vs its own software slice (Huffman + bit reader, 49.6 % of stock) | ms | 153,121 cycles @ 50 MHz = **3.06 ms** vs 185 ms (stock, local) | 1.53 ms @ 100 MHz | K1 + `docs/integration.md` |
| K4b end-to-end speed-up of huffman_engine + `mtf_cam` together (SoC-peripheral model, driver ≤ 1 ms, `mtf_cam` adds ≤ 0.34 M cycles = 6.7 ms @ 50 MHz for 336,184 L-bytes) | × | vs stock ≈ 0.372 / (0.372 − 0.297 + 0.0031 + 0.0067 + 0.001) ≈ **4.3×**; vs T3 ≈ 0.119 / (0.119 − 0.046 + 0.011) ≈ **1.4×** (Amdahl: iBWT + RLE4 remain in software) | — | `test_driver` cycle model; VM numbers replace local ones when Matan measures them |
| K5 standard-cell area (no macros) | mm² | soft ceiling 1.0 (flagged, not gating); compared with published decoders in `docs/ppa.md` (Yuval, Q11) | — | `make area`, OpenLane |
| K6 power | mW | report only | — | OpenLane |

## 3. Functional requirements

| Id | Statement | Measurable KPI (unit) | Acceptance test | Source |
|---|---|---|---|---|
| PRD-F1 | One invocation decodes one block. bzip2 mode: the first selector is consumed before symbol 0, a new selector every 50 symbols, decode stops after emitting EOB (= ALPHABET − 1; EOB may be symbol 0). DEFLATE mode: literal / length+distance events until EOB (256). Ordering is semantic (F2 bit-exactness); the implementation may pipeline aligner, cascade and lookup. | symbol stream == golden trace (0 mismatches, exact count) | `test_full_benchmark`, `test_deflate` | `t0_stock.py::decode_huffman_block`, `gzip_main` |
| PRD-F2 | Canonical Huffman decode by comparator cascade: for the window of the next MAXLEN bits, the shortest length l with first_code[l] ≤ code < first_code[l] + count[l] wins; symbol = symtab[base[l] + code − first_code[l]]. first_code per RFC 1951 §3.2.2 (bzip2 uses the same rule: codes by increasing length, then symbol index). Bit-exact to `golden/canonical_model.py`. | 0 differing symbols, lengths or consumed-bit counts vs the emulation model | `test_smoke`, `test_random` | ADR-0003 |
| PRD-F3 | Tables are built in hardware, after the accepted doorbell, from code-length vectors written by software: 5-bit lengths, valid 0..MAXLEN (0 = unused symbol), MAXLEN = 20 (bzip2) / 15 (DEFLATE). | count/first_code/base/symtab (debug-readable) == emulation model; K2 | `test_random`, `test_driver` | ADR-0003 |
| PRD-F4 | Input: raw compressed bytes on `s_bits` (32-bit beats, TLAST on the last beat); the first symbol starts at bit `START_BIT` of the buffer (bit 0 = first byte's MSB in bzip2 mode, LSB in DEFLATE mode); bzip2 codes are read MSB-first, DEFLATE codes bit-reversed LSB-first, DEFLATE extra bits LSB-first integers. After TLAST the aligner pads the window with zeros so a final code shorter than MAXLEN decodes; over-fetch beyond the last consumed bit is ≤ 4 beats and reported in OVERFETCH (unit: 32-bit beats). | consumed bits == golden `end_bit − sym_start_bit` (exact); OVERFETCH ≤ 4 | `test_random`, `test_full_benchmark`, `test_deflate` | golden trace; review R5 |
| PRD-F5 | Output on `m_sym`, one beat per symbol/event: bzip2 = symbol (≥ 9 bits; exact encoding shared with `mtf_cam`, MAS); DEFLATE = {literal 8-bit} \| {length 9-bit (3..258), distance 16-bit (1..32768), extra bits added} \| {EOB}. TLAST on EOB. | stream == golden events (0 mismatches) | `test_full_benchmark`, `test_deflate` | Q5, Q10; review R1 |
| PRD-F6 | Back-pressure: `m_sym.tready` low stalls the decoder, `s_bits.tvalid` or `s_sel.tvalid` low stalls it; no beat is lost or duplicated; `tvalid` never depends combinationally on `tready`. | 0 mismatches under random stalls (0–90 % duty) on both ports; protocol assertions 0 | `test_random` (stall mode), `test_driver` | Q7 |
| PRD-F7 | Configuration per invocation via AXI-Lite: MODE (0 bzip2 / 1 DEFLATE), START_BIT (32-bit), ALPHABET (9-bit), N_TABLES (1..6), lengths window (N_TABLES_MAX × ALPHABET_MAX × 5 bit, packed continuously 6 lengths per word, table-major → 147 words for the benchmark), SYMBOL_LIMIT (32-bit, default 2^20, valid 1..2^27). Selectors arrive on the `s_sel` AXI-Stream slave (8-bit beats, low 3 bits, TLAST on the last selector), one consumed per 50 symbols; TLAST is the only terminator (no count register); after EOB the engine drains and ignores any surplus beats up to TLAST before DONE, so nothing leaks into the next invocation. DEFLATE mode: N_TABLES = 2; table 0 = literal/length, occupying length indices 0..ALPHABET−1 (ALPHABET = HLIT + 257, 257..288), table 1 = distance, the next 30 indices (fixed distance alphabet 30, unused = 0); EOB fixed at 256; selectors ignored (`s_sel` not read). | all fields round-trip (0 mismatches); benchmark config = 147 length words + 2,966 `s_sel` beats | `test_driver` | Q4, Q7; review R6, R13 |
| PRD-F8 | Capacity parameters (defaults verified): ALPHABET_MAX = 288, MAXLEN = 20 (bzip2) / 15 (DEFLATE), N_TABLES_MAX = 6, selectors streamed (no on-chip list; bzip2 maximum 18,002 per block), SYMBOL_LIMIT 32-bit. | benchmark block (147 / 6 / 2,966 selectors) and DEFLATE (ALPHABET 288 + 30 distance lengths / 2 tables) accepted | `test_full_benchmark`, `test_deflate` | Q9; review R13 |
| PRD-F9 | Doorbell-time rejection (sticky flag, no BUSY/DONE/IRQ, counters hold, state unchanged): ERR_PARAM — ALPHABET < 3 or > ALPHABET_MAX, N_TABLES outside 1..N_TABLES_MAX, SYMBOL_LIMIT = 0 or > 2^27, MODE = 1 with N_TABLES ≠ 2 or ALPHABET < 257; ERR_TABLE — any length > MAXLEN (lengths 21..31 in the 5-bit field), or an over-subscribed table (Σ 2^−l > 1). Incomplete tables (Σ < 1, incl. a single 1-bit code) and an all-zero DEFLATE distance table are legal. | each case injected once → flag set, 0 output beats, BUSY = 0 | `test_corner` | Q9; review R2, R12 |
| PRD-F10 | Run-time errors stop the engine at the offending symbol: ERR_NOCODE (no length matches within MAXLEN bits), ERR_SELECTOR (selector value ≥ N_TABLES at first use, or `s_sel` TLAST already consumed when a new selector is needed before EOB), ERR_SYMBOL (DEFLATE literal/length ≥ 286 or distance ≥ 30; length code 284 + extra 31 decodes as 258 like pyflate), ERR_LIMIT (SYMBOL_LIMIT beats without EOB), ERR_UNDERRUN (a consumed bit lies beyond the last received bit). Post-error state: BUSY = 0, DONE = 0, ERR flag set, IRQ asserted, no TLAST emitted, CYCLES/SYMBOLS/BITS frozen at the offending symbol; recovery by the next accepted doorbell (flags W1C). The golden model raises Python exceptions at these points; hardware sets the flag instead. | flag set, SYMBOLS == symbols before the error, 0 beats after it, IRQ within 2 cycles | `test_corner` | Q9; review R3, R4 |
| PRD-F11 | Control semantics (own statement, mirrors grape): DOORBELL accepted only when idle; DOORBELL while BUSY, and any configuration write (MODE, START_BIT, ALPHABET, N_TABLES, lengths, SYMBOL_LIMIT) while BUSY, is ignored and sets ERR_BUSY; configuration registers read back the values latched at the doorbell while STATUS and the F12 counters are live. ABORT: takes effect within 8 cycles when decoding or stalled by `tready`/`tvalid`, within 16 cycles during a table build; ABORTED + IRQ; no TLAST; counters hold; ABORT while idle is a no-op; DOORBELL + ABORT in one write → ABORT wins; ABORT arriving after EOB → DONE only. DONE/ABORTED/ERR_* and the IRQ are W1C; an accepted doorbell clears none of them. Reset (synchronous, active-low) at any time returns to idle with every register zero. | each rule one directed check; latencies measured in cycles | `test_driver` | grape PRD F9–F12/F15; review R7 |
| PRD-F12 | Counters, read-only: CYCLES (64-bit, accepted doorbell → DONE/ABORTED/ERR inclusive), SYMBOLS (32-bit, beats emitted), BITS (32-bit, bits consumed since START_BIT), BUILD_CYCLES (16-bit, longest single table build of the invocation), OVERFETCH (8-bit, beats). With SYMBOL_LIMIT ≤ 2^27 (F9) no counter overflows: BITS ≤ 2^27 × 20 < 2^32, CYCLES ≤ 2^27 × 20 ≪ 2^64. | == testbench counts (exact) | `test_driver`, `test_full_benchmark` | Q9; review R13, R14 |
| PRD-F13 | Multi-block streams: one invocation per block; the next block's header starts at bit START_BIT + BITS of the same buffer and is parsed by software, which issues the next doorbell with the new START_BIT and lengths. | 2-block synthetic bzip2 stream decodes both blocks == golden; surplus `s_sel` beats of block 1 do not affect block 2 | `test_corner` | Q9; review R14 |
| PRD-F14 | Bus verification: AXI-Lite and all three AXI-Stream ports are checked by independent protocol agents (`cocotbext-axi` master/slave, stream source/sink with protocol assertions), never only by datapath results. | 0 protocol violations across all tests | all tests | Q7 |
| PRD-F15 | Reference models: golden = instrumented stock pyflate (`golden/pyflate_ref.py`) cross-checked against libbzip2 (`bz2`) / zlib on every run; predictor = independent emulation model (`golden/canonical_model.py`). The scoreboard compares DUT vs predictor and predictor vs golden trace, so a golden error is caught too (Yuval, Q8). | `calibrate.py`: stock == bz2; emulation == stock trace exactly (148,271 bzip2 symbols; 11 DEFLATE block bodies incl. end bits, one multi-block and one stored stream) | `golden/calibrate.py` (software), `test_full_benchmark` | Q8; review R8 |
| PRD-F16 | Single clock, synchronous active-low reset (as grape). | — | `test_driver` | ADR-0001 |

## 4. HW/SW split

| Function (pyflate bzip2 path) | HW / SW | Data crossing per block |
|---|---|---|
| stream header, block magic/CRC, `randomised`, origPtr, `used` bitmap (`compute_used`) | SW | — |
| selector list unary + inverse-MTF (`compute_selectors_list`) | SW → `s_sel` stream | 2,966 × 8-bit beats |
| delta-coded code lengths (`compute_tables` bit loop) | SW → lengths window | 6 × 147 × 5 bit → 147 words |
| table build (count/first_code/base/symtab) | **HW** | — |
| bit aligner + symbol decode + selector FSM (`RBitfield`, `find_next_symbol`, 50-symbol switch) | **HW** | in: 16,891 × 32-bit beats (67,562 B); out: 148,271 symbol beats |
| MTF + RUNA/RUNB expansion | `mtf_cam` (next module) | symbol stream on-chip |
| inverse BWT, RLE4, MD5 | SW (non-target, ADR-0003) | L-vector 336,184 B from `mtf_cam` DMA |
| DEFLATE: gzip header, block type, HLIT/HDIST/HCLEN, code-length-code decode → lit/dist lengths | SW | ALPHABET + 30 lengths (≤ 318 → 53 words) |
| DEFLATE: symbol decode incl. extra bits | **HW** | events out |
| DEFLATE: LZ77 window copy, stored blocks | SW (stretch HW block) | — |

Per benchmark block: 147 length words + ~10 control words = 157 AXI-Lite transactions ≈ 628 bus
cycles (0.41 % of the 153,121-cycle model; 4 cycles/transaction assumed, measured at MAS); the
three streams are moved by platform DMA outside this module (testbench-modelled, as grape).

## 5. Interfaces (PRD level; detail in MAS)

- 32-bit AXI4-Lite slave: control/status/counters, lengths window (ADR-0001).
- AXI4-Stream slave `s_bits` (32-bit, TLAST at end of buffer) — compressed bytes.
- AXI4-Stream slave `s_sel` (8-bit, TLAST at end of list) — selectors, bzip2 mode only.
- AXI4-Stream master `m_sym` (bzip2: ≥ 9-bit symbol; DEFLATE: 8-bit literal / 9 + 16-bit length,
  distance / EOB, with type bits; TLAST on EOB) — consumed by `mtf_cam` or by DMA.
- One clock, `rst_n`; one level IRQ.
- Data volume per benchmark block: 67,562 B + 2,966 B in, 148,271 beats out, 628 B config.

## 6. Non-goals

- Inverse BWT, RLE4, CRC/MD5 in hardware (ADR-0003; report §7 carries a quantified iBWT sketch).
- Header/length/selector parsing in hardware (1.65 % of stream bits; software, = Rust FFI boundary).
- LZ77 window copy (stretch block only), stored blocks, gzip framing — software.
- Multi-symbol/speculative decode, 2^k LUT decode (PPA comparison only if time allows).
- On-chip selector storage (streamed instead; 18,002 × 3 bit would be 54 kbit of flops).
- bzip2 `randomised` blocks (unsupported by pyflate too).

## 7. Acceptance tests (names reused by `hw-dv-testplan`)

| Test | Checks | Requirements |
|---|---|---|
| `test_smoke` | one hand-made 4-symbol table, 8 symbols, bzip2 mode, no stalls; == emulation model | F1, F2, F3 |
| `test_random` | random Kraft-valid and incomplete tables (bzip2 alphabet 3..258; DEFLATE lit 257..288, dist 1..32, lengths ≤ MAXLEN of the mode), random symbol sequences encoded by the testbench encoder, random selectors, both modes, random ready/valid stalls; == emulation model | F2–F8 |
| `test_full_benchmark` | the shipped block: symbol stream == golden trace (148,271), BITS == 531,571, K1 from CYCLES/SYMBOLS | F1, F4, F5, F12, K1 |
| `test_deflate` | zlib-generated dynamic + fixed blocks (≥ 10 streams incl. a single-distance-code table and a literal-only block): events == golden trace incl. extra bits and end bit | F1, F4, F5 |
| `test_driver` | register round-trip, doorbell/BUSY/ABORT (decoding, stalled, during build)/IRQ/reset, K2 build cycles, counters, protocol agents on all four ports | F6, F7, F11, F12, F14, F16 |
| `test_corner` | every ERR_* of F9/F10 injected (incl. 284+31, lit 286, dist 30, ALPHABET 3 and 288, N_TABLES 1 and 6, 18,002 selectors, `s_sel` TLAST early / surplus beats, SYMBOL_LIMIT 0 and 2^27, MODE=1 with N_TABLES≠2, EOB as symbol 0, single 1-bit-code table, empty distance table); 2-block stream; OVERFETCH bound | F1, F8, F9, F10, F13 |

## 8. Open questions (carried to MAS / uArch)

1. `m_sym` beat encoding shared with `mtf_cam` (symbol + type bits) — MAS, with the mtf_cam PRD.
2. Lengths window as memory-mapped registers vs a small RAM; whether `s_sel` and `s_bits` share one DMA channel — MAS.
3. K1 final number and the ≥ 0.9 → 1.0 sym/cycle stretch; cycle-model assumptions (selector switch, refill) — uArch.
4. VM timings for K4 (Matan) and the area comparison set for K5 (Intel IAA, AMD Vitis, Ledwon & Cockburn) — PPA.

## 9. Review findings

See `docs/review_prd.md`.

## Errata (post-approval, from the MAS review 2026-08-30)

- PRD-F9: an **over-subscribed table** (Σ 2^−l > 1) cannot be detected at doorbell time — the
  count pass of the hardware build is what computes the sum. MAS §8 defines it as a build-time
  ERR_TABLE (BUSY 1 → 0, no beats, counters stop at the failing table). Length > MAXLEN remains a
  doorbell-time rejection. `test_corner` follows the MAS definition.
- PRD-F9 "no BUSY/DONE/IRQ" on a doorbell-time rejection: "no IRQ" means no *DONE* interrupt; the
  ERR_PARAM / ERR_TABLE flags do assert `irq` when their IRQ_EN bit is set (ADR-0005 mask rule,
  uniform across modules; MAS §2/§8).
