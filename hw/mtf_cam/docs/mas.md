# mtf_cam — MAS (Architecture Spec)

Status: **approved** 2026-09-04 (MAS checkpoint). Stage 2 of `hw/FLOW.md`.
Inputs: `docs/prd.md` (approved 2026-08-30), ADR-0001, ADR-0004 (chained module, W parameter),
ADR-0005 (register conventions), ADR-0006 (symbol beat). Block diagram:
`docs/block_diagram.{json,mmd,svg}`. Interview: `prompt.txt` 2026-08-30 (Q1–Q6).

## 1. Context

Second pyflate accelerator: one 4 KB AXI4-Lite window, one AXI4-Stream slave `s_sym` (symbol beats,
ADR-0006 — from `huffman_engine.m_sym` on chip in the `pyflate_accel` wrapper, window at +0x1000,
or from a DMA replay of the golden symbol trace when verified standalone), one AXI4-Stream master
`m_l` (L-vector bytes, W lanes) to platform DMA. Software writes the used map, doorbells
`mtf_cam` first and `huffman_engine` second, waits for DONE, reads BYTES_OUT. The DMA life-cycle
rule of the huffman MAS §5 applies to `m_l` (stopped/flushed before every doorbell).

## 2. I/O table

| Signal | Dir | Width | Clock | Reset value | Description |
|---|---|---|---|---|---|
| `clk` | in | 1 | — | — | single clock, K4 ≥ 50 MHz |
| `rst_n` | in | 1 | `clk` | — | synchronous active-low; every RW/W1C register and counter → 0 (PRD-F11) |
| `s_axi_*` | in/out | AXI4-Lite, 12-bit address, 32-bit data | `clk` | outputs 0 | as grape MAS §2 |
| `s_axis_sym_tdata` | in | 32 | `clk` | — | symbol beat (ADR-0006): TYPE 0 → value 0/1 = RUNA/RUNB, 2..N_USED = MTF symbol (rank = value − 1), ≥ N_USED + 1 → ERR_RANK; TYPE 3 → EOB, value must equal N_USED + 1 (else ERR_RANK); TYPE 1/2 → ERR_RANK; [27:12] and [31:28] ignored |
| `s_axis_sym_tlast` | in | 1 | `clk` | — | expected with the EOB beat (huffman always sets it); ignored on a TYPE 3 beat; TLAST on any other beat → ERR_UNDERRUN |
| `s_axis_sym_tvalid` / `tready` | in / out | 1 / 1 | `clk` | — / 0 | handshake; `tready` = 0 when idle, during init, after error/abort, and when the item FIFO is full (PRD-F4/F7) |
| `m_axis_l_tdata` | out | 8·W | `clk` | 0 | L-vector bytes, byte 0 in [7:0] (lowest lane first), W ∈ {4, 8, 16}, default 8 |
| `m_axis_l_tkeep` | out | W | `clk` | 0 | all ones except the last beat of the block (contiguous from lane 0); lanes with TKEEP = 0 carry 0 |
| `m_axis_l_tlast` | out | 1 | `clk` | 0 | last beat of the block; no beat at all for an empty block (Q1) |
| `m_axis_l_tvalid` / `tready` | out / in | 1 / 1 | `clk` | 0 / — | handshake; `tvalid` never depends combinationally on `tready` (PRD-F6) |
| `irq` | out | 1 | `clk` | 0 | registered \|(STATUS & IRQ_EN) |

Parameters: `W = 8` (4, 16 for PPA), `N_LIST = 256` (16 for formal), `D ≥ 8` item-FIFO depth (uArch),
`RUN_W = 21` (run accumulator, holds 2^20) — readable through CAPS.

## 3. Clock and reset

One clock domain, `rst_n` synchronous ≥ 1 cycle, no CDC. Reset drops in-flight AXI-Lite
transactions and stream beats (bus master and DMA reset with the module); after release the module
is idle within 1 cycle, `tready`/`tvalid` = 0, `irq` = 0, the list contents undefined until the next
init (not readable: DBG_DATA reads 0 before the first init).

## 4. Register map

ADR-0005 conventions (reserved RAZ/WI OKAY, unmapped in-window → SLVERR). **Writable while BUSY:
STATUS (W1C), IRQ_EN, CTRL, DBG_SEL**; writes to USED[w], SYMBOL_LIMIT, BYTES_LIMIT while BUSY are
ignored with ERR_BUSY (OKAY). Configuration registers hold pending values while idle, are latched at
the accepted doorbell, read the latched values while BUSY; STATUS, counters and DBG_DATA are live.
A single stored copy of the used map satisfies the latching rule (BUSY writes are ignored).

| Offset | Name | Bits | Access | Reset | Description |
|---|---|---|---|---|---|
| 0x000 | ID | 31:0 | RO | 0x4D544631 | ASCII `MTF1` |
| 0x004 | VERSION | 31:0 | RO | 0 | git short SHA (synthesis parameter) |
| 0x008 | CTRL | 0 | WP | 0 | DOORBELL (PRD-F1); ignored + ERR_BUSY while BUSY; rejected with ERR_PARAM (F9) |
| | | 1 | WP | 0 | ABORT (F11): within 8 cycles in any state; wins over bit 0 |
| 0x00C | STATUS | 0 | RO | 0 | BUSY |
| | | 1 | W1C | 0 | DONE (the cycle after the last `m_l` beat is handshaken; empty block: the cycle after the EOB handshake) |
| | | 2 | W1C | 0 | ABORTED |
| | | 8 | W1C | 0 | ERR_BUSY |
| | | 9 | W1C | 0 | ERR_PARAM (F9: N_USED = 0 or > N_LIST, SYMBOL_LIMIT 0 or > 2^27, BYTES_LIMIT 0 or > 2^30) — doorbell-time, BRESP held ≤ 8 cycles |
| | | 10 | W1C | 0 | ERR_RANK (F10: value > N_USED + 1, TYPE 1/2, EOB type/value mismatch) — per symbol |
| | | 11 | W1C | 0 | ERR_RUN (F10: run would exceed 2^20) — per symbol |
| | | 12 | W1C | 0 | ERR_LIMIT (F10): beat number SYMBOL_LIMIT is not EOB (EOB as that beat → DONE); or, checked at item production on the symbol side, BYTES_OUT + bytes accepted but not yet handshaken (item FIFO, expander, packer) + this item's bytes > BYTES_LIMIT (item not enqueued; hence BYTES_OUT ≤ BYTES_LIMIT always, flush included) — per symbol |
| | | 13 | W1C | 0 | ERR_UNDERRUN (F10: TLAST on a non-EOB beat) — per symbol |

Error timing: a per-symbol flag is set ≤ 4 cycles after the offending `s_sym` handshake, `irq` one cycle later (PRD-F10 ≤ 2 cycles after the flag).
| 0x010 | IRQ_EN | 13:8, 2:1 | RW | 0 | mask over the sticky bits (bits 7:3 reserved RAZ/WI); writable while BUSY; all flags assert `irq` iff enabled |
| 0x014 | IRQ_STATUS | 13:8, 2:1 | RO | 0 | STATUS & IRQ_EN |
| 0x018–0x03C | — | — | reserved | 0 | RAZ/WI, OKAY |
| 0x040 | CYCLES_LO | 31:0 | RO | 0 | accepted doorbell → DONE/ABORTED/ERR inclusive (F12); live non-atomic while BUSY, stable when idle (read LO then HI) |
| 0x044 | CYCLES_HI | 31:0 | RO | 0 | high word |
| 0x048 | SYMBOLS_IN | 31:0 | RO | 0 | `s_sym` beats accepted incl. the EOB beat (live); frozen at the offending beat on error |
| 0x04C | BYTES_OUT | 31:0 | RO | 0 | L-vector bytes handshaken on `m_l` incl. a flushed partial beat (live) |
| 0x050 | INIT_CYCLES | 8:0 | RO | 0 | fill cycles of the last list init = cycles from the accepted doorbell to `s_sym.tready` rising, ≤ 256 (F4: one used byte per cycle, overhead ≤ 256 − N_USED absorbed); the K3 cycle model uses the measured value |
| 0x054 | MAX_RUN | 20:0 | RO | 0 | largest run item n (bytes) enqueued in the invocation; a run discarded at an error does not count |
| 0x058–0x0FC | — | — | reserved | 0 | RAZ/WI, OKAY |
| 0x100 | SYMBOL_LIMIT | 31:0 | RW | 0 | 1..2^27 (reset 0 rejected; driver default 2^20) |
| 0x104 | BYTES_LIMIT | 31:0 | RW | 0 | 1..2^30 (reset 0 rejected; driver default 2^20) |
| 0x108 | CAPS | 7:0 W, 15:8 D, 24:16 N_LIST, 31:25 reserved 0 | RO | build parameters | e.g. W = 8, D = 8, N_LIST = 256 (0x0100_0808) |
| 0x10C | DBG_SEL | 7:0 rank | RW | 0 | rank whose current list byte DBG_DATA returns; writable while BUSY |
| 0x110 | DBG_DATA | 7:0 | RO | 0 | list byte at rank DBG_SEL (live, partial during init; 0 for rank ≥ N_USED or before the first init) |
| 0x114–0x1FC | — | — | reserved | 0 | RAZ/WI, OKAY |
| 0x200 + 4·w | USED[w] | 31:0 | RW | 0 | used map: bit b of word w = byte value 32·w + b is present (w = 0..7); N_USED = popcount |
| 0x220–0xFFC | — | — | — | — | not mapped → SLVERR |

## 5. Data path protocol (ADR-0001, ADR-0004, ADR-0006)

- **`s_sym`**: one ADR-0006 beat per symbol from `huffman_engine` (or the replay DMA). `tready`
  rises after the list init completes (INIT_CYCLES ≤ 256 after the accepted doorbell), drops while
  the item FIFO is full (PRD-F7), and stays 0 from DONE/ERR/ABORT until the next accepted doorbell.
  A TYPE 3 beat ends the block; the module does not read further beats. `huffman_engine`
  emits nothing after EOB and, on its own ERR/ABORT, deasserts `m_sym.tvalid` within its bound and
  emits nothing until its next accepted doorbell (huffman MAS amendment 2026-08-30, ADR-0006), so
  every `mtf_cam` invocation starts with an empty `s_sym`.
- **`m_l`**: byte-packed W-byte beats (PRD-F6): every beat except the last carries W bytes
  (TKEEP all ones); the last beat carries the remainder with TKEEP contiguous from lane 0 and
  TLAST = 1; an empty block emits **no beat** (Q1) — software reads BYTES_OUT = 0 and the DMA is
  stopped by the flush rule. On ERR/ABORT: the flag and BUSY = 0 are set within the stated bound regardless of `tready`;
  the item FIFO, the expander state and the pending run are discarded; the packer's partial beat
  (if any) stays presented (`tvalid` held) until handshaken — no TLAST — and BYTES_OUT
  increments only on that handshake (PRD-F10/F11); CYCLES stops at the flag. **An accepted
  doorbell or a reset withdraws a still-pending beat** (`tvalid` → 0, bytes not counted), so
  every block starts with an empty `m_l`. Back-pressure
  stalls the expander without loss.
- **Doorbell response**: BRESP after the doorbell-time checks (ERR_PARAM) are visible in STATUS
  (≤ 8 cycles; ADR-0005).
- **DMA / chaining rules**: `m_l` sink stopped and flushed before every doorbell; in the chained
  wrapper the producer is `huffman_engine`, doorbelled after `mtf_cam` (doorbelling it first is
  tolerated — its beats wait on `tready` = 0 — but its CYCLES then includes the wait). If either
  module ends in ERR/ABORT or the driver's timeout expires, the chained driver **aborts the other
  module** (huffman stalls forever on `tready` = 0; mtf_cam waits forever for EOB), then applies
  the flush rule before the next block. Bus traffic per block: 8 used-map
  words + ~6 control words ≈ 14 transactions ≈ 56 cycles (0.04 % of the 157,560-cycle model;
  estimate, measured in `test_driver`; supersedes the PRD §4 figure of 12 words).

Invocation sequence (software): write USED[0..7], SYMBOL_LIMIT, BYTES_LIMIT → start the `m_l`
sink DMA → CTRL.DOORBELL → STATUS BUSY (or ERR_PARAM) → doorbell `huffman_engine` → wait DONE/irq
→ read BYTES_OUT, counters → W1C.

## 6. Driver API (Python, `hw/mtf_cam/driver/`, reused by `hw-integrate`)

```python
class MtfDriver(AccelDriver):                      # base: hw/common/driver/accel.py (wait_done returns when BUSY = 0)
    def configure(self, used_map, symbol_limit=1 << 20, bytes_limit=1 << 20) -> None
                     # used_map: 256 bools or a 32-byte bitmap; validates N_USED >= 1
    def caps(self) -> dict                         # {"W": .., "D": .., "N_LIST": ..} from CAPS
    def read_list(self) -> list[int]               # DBG_SEL/DBG_DATA sweep over ranks 0..N_USED-1 (debug)
    def expand_block(self, symbols: list[int]) -> bytes
                     # standalone: symbols are raw values (0/1 runs, 2..N_USED MTF, N_USED+1 EOB); the replay
                     # source makes ADR-0006 beats (TYPE 0, and TYPE 3 + TLAST for the EOB value); the chained
                     # path feeds huffman's 32-bit beats unchanged (HuffmanDriver.decode_block returns them).
                     # configure, program source + m_l sink, start, wait_done (returns when BUSY = 0), then
                     # drain the sink until m_l.tvalid = 0 before reading BYTES_OUT; return the sink bytes
                     # (== BYTES_OUT). Raises on ERR_PARAM/ERR_BUSY/ERR_RANK/ERR_RUN/ERR_LIMIT/
                     # ERR_UNDERRUN; ABORTED returns normally
```

The chained driver (`pyflate_accel`: `decode_bzip2_block(data, start_bit, lengths, selectors,
used) -> bytes`) is written by `hw-integrate`; it doorbells `MtfDriver` then `HuffmanDriver`.

## 7. Block diagram

`docs/block_diagram.svg`: Host/DMA (CPU + driver, AXI-Lite handshake cell, DMA / huffman_engine)
→ Control (register file incl. used map, block FSM doorbell → init → run → EOB/error, counters) →
List (init from the used map, N_LIST-entry shift-register CAM, rank select + move-to-front) →
Run accumulator (RUNA/RUNB) → Item FIFO (depth D) → Expander + beat packer → `m_l`. CAM organisation,
D and the packer pipeline are uArch decisions.

## 8. Error and status behaviour

| Event | STATUS | BUSY | irq (if enabled) | Streams | Counters |
|---|---|---|---|---|---|
| doorbell accepted | BUSY | 1 | — | init runs; `s_sym` tready 0 until done | CYCLES restarts, others 0 |
| init done | — | 1 | — | `s_sym` tready 1 | INIT_CYCLES |
| EOB (TYPE 3, value N_USED + 1, TLAST) | DONE the cycle after the last `m_l` beat handshake (empty block: no beat) | 0 | DONE | tready 0 | CYCLES stops |
| ABORT while BUSY | ABORTED within 8 cycles of the write in any state, regardless of `m_l.tready`; DONE instead if the last beat was already handshaken | 0 | ABORTED / DONE | FIFO/expander/pending run discarded; partial beat held valid until handshaken (no TLAST); tready 0 | CYCLES stops at the flag; BYTES_OUT counts the flush when handshaken |
| ABORT idle / DOORBELL+ABORT | as grape MAS §8 | | | | |
| doorbell rejected (F9) | ERR_PARAM | 0 | flag | none | hold |
| run-time error (F10) | ERR_RANK / ERR_RUN / ERR_LIMIT / ERR_UNDERRUN, ≤ 4 cycles after the offending handshake | 0 | flag | FIFO/expander/pending run discarded; partial beat held valid (no TLAST); tready 0 | SYMBOLS_IN frozen at the offending beat; BYTES_OUT counts the flush when handshaken |
| config write while BUSY | ERR_BUSY | 1 | ERR_BUSY | — | — |
| reset | 0 | 0 | 0 | tready/tvalid 0 | 0 |

`irq` registered (1 cycle); sticky bits W1C only; doorbell clears none.

## 9. Traceability

| PRD | MAS element |
|---|---|
| F1 | `s_sym` TYPE/EOB rules (§2, §5), DONE definition (§4/§8) |
| F2, F3 | §7 List / Run blocks; behaviour per `golden/list_model.py` (uArch) |
| F4 | USED[w], INIT_CYCLES, `s_sym` tready during init, doorbell order (§5) |
| F5 | K8 formal on the List block (`make formal`, N_LIST = 16) |
| F6 | `m_l` packing/TKEEP/TLAST, empty block (§2, §5) |
| F7 | item FIFO D (CAPS), tready rule |
| F8 | parameters + CAPS |
| F9, F10 | STATUS bits 9–13, §4 error-timing note, §8 rows |
| F11 | CTRL.ABORT semantics, writable-while-BUSY set, latching |
| F12 | counters 0x040–0x054 |
| F13 | empty block: no beat (Q1) |
| F14 | `cocotbext-axi` agents on all three ports |
| F15 | replay source from the golden symbol trace; predictor `golden/list_model.py` |
| F16 | §3 |

## 10. Review findings

See `docs/review_mas.md` (written by `hw-review`).
