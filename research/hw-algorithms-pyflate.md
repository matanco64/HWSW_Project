# pyflate hardware acceleration — bzip2 + DEFLATE decode survey

Date: 2026-08-26. Input to the `huffman_engine` and `mtf_cam` PRD/uArch stages. Compiled by a
research agent from primary sources (URLs at the end); items marked *[unverified]* were taken from
abstracts or snippets only.

Benchmark facts: pyflate is a pure-Python **DEFLATE (gzip) and bzip2** decoder
(`benchmarks/bm_pyflate/run_benchmark.py:643-645` dispatches on file magic); the shipped input
`interpreter.tar.bz2` is bzip2 (900 kB blocks). bzip2 pipeline per block: bit reader over a Python
big-int → canonical Huffman decode (linear scan; 2–6 tables switched every 50 symbols via selectors)
→ move-to-front (256 entries) → RUNA/RUNB zero-run decode → inverse Burrows–Wheeler transform →
RLE1 expansion → CRC32. Local profile: `find_next_symbol` ~44 % cumulative, bit-buffer arithmetic
~20 %, inverse BWT ~17 %, `move_to_front` ~11 %.

## 1. Canonical Huffman decoder architectures

| Approach | Throughput | Table build per block | Area notes | Source |
|---|---|---|---|---|
| (a) Length-indexed `first_code/count`, bit-serial: shift 1 bit, `code < first_code[len]+count[len]` → `sym = symtab[base[len] + code − first_code[len]]` | 1 bit/cycle ⇒ 0.2–0.5 sym/cycle at bzip2's 2–5-bit average code | O(maxlen) = 20 (bzip2) / 15 (DEFLATE) cycles for counts + one pass over 258 lengths (~300 cycles) | tiny: comparators reused sequentially, 258 × 9-bit symbol RAM | the algorithm in pyflate / RFC 1951 §3.2.2 |
| **(a′) Comparator cascade**, parallel over lengths: extract next 20 bits, compare in parallel against `first_code[len]` for every len, priority-encode the shortest match, symtab lookup | **1 symbol/cycle** (2–3 pipeline stages: align → compare/priority → RAM) | same ~300 cycles | 20 × 20-bit comparators + 20 × (first_code, base) regs + symbol RAM per table; 6 tables → 6 register sets | same principle as Intel IoT DEFLATE decoder *[unverified detail]*; Ledwon & Cockburn |
| (b) Direct LUT indexed by next k bits → (symbol, length); two-level for long codes | 1 symbol/cycle, single RAM read; long codes cost a second read | 2^k fill cycles per table (k = 10 → 1024 × 6 tables per bzip2 block) | 2^k × 14-bit RAM per table; sky130 has no BRAM → 6 × 1024 × 14 b ≈ 86 kb of flops/OpenRAM — large | Sarangi & Baas; Ledwon/Cockburn 512-entry LUT for static codes |
| (c) Speculative / multi-symbol: decode from several bit offsets in parallel, exploit self-synchronisation, out-of-order commit | > 1 sym/cycle (Intel: +69 % from OoO speculation, 2.3× dual path; 20.5 Gb/s @ 1.4 GHz, 14 nm, 33,464 µm²) | as (b) plus replicated decoders | multiple decoders + reorder logic — overkill here | Satpathy et al. VLSI 2019; ISSCC 2018 (abstracts) |
| Encoder-side reference: Fowers et al. FCCM 2015 — fully pipelined *static* Huffman only, dynamic table build avoided as the serial bottleneck; 5.6 GB/s on Stratix V | — | — | — | Fowers et al. |

Amortisation: a 900 kB bzip2 block yields ~10⁵–10⁶ MTF symbols; 6 × ~300-cycle builds are < 1 %
overhead (6 × 1024-cycle LUT fills still < 5 %). Building in HW from the 258 × 5-bit code lengths
is cheap and avoids DMA-ing tables. Commercial datapoint: AMD Vitis zlib streaming decompressor
(dynamic + fixed Huffman) = 518 MB/s @ 283 MHz, 6.7 K LUTs, 8 BRAM ⇒ ~1.8 B/cycle (multi-byte LZ
copy, ~1 sym/cycle Huffman).

## 2. bzip2-specific stages in hardware

- **Format facts** (Wikipedia; Tsai's bzip2-format spec): MSB-first bitstream; 2–6 tables; selector
  every 50 symbols (unary-coded, MTF-coded list); code lengths delta-coded, 1–20 bits; alphabet =
  RUNA, RUNB, MTF indices 1..255, EOB; RUNA/RUNB = bijective base-2 zero-run length; origPtr 24 bits;
  RLE1 (4 repeats + count byte); block CRC32.
- **Selector FSM:** 50-symbol counter; on rollover fetch the next selector (inverse-MTF'd by SW or a
  6-entry MTF) and switch the table register set. Six register sets (20 × (first_code, base) each)
  avoid reload stalls.
- **MTF as shift-register CAM:** 256 × 8-bit register file; decode index i → read entry i (mux),
  shift entries 0..i−1 down by one, write the symbol at 0 — one symbol/cycle, ~256 8-bit registers +
  256 compare/enable cells. FPGA BWT-compressor pipelines report MTF at one character per cycle
  (Zhao et al. FPT 2017, 155 MHz NetFPGA *[unverified: abstract]*). pyflate keeps the MTF table as
  a Python list with `pop/insert` (11 % of runtime) — an easy ~50–100× win.
- **RUNA/RUNB:** accumulator `run += (1|2) << k` per run symbol; emit `run` copies of MTF[0] on the
  first non-run symbol — one cycle per symbol plus a burst writer. Zero runs are where the decoder's
  1 sym/cycle rate matters most (dense runs of 1–2-bit codes).
- **RLE1 + CRC32:** trivial streaming logic (byte/cycle) — but see §3, they stay in SW with iBWT.

## 3. Inverse BWT — memory-bound analysis (why it stays in software)

- Algorithm: cumulative counts C[256] (one pass), `T[i] = C[L[i]]++` (second pass; sequential
  writes, random reads of C only), then the output pass `p = T[p]; out = L[p]` — a **dependent-load
  chain** of N loads, each address depending on the previous load. Wuffs/libbzip2 pack
  `(byte | ptr << 8)` into one 32-bit word so it is one load per output byte.
- Per-step latency = memory latency; the chain cannot be pipelined. A 900 kB T-vector (3.6 MB) does
  not fit on-chip in sky130 (OpenRAM macros are tens of kB), so hardware would chase pointers in
  external memory — no better than a CPU whose L2 misses already dominate this stage in C decoders.
- Parallelisation requires independent chains; bzip2's permutation is a single cycle. GPU work
  (Weissenberger et al. ICPP 2024) breaks the chain via list ranking / pointer jumping (log N
  passes over the whole array), reaching 2.4 GB/s iBWT+iMTF on an A100 — bandwidth-heavy, not for a
  small ASIC. FPGA bzip2 work (Zhao FPT 2017; SFU FCCM 2019) targets the *forward* sort and names
  random memory access as the bottleneck *[unverified: abstract]*.
- **Conclusion:** iBWT is not an accelerator target for this project. pyflate's 17 % is interpreter
  overhead → software kernel (Matan's side). State this as a deliberate non-target in report §7.

## 4. DEFLATE / gzip path (RFC 1951)

- **Bit order:** LSB-first, with Huffman codes packed MSB-of-code-first ⇒ codes appear bit-reversed
  relative to bzip2. Max code length 15; two alphabets per block (lit/len 286–288 symbols, distance
  30–32). Block types: stored, fixed (RFC-defined lengths), dynamic.
- **Dynamic header:** HLIT/HDIST/HCLEN; 19 code-length-code lengths in the permuted order
  (16, 17, 18, 0, 8, …); build a 7-bit-max table; decode HLIT+HDIST lengths with symbols 16/17/18
  (repeat previous 3–6; zeros 3–10; zeros 11–138) — a small FSM reusing the canonical builder three
  times per block (Ledwon/Cockburn: 3 cycles/literal, 4 per len/dist pair @ 250 MHz HLS
  *[unverified: snippet]*).
- **Symbol decode:** lit/len symbols 257–285 → base length + 0–5 extra bits (RFC §3.2.5); distance
  symbols 0–29 → base + 0–13 extra bits. Extra bits are raw LSB-first — the aligner must serve
  "peek 15 / consume n" for codes and "read n ≤ 13 raw bits" for extras in the same or next cycle.
- **LZ77 copy engine:** 32 KB circular window (in sky130 a 32 KB OpenRAM or an external buffer — the
  largest single memory in the design). Overlapping copies (dist < len) copy at most `dist` bytes per
  beat and replicate; multi-byte-per-cycle copy raises throughput (Vitis ~1.8 B/cycle; Intel
  multi-write register-file window). The window is the past *output* stream.
- **Sharing one canonical engine:** parametrise MAXLEN (20 vs 15), add a bit-reverse mode in the
  aligner (reverse the peeked 15-bit window for DEFLATE), 2 vs up-to-6 table register sets,
  alphabet ≤ 288. The builder (counts → first_code → base → symtab) is format-agnostic. bzip2
  selectors/MTF/RUNA-RUNB and DEFLATE extra-bits/LZ77 are separate post-decoder blocks behind a
  mode bit.

## 5. Bit reader / aligner

64-bit shift register fed by a 32-bit FIFO; barrel shifter presents the next 20 (bzip2) or
15 + 13 (DEFLATE) bits; `consume(n)`, n ≤ 20 per cycle; refill when < 32 valid bits. The two-cycle
refill hazard is covered by keeping ≥ 20 spare bits. MSB-first for bzip2 (bytes enter at the top),
LSB-first for DEFLATE with per-window reversal. pyflate's big-int `>>`/`&` bit-buffer arithmetic
(20 %) disappears once the stream is DMA'd to the engine.

## 6. Recommendation — module scope and HW/SW split (adopted for the PRD)

1. **`huffman_engine`** (bzip2 + DEFLATE): approach (a′) comparator cascade — 1 symbol/cycle,
   ~300-cycle HW table build from DMA'd code lengths. SW parses the delta-coded lengths and
   selectors (small fraction of runtime); HW builds first_code/base/symtab. Targets the 44 % + 20 %
   (`find_next_symbol` + bit buffer). Expected 1 sym/cycle @ 50–100 MHz on sky130 (Tiny Tapeout
   documents ~66 MHz practical; small OpenLane pipelines reach 100–200 MHz) ⇒ 50–100 Msym/s vs
   pyflate's ~1–2 Msym/s.
2. **`mtf_cam`** + RUNA/RUNB expander chained after it: 1 sym/cycle, emits raw L-vector bytes into
   a DMA buffer ⇒ removes another 11 %. Output is the byte stream, not a full-block decode.
3. **Leave iBWT, RLE1, CRC in software** (C/NumPy-style kernel; §3). Stretch: DEFLATE LZ77 copy
   engine with 32 KB window only if area allows after all three modules sign off.
4. **Golden model / testbench:** instrument pyflate itself (`bzip2_main` / `gzip_main`) — wrap
   `find_next_symbol` / `HuffmanTable` to dump (table_id, code_len, symbol) per decode; dump
   selectors and MTF output per block. cocotb/pyuvm reads these as expected streams and feeds the
   raw bytes of `interpreter.tar.bz2` to the DUT. Stage-level traces (Huffman symbols → MTF bytes →
   L-vector → output) give per-module scoreboards.

## Sources
- Fowers et al., FCCM 2015: https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/fccm2015_cr2.pdf
- Satpathy et al., VLSI 2019 GZIP decoder: https://ieeexplore.ieee.org/document/8777934/ · IoT DEFLATE ISSCC 2018: https://ieeexplore.ieee.org/document/8494238/ (abstracts)
- Ledwon & Cockburn, FPGA DEFLATE: http://www.ece.ualberta.ca/~jhan8/publications/1570528606.pdf (snippet only)
- Sarangi & Baas, canonical Huffman decoders: https://www.sciencedirect.com/science/article/abs/pii/S0167926022001298
- AMD Vitis Data Compression benchmarks: https://xilinx.github.io/Vitis_Libraries/data_compression/2022.1/benchmark.html
- bzip2 format: https://en.wikipedia.org/wiki/Bzip2 · https://github.com/dsnet/compress/blob/master/doc/bzip2-format.pdf · https://nigeltao.github.io/blog/2022/wuffs-bzip2-decoder.html
- Weissenberger et al., ICPP 2024 GPU iBWT/iMTF: https://dl.acm.org/doi/10.1145/3673038.3673067 · https://github.com/weissenberger/bzip2gpu
- Zhao et al., FPT 2017 BWT/MTF/RLE/Huffman FPGA pipeline: https://nicsefc.ee.tsinghua.edu.cn/nics_file/pdf/publications/2017/FPT17_233_RsCput5.pdf
- SFU FCCM 2019 BWT accelerator: http://www.sfu.ca/~zhenman/files/SC3-FCCM2019-BWT.pdf
- RFC 1951: https://www.rfc-editor.org/rfc/rfc1951
- Tiny Tapeout clock guidance: https://tinytapeout.com/specs/clock/
