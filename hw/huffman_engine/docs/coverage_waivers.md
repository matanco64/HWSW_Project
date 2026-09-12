# huffman_engine — coverage analysis and waivers (dv_coverage)

Suite: 15 tests (smoke, backpressure, bench_block, random_cfg/busy, errors_reject/runtime,
abort, reset, multiblock, sel_boundary, dbg, first_latency, deflate, cover_fill), Verilator
`--coverage`, `tb/cov/func_cov.txt` + `coverage.dat`.

## Results

| Metric | Value | Gate | Status |
|---|---|---|---|
| Functional bins | 34/34 hit | all groups | ✅ |
| Line | 90.4 % (141/156) | ≥ 90 % | ✅ |
| Branch | 91.7 % (264/288) | — | ✅ |
| Toggle | 72.8 % (9,423/12,938) | ≥ 90 % | ⚠ see below |

## The toggle gap is structural, not a verification hole

3,515 of 12,938 toggle points never flip. They are **not** clustered in an unexercised
feature — they are a long tail of a few unflipped bits across nearly every register in a
control-and-storage design:

- **Provisioned-but-bounded counters/limits** (~250 points): `cycles_q[63:18]` (a 64-bit
  counter; the benchmark's own K1 is 149,281 = 18 bits), `symbol_limit`/`l_limit_o[31:21]`
  (32-bit register, PRD default 2²⁰), `bits_consumed_o[31:20]` (max block 531,571 bits),
  `overfetch_q[7:3]` (value ≤ 4 by the FIFO cap). These bits **cannot** toggle under any valid
  program — the registers are sized to the register-map field width, not the reachable value.
- **Constant ROM localparams** (~200 points): `LEN_BASE`/`DIST_BASE`/`LEN_EXTRA`/`DIST_EXTRA`
  in `huff_deflate` (RFC 1951 tables) and the builder's constants — a constant's bits toggle
  zero times by definition.
- **Sparse wide storage** (the bulk): the 288-word × 30-bit LEN window, the 6×288×9-bit symtab,
  and the 6×20×9-bit count bins are provisioned for the *union* of all configs; the top bit of
  each 5-bit length field (lengths ≤ 20, so bit 4 rarely) and the high bits of small counts do
  not flip. `cover_fill` (alphabet 288, 6 tables) writes every LEN word and builds every table,
  but a length value is still 1..15 and a per-length count is still small.

Contrast grape (96 % toggle): its FP64 physics datapath carries full-range mantissas that flip
almost every bit. A comparator-cascade decoder over narrow length/count fields cannot, and no
feasible stimulus changes that (SYMBOL_LIMIT's top bits need 2²⁷ symbols; a 64-bit cycle
counter needs 2⁶³ cycles). The design is otherwise thoroughly verified: functional 100 %, line
90.4 %, branch 91.7 %, a real DEFLATE extra-count bug and a DBG range bug found and fixed here,
the full benchmark block trace-exact, and 15 tests green on both simulators.

## Disposition

The toggle number is reported honestly as **72.8 %**. Closing it to a nominal 90 % would require
either hundreds of line-level `// verilator coverage_off` waivers around provisioned storage and
constant ROMs (each an unreachable-by-construction citation) or architecturally impossible
stimulus. The recommendation is to record toggle as measured with this analysis, treating the
90 % toggle target as calibrated for datapath-dominated modules (grape) and not meaningful for a
control/storage module — pending the human's decision at the dv_coverage gate.
