# mtf_cam — PRD (Product Requirements Document)

Status: **approved** 2026-08-30 (PRD checkpoint). Stage 1 of `hw/FLOW.md`.
Vocabulary: `hw/CONTEXT.md`. Decisions: ADR-0001 (bus family, proposed), ADR-0003 (iBWT stays in
software), ADR-0004 (chained module, expander width parameter, accepted). Research:
`research/hw-algorithms-pyflate.md` §2; `dev/pyflate/FINDINGS.md` §0, §1e. Interview record:
`prompt.txt` 2026-08-29 (rounds Q1–Q9). All numbers below are printed by `golden/calibrate.py`.

## 1. Purpose and workload slice

`mtf_cam` is the second pyflate accelerator: it consumes the bzip2 symbol stream produced by
`huffman_engine` (RUNA, RUNB, MTF symbols, EOB), maintains the block's move-to-front list, expands
zero runs, and emits the **L-vector** (the inverse-BWT input) as a byte stream to platform DMA.
It replaces `move_to_front` and the run/MTF part of `decode_huffman_block` in
`dev/pyflate/t0_stock.py` (lines 411–429, 274). Software keeps the `used`-map parse (it writes the
256-bit map), the inverse BWT (non-target, ADR-0003), RLE4 and MD5.

**Workload slice** (benchmark block): input 148,271 symbols = 89,837 MTF + 58,433 RUNA/RUNB + EOB;
output **336,184 L-bytes** = 89,837 MTF bytes + 246,347 run bytes (73.3 %) from 34,664 run groups.
MTF rank: mean 7.17, p50 3, p90 17, p99 62, max 144, rank 0 never (zeros are runs), rank 1 = 30.4 %.
Runs: length mean 7.11, p50 2, max 8,157; ≤ 12 run symbols per group. 145 used byte values.

Software share (self time, cProfile; `dev/pyflate/FINDINGS.md` §3, §1e): stock `move_to_front`
0.110 s / 92,803 calls ≈ 9.3 % of the 1.186 s profile plus the run/MTF control inside
`decode_huffman_block` (18.9 % self, shared with the selector walk); the 3-slice MTF alone costs
80.4 ms for this trace (§1e). T3: `list.pop` + `list.append` + `bytearray.append` ≈ 0.030 s ≈ 10.5 %
of 0.285 s. With `huffman_engine`, the two modules cover the stock loop's 79.9 % (huffman PRD §1).

## 2. KPIs

| KPI | Unit | Requirement | Stretch | Measured by |
|---|---|---|---|---|
| K1 MTF path throughput | symbols/cycle | **1** sustained for any rank 1..255 (latency free; lookup/shift may be pipelined) | — | directed run-free stream of 4,096 symbols with `tready` = 1: CYCLES = INIT_CYCLES + 4,096 + pipeline latency (≤ 8) |
| K2 expander output | bytes/cycle | **W** (parameter, default 8) sustained during a run; output byte-packed, TKEEP partial only on the block's last beat | W = 16 design point | testbench beat counter over the 8,157-byte run: 1,020 full beats in 1,020 consecutive cycles at W = 8 (`tready` = 1) |
| K3 block cycles, accepted doorbell → DONE (last beat handshaken), benchmark block, W = 8, `m_l.tready` = 1 and `s_sym.tvalid` = 1 throughout | cycles/input symbol | **≤ 1.10** (block ≤ 163,098 cycles). Cycle model (`golden/list_model.cycles`, assumptions in F7): symbol side 1/cycle producing items into an item FIFO of depth D, drain side 1 cycle per MTF byte and ⌈n/W⌉ per run: D = 0 → 1.370 (fully serialised), **D = 8 → 1.063**, D = 32 → 1.046, D = 128 → 1.035; lower bound max(148,271, 144,533)/148,271 = 1.0 | 1.023 at W = 16, D = 8 | `CYCLES / SYMBOLS_IN`, `test_full_benchmark` |
| K4 clock, sky130_fd_sc_hd tt_025C_1v80 | MHz | **≥ 50** | 100 | `make ppa` STA |
| K5 block time and speed-up | ms / × | 157,560 cycles (D = 8) @ 50 MHz = **3.15 ms** vs the stock MTF alone: 80.4 ms measured on this trace (FINDINGS §1e micro-benchmark) / 110 ms `move_to_front` tottime under cProfile (§3) ⇒ **≈ 25×** on the stage; end-to-end with `huffman_engine`: huffman PRD K4b (4.3× stock / 1.4× T3, local numbers) | — | `docs/integration.md` (integration stage, `test_driver` cycle model) |
| K6 area (no macros), W sweep 4/8/16 | mm² | soft ceiling 1.0 (flagged, not gating); trade-off table area vs K3 for W ∈ {4, 8, 16} (K3 model: 1.175 / 1.063 / 1.023 at D = 8) | — | `make area PARAMS=W=…`, OpenLane (PPA stage row in §7) |
| K7 power | mW | report only | — | OpenLane |
| K8 formal | — | SymbiYosys proof of the MTF-list invariants (F5) passes: unbounded induction on a 16-entry parametrisation, bounded depth ≥ 20 on 256 | — | `make formal` |

## 3. Functional requirements

| Id | Statement | Measurable KPI (unit) | Acceptance test | Source |
|---|---|---|---|---|
| PRD-F1 | One invocation processes one bzip2 block: symbols arrive on `s_sym` (the `huffman_engine.m_sym` beat format; TLAST on EOB); the module emits the L-vector on `m_l` byte-packed (F6) and asserts TLAST on the last beat; DONE the cycle after that beat has been handshaken. EOB is the symbol *value* N_USED + 1 (software must program `huffman_engine` ALPHABET = popcount(used) + 2); a type-bit EOB with another value, or a value EOB without the type bit, is ERR_RANK. Ordering is semantic (F2/F3 bit-exactness); MTF lookup, shift and expansion may be pipelined. | L-vector == golden (0 mismatching bytes, exact length 336,184 on the benchmark block) | `test_full_benchmark` | `t0_stock.py:411-429` |
| PRD-F2 | MTF semantics: symbol s ≥ 2 selects rank r = s − 1; the byte at rank r is emitted and moved to rank 0, ranks 0..r−1 shift down by one. Bit-exact to `golden/list_model.py` per symbol. | per-symbol byte == emulation model (0 mismatches) | `test_smoke`, `test_random` | ADR-0004 |
| PRD-F3 | Run semantics: consecutive RUNA (0) / RUNB (1) symbols accumulate n = Σ (1 + s_k) · 2^k (k = 0.. per group); at the first non-run symbol (MTF symbol or EOB) the module emits n copies of the rank-0 byte *before* that symbol's own output. n ≤ 2^20 (bzip2 blocks are ≤ 900 kB): at most 20 run symbols per group; the run symbol whose addition would make n > 2^20 is the offending symbol (ERR_RUN, F10). | run bytes == emulation model; n = 2^20 accepted, 2^20 + 1 rejected | `test_random`, `test_corner` | `t0_stock.py:412-424` |
| PRD-F4 | List initialisation: software writes the 256-bit used map (8 AXI-Lite words); at the accepted doorbell the module builds the list as the ascending sequence of used byte values in ≤ 256 cycles (INIT_CYCLES counter); N_USED = popcount(used), 1..N_LIST. `s_sym.tready` = 0 while idle, during init, and after an error or abort; software doorbells `mtf_cam` before `huffman_engine`. | list after init == sorted used bytes (debug read-back); INIT_CYCLES ≤ 256 | `test_driver`, `test_random` | Q3; `t0_stock.py:395` |
| PRD-F5 | List invariants (formal, K8): (i) the list is always a permutation of the initial N_USED bytes (no loss, no duplicate); (ii) a lookup at rank r returns the byte that was at rank r before the shift; (iii) afterwards that byte is at rank 0 and the previous ranks 0..r−1 are at 1..r; ranks ≥ r+1 unchanged. | `sby` PASS (induction on 16 entries; bounded on 256) | `make formal` | Q6 |
| PRD-F6 | Output stream `m_l`: W bytes per beat (parameter W ∈ {4, 8, 16}, default 8), **byte-packed**: every beat except the block's last carries W valid bytes (TKEEP all ones), the last beat carries the remainder (TKEEP partial); TLAST on the last beat; bytes in L-vector order, byte 0 = lowest lane. Benchmark block = 42,023 beats at W = 8. Back-pressure (`tready` low) stalls without loss or duplication; `tvalid` never depends combinationally on `tready`. | 0 mismatches under random `tready` (0–90 % duty); protocol assertions 0 | `test_random` (stall mode) | Q5, Q9 |
| PRD-F7 | Input stream `s_sym`: symbols are accepted one per cycle into an item FIFO of depth D ≥ 8 (parameter, set at uArch) that decouples the symbol side (list update, run accumulate) from the drain side (1 cycle per MTF byte, ⌈n/W⌉ per run group); `tready` drops when the FIFO is full (and in the idle/init/error/abort states of F4); no symbol is lost or duplicated; at W = 8 the benchmark block completes in K3. | 0 mismatches under random `tvalid`; K3 (model 1.063 at D = 8) | `test_random`, `test_full_benchmark` | Q2 |
| PRD-F8 | Parameters (defaults verified): W = 8 (4 and 16 built and smoke-tested for PPA), N_LIST = 256 (16 for the formal proof), D ≥ 8 (uArch), run accumulator 21 bits (holds 2^20), SYMBOL_LIMIT and BYTES_LIMIT 32-bit registers (1..2^27 / 1..2^30, defaults 2^20 / 2^20). | W = 8 full suite; W = 4/16 `test_smoke` + `test_full_benchmark` | all | Q9 |
| PRD-F9 | Doorbell-time rejection (sticky flag, no BUSY/DONE/IRQ, counters hold): ERR_PARAM — used map all zero (N_USED = 0), SYMBOL_LIMIT = 0 or > 2^27, BYTES_LIMIT = 0 or > 2^30. | flag set, 0 output beats | `test_corner` | Q7 |
| PRD-F10 | Run-time errors stop the module at the offending symbol: ERR_RANK (symbol value > N_USED + 1, i.e. ≥ ALPHABET; or an EOB type/value mismatch, F1), ERR_RUN (the run symbol whose addition makes n > 2^20), ERR_LIMIT (SYMBOL_LIMIT symbols without EOB, or BYTES_OUT would exceed BYTES_LIMIT), ERR_UNDERRUN (`s_sym` TLAST on a non-EOB symbol). Post-error: bytes already handshaken stay; a run group pending at the offending symbol is **discarded**; the packer's partial beat is flushed with TKEEP and no TLAST; BUSY = 0, DONE = 0, flag + IRQ; counters frozen (BYTES_OUT = bytes handshaken). | flag set; ≤ 1 beat after the error (the partial flush: TKEEP partial, no TLAST); BYTES_OUT == bytes handshaken incl. the flush; IRQ within 2 cycles | `test_corner` | Q7 |
| PRD-F11 | Control semantics (own statement, mirrors the other modules): DOORBELL accepted only when idle; DOORBELL or a write to the used map / SYMBOL_LIMIT / BYTES_LIMIT while BUSY is ignored with ERR_BUSY; configuration reads while BUSY return the latched values, STATUS and counters are live. ABORT takes effect within 8 cycles in any state (init, decoding, draining a run — the partial beat is flushed with TKEEP, no TLAST; BYTES_OUT counts it — or stalled by `tready`), ABORTED + IRQ; ABORT while idle is a no-op; DOORBELL + ABORT in one write → ABORT wins; ABORT during the post-EOB drain is honoured (ABORTED, not DONE); ABORT after the last beat is handshaken → DONE only. DONE/ABORTED/ERR_* and the IRQ are W1C; an accepted doorbell clears none. Reset (synchronous, active-low) at any time → idle, every register zero. | one directed check per rule, latencies in cycles | `test_driver` | grape/huffman PRDs |
| PRD-F12 | Counters, read-only: CYCLES (64-bit, accepted doorbell → DONE = last beat handshaken / ABORTED / ERR inclusive), SYMBOLS_IN (32-bit), BYTES_OUT (32-bit, bytes handshaken), INIT_CYCLES (9-bit), MAX_RUN (21-bit, longest run of the block). No overflow by construction: SYMBOLS_IN ≤ SYMBOL_LIMIT ≤ 2^27, BYTES_OUT ≤ BYTES_LIMIT ≤ 2^30 (ERR_LIMIT otherwise, F10), CYCLES ≤ 2^27 + 2^30/W ≪ 2^64. | == testbench counts (exact) | `test_driver`, `test_full_benchmark` | Q7 |
| PRD-F13 | Empty block: EOB as the first symbol → 0 bytes, one `m_l` beat with TKEEP = 0 and TLAST (or no beat — MAS decides, testbench accepts the MAS choice), DONE. | DONE, BYTES_OUT = 0 | `test_corner` | Q7 |
| PRD-F14 | Bus verification: AXI-Lite and both AXI-Stream ports checked by independent protocol agents (`cocotbext-axi`), never only by datapath results. | 0 protocol violations across all tests | all tests | Q7 (huffman F14) |
| PRD-F15 | Reference models: golden = `golden/mtf_ref.py` (instrumented stock pyflate via the huffman_engine wrapper, == libbzip2), capturing the used map, the symbol stream, per-symbol MTF bytes and the L-vector; predictor = `golden/list_model.py` (functional model `expand`, cycle model `cycles`). Scoreboard: DUT vs predictor per beat, predictor vs golden per block; the cycle model is validated only against the DUT in `test_full_benchmark` (K3). | `calibrate.py`: L-vector and per-symbol bytes == golden (336,184 B / 89,837 lookups) | `golden/calibrate.py`, `test_full_benchmark` | Q8 |
| PRD-F16 | Single clock, synchronous active-low reset; one level IRQ. | — | `test_driver` | ADR-0001 |

## 4. HW/SW split

| Function (pyflate bzip2 path) | HW / SW | Data crossing per block |
|---|---|---|
| `used` map parse (`compute_used`) | SW → 8 AXI-Lite words | 32 B |
| initial list (`favourites` = sorted used bytes) | **HW** (F4) | — |
| Huffman decode → symbol stream | `huffman_engine` → `s_sym` on chip | 148,271 beats (no memory traffic) |
| MTF lookup + move-to-front (`move_to_front`) | **HW** | — |
| RUNA/RUNB accumulate + expand (`repeat`, `favourites[0] * repeat`) | **HW** | — |
| L-vector to memory | `m_l` → platform DMA | 336,184 B (42,023 × 8-byte beats at W = 8) |
| inverse BWT (`bwt_reverse`), RLE4, MD5 | SW (non-target, ADR-0003) | — |

Per block ≈ 12 AXI-Lite words (≈ 48 bus cycles, 0.03 % of the 157,560-cycle model); the two
streams are on-chip (input) and platform DMA (output), testbench-modelled as before.

## 5. Interfaces (PRD level; detail in MAS)

- 32-bit AXI4-Lite slave: control/status/counters, `used` map (8 words) (ADR-0001).
- AXI4-Stream slave `s_sym` — `huffman_engine.m_sym` beat format (≥ 9-bit symbol + type bits,
  encoding fixed jointly at MAS; TLAST on EOB).
- AXI4-Stream master `m_l` — W × 8 bit data, TKEEP, TLAST at end of block.
- One clock, `rst_n`; one level IRQ.
- Data volume per benchmark block: 148,271 beats in, 336,184 B out, 32 B config.

## 6. Non-goals

- Inverse BWT, RLE4, CRC/MD5 (ADR-0003).
- Selector inverse-MTF (2–6 entries; software, huffman PRD §4) — not this list.
- DEFLATE symbols (never routed here; `huffman_engine` sends DEFLATE events to DMA).
- Multi-symbol-per-cycle MTF; RAM-based MTF (PPA comparison only if time allows).
- bzip2 `randomised` blocks.

## 7. Acceptance tests (names reused by `hw-dv-testplan`)

| Test | Checks | Requirements |
|---|---|---|
| `test_smoke` | 4 used bytes, 10 symbols incl. one run group; == emulation model, no stalls | F1–F4 |
| `test_random` | random used maps (N_USED 1..256), random symbol streams (ranks 1..N_USED−1, run groups of ≤ 20 symbols with n ≤ 2^20), random stalls on both ports, W = 8; == emulation model per beat | F2–F8 |
| `test_full_benchmark` | the shipped block's symbol trace (from the huffman golden) → L-vector == golden (336,184 B); K3 from CYCLES/SYMBOLS_IN; W = 4/8/16 | F1, F7, F8, F12, K3 |
| `test_driver` | register round-trip, doorbell/BUSY/ABORT (idle, init, during a long run, stalled)/IRQ/reset, `tready` = 0 when idle/init/error, INIT_CYCLES, counters, K1 directed stream, protocol agents on all three ports | F4, F11, F12, F14, F16, K1 |
| `test_corner` | every ERR_* of F9/F10 (incl. EOB type/value mismatch, run pending at ERR_RANK → discarded, BYTES_LIMIT); N_USED = 1 and 256; rank N_USED−1; run n = 2^20 and 2^20 + 1; EOB first; TLAST early; 8,157-byte run with `tready` stalls; ABORT during the post-EOB drain | F1, F3, F9, F10, F11, F13 |
| `make formal` | F5 invariants with SymbiYosys (N_LIST = 16 induction, 256 bounded) | F5, K8 |
| `make ppa PARAMS=W=4/8/16` | K4 Fmax, K6 area, K7 power for the three widths; trade-off table in `docs/ppa.md` | K4, K6, K7 |
| integration (`docs/integration.md`) | K5 from the `test_driver` cycle model and the `huffman_engine` numbers | K5 |

## 8. Open questions (carried to MAS / uArch)

1. `s_sym` beat encoding (shared with `huffman_engine.m_sym`) — MAS, joint.
2. Empty-block output: zero-length beat vs no beat — MAS (DMA convention).
3. Item-FIFO depth D (8 → 1.063, 32 → 1.046, 128 → 1.035 cycles/symbol) and the CAM/packer pipeline — uArch.
4. CAM implementation: 256 × 8-bit shift register (baseline) vs rank counters — uArch, with the W sweep at PPA.

## 9. Review findings

See `docs/review_prd.md`.
