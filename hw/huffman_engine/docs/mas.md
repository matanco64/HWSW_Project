# huffman_engine — MAS (Architecture Spec)

Status: **review** (checkpoint — awaiting human approval). Stage 2 of `hw/FLOW.md`.
Inputs: `docs/prd.md` (approved 2026-08-28), ADR-0001 (AXI-Lite 32-bit + AXI-Stream bulk),
ADR-0003 (architecture + HW/SW boundary), ADR-0005 (register conventions), ADR-0006 (symbol-beat
encoding). Block diagram: `docs/block_diagram.{json,mmd,svg}`. Interview: `prompt.txt` 2026-08-30 (Q1–Q8).

## 1. Context

A memory-mapped, stream-attached peripheral on the SoC bus: one 4 KB AXI4-Lite window (control,
counters, length window), two AXI4-Stream slaves fed by platform DMA (`s_bits` compressed bytes,
`s_sel` selectors), one AXI4-Stream master `m_sym` (symbol beats, ADR-0006) consumed either by
`mtf_cam` on chip (the `pyflate_accel` wrapper of the integration stage: both modules, `m_sym →
s_sym` wired, mtf_cam's window at +0x1000) or by DMA when verified standalone / in DEFLATE mode.
Software parses headers, delta-coded lengths and selectors (ADR-0003) and calls
`HuffmanDriver.decode_block()` once per block.

## 2. I/O table

| Signal | Dir | Width | Clock | Reset value | Description |
|---|---|---|---|---|---|
| `clk` | in | 1 | — | — | single clock, K3 ≥ 50 MHz |
| `rst_n` | in | 1 | `clk` | — | synchronous active-low; every RW/W1C register and counter → 0 (PRD-F11) |
| `s_axi_*` | in/out | AXI4-Lite, 12-bit address, 32-bit data | `clk` | outputs 0 | as grape MAS §2 (awaddr/awprot/awvalid/awready, wdata/wstrb/wvalid/wready, bresp/bvalid/bready, araddr/arprot/arvalid/arready, rdata/rresp/rvalid/rready) |
| `s_axis_bits_tdata` | in | 32 | `clk` | — | compressed bytes, byte 0 of the stream in [7:0] (little-endian lanes) |
| `s_axis_bits_tkeep` | in | 4 | `clk` | — | all ones except on the TLAST beat, where it is contiguous from lane 0 (0x1/0x3/0x7/0xF); other patterns are protocol violations (caught by the agent); the engine uses the lowest contiguous run |
| `s_axis_bits_tlast` | in | 1 | `clk` | — | last word of the buffer |
| `s_axis_bits_tvalid` / `tready` | in / out | 1 / 1 | `clk` | — / 0 | handshake; `tready` = 0 when idle, after error/abort |
| `s_axis_sel_tdata` | in | 8 | `clk` | — | selector in [2:0], [7:3] ignored (bzip2 mode only; not read in DEFLATE mode); value checked when applied (F10) |
| `s_axis_sel_tlast` | in | 1 | `clk` | — | last selector |
| `s_axis_sel_tvalid` / `tready` | in / out | 1 / 1 | `clk` | — / 0 | handshake; `tready` = 0 when idle / DEFLATE / after error |
| `m_axis_sym_tdata` | out | 32 | `clk` | 0 | symbol beat (ADR-0006): [8:0] value (bzip2 0..ALPHABET−2 on TYPE 0), [11:9] TYPE, [27:12] distance (TYPE 2, else 0), [31:28] 0. EOB beat: **TYPE = 3 in both modes**, [8:0] = ALPHABET−1 (bzip2) / 256 (DEFLATE), [27:12] = 0, TLAST = 1; TYPE 0 beats never carry the EOB value |
| `m_axis_sym_tlast` | out | 1 | `clk` | 0 | on the EOB beat |
| `m_axis_sym_tvalid` / `tready` | out / in | 1 / 1 | `clk` | 0 / — | handshake; `tvalid` never depends combinationally on `tready` (PRD-F6) |
| `irq` | out | 1 | `clk` | 0 | registered \|(STATUS & IRQ_EN) |

Parameters: `ALPHABET_MAX = 288`, `MAXLEN = 20`, `N_TABLES_MAX = 6` (PRD-F8).

## 3. Clock and reset

One clock domain, `rst_n` synchronous ≥ 1 cycle, no CDC. Reset drops in-flight AXI-Lite
transactions and stream beats (the DMA and bus master are reset with the module); after release
the module is idle within 1 cycle, all stream `tready`/`tvalid` = 0, `irq` = 0.

## 4. Register map

ADR-0005 conventions: reserved bits/words RAZ/WI OKAY; unmapped in-window words → SLVERR;
**writable while BUSY: STATUS (W1C), IRQ_EN, CTRL, DBG_SEL**; writes to listed RW configuration
registers (MODE, START_BIT, ALPHABET, N_TABLES, SYMBOL_LIMIT, length window) while BUSY are ignored
with ERR_BUSY (OKAY). Configuration registers hold pending values while idle (read back what was
written), are latched at the accepted doorbell, and read the latched values while BUSY; STATUS,
counters and DBG_DATA are live.

| Offset | Name | Bits | Access | Reset | Description |
|---|---|---|---|---|---|
| 0x000 | ID | 31:0 | RO | 0x48554631 | ASCII `HUF1` |
| 0x004 | VERSION | 31:0 | RO | 0 | git short SHA (synthesis parameter) |
| 0x008 | CTRL | 0 | WP | 0 | DOORBELL (PRD-F1); ignored + ERR_BUSY while BUSY; rejected at the doorbell with ERR_PARAM (F9), or during the build with ERR_TABLE (see §8) |
| | | 1 | WP | 0 | ABORT (F11): within 8 cycles decoding/stalled, 16 during a table build; wins over bit 0 |
| 0x00C | STATUS | 0 | RO | 0 | BUSY |
| | | 1 | W1C | 0 | DONE (EOB beat handshaken, surplus `s_sel` beats drained) |
| | | 2 | W1C | 0 | ABORTED |
| | | 8 | W1C | 0 | ERR_BUSY |
| | | 9 | W1C | 0 | ERR_PARAM (F9: ALPHABET, N_TABLES, SYMBOL_LIMIT, MODE/N_TABLES/ALPHABET combination) |
| | | 10 | W1C | 0 | ERR_TABLE: length > MAXLEN of the mode (checked at the doorbell, rejection) or over-subscribed table (only knowable after the count pass: raised during the build, §8). Entries beyond N_TABLES·ALPHABET (DEFLATE: ALPHABET + 30) are ignored by both checks |
| | | 11 | W1C | 0 | ERR_NOCODE (F10) |
| | | 12 | W1C | 0 | ERR_SELECTOR (F10) |
| | | 13 | W1C | 0 | ERR_SYMBOL (F10) |
| | | 14 | W1C | 0 | ERR_LIMIT (F10) |
| | | 15 | W1C | 0 | ERR_UNDERRUN (F10) |
| 0x010 | IRQ_EN | 15:1 | RW | 0 | mask over the sticky bits; writable while BUSY |
| 0x014 | IRQ_STATUS | 15:1 | RO | 0 | STATUS & IRQ_EN |
| 0x018–0x03C | — | — | reserved | 0 | RAZ/WI, OKAY |
| 0x040 | CYCLES_LO | 31:0 | RO | 0 | accepted doorbell → DONE/ABORTED/ERR inclusive (F12); live and non-atomic while BUSY, stable when BUSY = 0 (read LO then HI) |
| 0x044 | CYCLES_HI | 31:0 | RO | 0 | high word |
| 0x048 | SYMBOLS | 31:0 | RO | 0 | `m_sym` beats handshaken (live) |
| 0x04C | BITS | 31:0 | RO | 0 | bits consumed since START_BIT (live) |
| 0x050 | BUILD_CYCLES | 15:0 | RO | 0 | longest single table build of the invocation (K2) |
| 0x054 | OVERFETCH | 7:0 | RO | 0 | `s_bits` beats accepted beyond the last consumed bit (≤ 4, F4) |
| 0x058–0x0FC | — | — | reserved | 0 | RAZ/WI, OKAY |
| 0x100 | MODE | 0 | RW | 0 | 0 = bzip2, 1 = DEFLATE (F7) |
| 0x104 | START_BIT | 31:0 | RW | 0 | first code bit within the `s_bits` buffer (F4; bit 0 = byte 0 MSB in bzip2, LSB in DEFLATE) |
| 0x108 | ALPHABET | 8:0 | RW | 0 | bzip2: symbols per table (3..288, EOB = ALPHABET − 1); DEFLATE: literal/length alphabet (257..288) |
| 0x10C | N_TABLES | 2:0 | RW | 0 | bzip2 1..6; DEFLATE must be 2 (else ERR_PARAM) |
| 0x110 | SYMBOL_LIMIT | 31:0 | RW | 0 | 1..2^27, else ERR_PARAM (reset 0 is rejected; the PRD default 2^20 is the driver default). ERR_LIMIT fires when SYMBOL_LIMIT beats have been emitted and none was EOB (EOB as beat number SYMBOL_LIMIT → DONE); the emulation model gets the same check at `hw-dv-testplan` |
| 0x114 | DBG_SEL | 2:0 table, 5:4 kind (0 count, 1 first_code, 2 base, 3 symtab), 16:8 index | RW | 0 | selects the word DBG_DATA returns; writable while BUSY |
| 0x118 | DBG_DATA | 31:0 | RO | 0 | selected built-table entry: kinds 0–2 by length index 1..MAXLEN, kind 3 by symbol slot 0..ALPHABET−1. Reads 0 for table ≥ N_TABLES, index out of range, or before the first build of the invocation; live (possibly partial) during a build, stable after it (F3) |
| 0x11C–0x3FC | — | — | reserved | 0 | RAZ/WI, OKAY |
| 0x400 + 4·w | LEN[w] | 6 × 5 bit: [4:0] length 6w, [9:5] 6w+1, … [29:25] 6w+5; 31:30 reserved | RW | 0 | length window, w = 0..287: packed continuously, table-major — length of symbol s in table t is entry e = t·ALPHABET + s at word ⌊e/6⌋, field e mod 6 (F7). DEFLATE: same formula with t = 1 — table 0 = indices 0..ALPHABET−1 (lit/len), table 1 = indices ALPHABET..ALPHABET+29 (30 distance lengths; software drops HDIST entries 30/31, which must be 0); entries ≥ ALPHABET + 30 ignored. A single stored copy satisfies the latching rule (writes while BUSY are ignored) — uArch choice |
| 0x880–0xFFC | — | — | — | — | not mapped → SLVERR |

## 5. Data path protocol (ADR-0001, ADR-0006)

Streams are AXI4-Stream, single clock, no sideband beyond TKEEP/TLAST as listed.

- **`s_bits`**: the DMA presents the compressed buffer from its first byte; the engine consumes
  words into a 64-bit window, decodes from START_BIT, pads with zeros after TLAST (F4), and accepts
  at most 4 beats beyond the last consumed bit (OVERFETCH). `tready` may rise from the accepted doorbell (prefetch during the build is allowed, bounded
  by the window) and drops when the window is full or the module is not BUSY. Over-fetched beats are dropped at DONE (a new invocation restarts
  the DMA from its own buffer start, F13: the next block's START_BIT = previous START_BIT + BITS +
  header bits parsed by software — software re-presents the *same* buffer or a sub-buffer, its
  choice; the engine only needs START_BIT to be within the presented buffer).
- **`s_sel`**: one 8-bit beat per selector, [2:0] used, TLAST on the last; `tready` stays 0 until
  the last table build completes; the engine then reads one beat before symbol 0 and one every 50 symbols; after EOB it drains and ignores remaining beats
  up to TLAST before DONE (F7); ERR_SELECTOR if TLAST was already consumed when a selector is
  needed, or the value ≥ N_TABLES. Not read in DEFLATE mode (`tready` = 0; the DMA must not be
  started or must tolerate stall — driver rule).
- **`m_sym`**: one ADR-0006 beat per decoded symbol/event; TLAST on EOB; back-pressure stalls the
  decoder without loss (F6).
- **Doorbell response**: BRESP is held only for the doorbell-time checks (ERR_PARAM, lengths > MAXLEN; ≤ 8 cycles) and returns once BUSY or the rejection flag is visible in STATUS (ADR-0005). Over-subscription is detected in the build (§8).
- **DMA rules (software/driver)**: before every doorbell the three DMA channels are stopped and flushed (the previous invocation may have left ≤ 4 over-fetched `s_bits` beats, surplus `s_sel` beats, or a sink without TLAST after ERR/ABORT); `s_bits`/`s_sel` `tready` stay 0 from DONE/ERR/ABORT until the next accepted doorbell; in DEFLATE mode the `s_sel` DMA is not started. In the testbench the cocotbext-axi source/sink objects are re-created per block.
- **Buffer end**: bits beyond the last received bit (bit 7 of the highest valid byte of the TLAST beat) may be *peeked* (read as 0) but a code or extra-bit field that *consumes* any of them → ERR_UNDERRUN; START_BIT ≥ buffer bits → ERR_UNDERRUN at symbol 0.
- Bus traffic per benchmark block: 147 length words + ~10 control words = 157 transactions ≈ 628
  cycles (0.41 % of the 153 k-cycle model — provisional until K1 is confirmed at uArch; 4
  cycles/transaction estimated from the handshake cell, measured in `test_driver`).

Invocation sequence (software): write MODE, START_BIT, ALPHABET, N_TABLES, SYMBOL_LIMIT, length
window → start the `s_bits` DMA (and `s_sel` in bzip2 mode) and the `m_sym` sink DMA → CTRL.DOORBELL
→ STATUS shows BUSY (or ERR_PARAM/ERR_TABLE) → wait DONE/irq → read SYMBOLS, BITS, counters → W1C.

## 6. Driver API (Python, `hw/huffman_engine/driver/`, reused by `hw-integrate`)

```python
class HuffmanDriver(AccelDriver):                  # base: hw/common/driver/accel.py (grape MAS §6)
    MODE_BZIP2, MODE_DEFLATE = 0, 1
    def configure(self, mode, start_bit, alphabet, n_tables, symbol_limit=1 << 20) -> None
    def load_lengths(self, tables: list[list[int]], validate=True) -> None
                     # packs 6 per word, table-major, using ALPHABET/MODE of the last configure() (raises if none);
                     # validate=True checks 0..MAXLEN of the mode; corner tests pass validate=False to inject ERR_TABLE
    def wait_done(self, max_polls: int) -> int        # override: returns when BUSY = 0; raises on ERR_PARAM,
                     # ERR_BUSY (since start) and on the run-time ERR_* / ERR_TABLE unless raise_errors=False;
                     # hw-integrate lifts "return when BUSY = 0" into AccelDriver for all modules
    def clear(self, bits: int = 0xFFFE) -> None       # sticky bits 15:1 (no bit 16 here)
    def read_table(self, t: int) -> dict                      # DBG_SEL/DBG_DATA: count, first_code, base, symtab
    def decode_block(self, data: bytes, start_bit: int, tables, selectors: list[int] | None,
                     mode=MODE_BZIP2) -> tuple[list[int], int]  # (symbol beats as ints, bits consumed):
                     # configure + load_lengths, program the platform DMA model with data / selectors /
                     # a sink buffer, start, wait_done, collect the sink, return SYMBOLS/BITS
```

The DMA model is platform code: in the testbench, cocotbext-axi `AxiStreamSource` (bits, sel) and
`AxiStreamSink` (sym); in the report's speed-up model, a byte-count × bus-width cost.

## 7. Block diagram

`docs/block_diagram.svg`: Host/DMA (CPU + driver, AXI-Lite handshake cell, platform DMA) →
Control (register file, block FSM doorbell → build → decode → EOB, counters) → Tables (length
window, builder, six table register sets, symbol-table RAM) → Aligner (word FIFO, 64-bit window,
mode reversal) → Decoder (comparator cascade, priority encode, symbol lookup, DEFLATE extra bits)
→ Output (selector FSM from `s_sel`, beat packer → `m_sym`). Register widths, RAM organisation
and pipeline depth are uArch decisions.

## 8. Error and status behaviour

| Event | STATUS | BUSY | irq (if enabled) | Streams | Counters |
|---|---|---|---|---|---|
| doorbell accepted | BUSY | 1 | — | `s_bits` tready may rise (prefetch ≤ 4 beats); `s_sel` tready stays 0 until the last table build completes; build starts | CYCLES restarts, others 0 |
| build done, decoding | — | 1 | — | `m_sym` beats | BUILD_CYCLES |
| EOB | DONE after the EOB beat handshake and `s_sel` drain | 0 | DONE | all tready 0 | CYCLES stops |
| ABORT while BUSY | ABORTED within 8 cycles (16 during build); if the EOB beat was already handshaken (i.e. during the `s_sel` drain) the drain stops and DONE is set instead | 0 | ABORTED / DONE | no TLAST emitted on abort; tready 0; remaining `s_sel` beats left to the DMA flush | hold at abort point |
| ABORT idle / DOORBELL+ABORT | as grape MAS §8 (no-op; idle both → nothing; BUSY both → ABORT + ERR_BUSY) | | | | |
| doorbell rejected at doorbell time (F9) | ERR_PARAM, or ERR_TABLE for a length > MAXLEN | 0 | flag if its IRQ_EN bit is set (PRD-F9 errata: "no IRQ" = no DONE interrupt) | none | hold |
| over-subscribed table found during the build | ERR_TABLE; BUSY 1 → 0 | 0 | flag (if IRQ_EN) | no beats; `s_sel` tready never rose (no selector consumed); `s_bits` prefetch (≤ 4 beats) dropped | CYCLES/BUILD_CYCLES stop at the failing table (PRD-F9 errata: build-time, not doorbell-time) |
| run-time error (F10) | ERR_NOCODE / ERR_SELECTOR / ERR_SYMBOL / ERR_LIMIT / ERR_UNDERRUN | 0 | flag | no further beats, no TLAST; tready 0 | frozen at the offending symbol |
| config write while BUSY | ERR_BUSY | 1 | ERR_BUSY | — | — |
| reset | 0 | 0 | 0 | tready/tvalid 0 | 0 |

`irq` registered (1 cycle); sticky bits W1C only; doorbell clears none.

## 9. Traceability

| PRD | MAS element |
|---|---|
| F1, F5 | ADR-0006 beat, TLAST on EOB, DONE definition (§8) |
| F2 | §7 Decoder blocks (cascade, priority, lookup) + `m_sym` beat |
| F15 | §6 DMA/testbench model (cocotbext-axi source/sink), predictor = `golden/canonical_model.py` |
| F3 | DBG_SEL/DBG_DATA, BUILD_CYCLES |
| F4 | START_BIT, `s_bits` TKEEP/TLAST, zero padding, OVERFETCH |
| F6 | `m_sym`/`s_bits`/`s_sel` back-pressure (§5) |
| F7 | MODE, ALPHABET, N_TABLES, SYMBOL_LIMIT, LEN window layout, `s_sel` port, DEFLATE table mapping |
| F8 | parameters (§2) |
| F9, F10 | STATUS bits 9–15, §8 rows |
| F11 | CTRL.ABORT semantics, writable-while-BUSY set, latching |
| F12 | CYCLES/SYMBOLS/BITS/BUILD_CYCLES/OVERFETCH |
| F13 | §5 `s_bits` multi-block note |
| F14 | `cocotbext-axi` agents on all four ports (`test_driver`) |
| F16 | §3 |
| K1, K2 | CYCLES/SYMBOLS, BUILD_CYCLES |

## 10. Review findings

See `docs/review_mas.md` (written by `hw-review`).
