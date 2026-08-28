---
status: accepted
---
# huffman_engine: comparator-cascade canonical decoder, tables built in hardware, headers parsed in software, DEFLATE as a verified mode

pyflate's runtime on the benchmark input (1 bzip2 block, 148,271 Huffman symbols, mean code
3.585 bits, lengths 2..15) is dominated by per-symbol interpreter work; the hardware target is a
fixed-function decoder that sustains one symbol per cycle. We chose the **comparator cascade**
(parallel compare of the aligned MAXLEN-bit window against per-length first_code ranges, shortest
match wins, symbol RAM lookup) over a 2^k lookup table because sky130 has no block RAM (6 tables ×
2^11 entries would be ~86 kbit of flops) and the cascade's table build is 314 steps per table
(1.3 % of the block's symbols, measured by `golden/calibrate.py`) versus 2^k fill cycles.
The **HW/SW boundary** is Matan's Rust FFI boundary: software parses the stream/block headers,
the `used` bitmap, the selector inverse-MTF and the delta-coded code lengths (1.65 % of the
stream bits) and hands the engine raw compressed bytes + a start bit offset + 6 × 147 code
lengths (AXI-Lite) + the selector list (streamed, one AXI-Stream beat per selector — 18,002 entries on chip would be 54 kbit of flops); the engine builds its tables and emits the symbol stream to
`mtf_cam` (or to DMA when verified standalone). **DEFLATE** (LSB-first, MAXLEN 15, two
alphabets, extra bits) is a required, tested mode of the same core even though the benchmark's
gzip path never runs (and is broken in stock pyflate): a mode nobody tests is not a feature. The
LZ77 window copy is a stretch block; in DEFLATE mode the engine emits literal / (length, distance)
events. **Inverse BWT stays in software** (research §3; 336 K-entry pointer chase, no sky130
fit); the report carries a quantified design sketch of an iBWT engine as discussion only.
Considered and rejected: single-bit-per-cycle canonical stepping (0.2–0.5 sym/cycle); speculative
multi-symbol decoders (area, no benefit at this scale); a fused Huffman+MTF module (breaks the
three-module plan and the standalone verification of each).
Sources: research/hw-algorithms-pyflate.md §1, §4, §6; dev/pyflate/FINDINGS.md §0, §4, §6.
