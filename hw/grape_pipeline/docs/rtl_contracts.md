# grape_pipeline — RTL block contracts (hw-rtl stage working doc)

Shared interface rules for the FP64 leaf units (uArch §1). These are the contracts the unit
agents build and test against; the integration blocks consume them unchanged.

## Common FP64 unit interface

```systemverilog
module fp64_<op> #(...) (
    input  logic        clk,
    input  logic        rst_n,       // sync active-low; clears valid pipeline only (not data regs)
    input  logic        in_valid,    // one operation issued this cycle
    input  logic [63:0] a,           // IEEE-754 binary64 operand
    input  logic [63:0] b,           // second operand (absent on sqrt/rcp)
    output logic        out_valid,   // exactly LATENCY cycles after in_valid
    output logic [63:0] result,      // binary64, RNE, full subnormals, canonical qNaN 0x7FF8000000000000
    output logic [3:0]  flags        // {invalid, divzero, overflow, underflow}, valid with out_valid
);
```

- **No back-pressure**: the static reservation table guarantees legal issue; an SVA inside each
  II-limited unit (`sqrt`, `rcp`) asserts `in_valid` never violates II = 2.
- Latency is a `localparam LATENCY` (add/sub 3, mul 3, sqrt 30, rcp 22) exported in a comment;
  changing it requires re-running `docs/schedule_model.py` (uArch §7).
- fp64_add has an extra input `sub` (1 = a − b). fp64_sqrt_srt / fp64_rcp_nr take only `a`.
- Rounding: RNE only. Results and flags must be **bit-exact** to numpy float64 semantics as
  checked by `tb/unit/fp_helpers.py` (the same semantics as `golden/emulation.py`):
  add/sub/mul = one correctly rounded op; sqrt = correctly rounded; **rcp = correctly rounded
  1.0 / a** (equal to numpy's division, every input).
- Flags per op: invalid (any NaN operand or 0·inf, inf−inf, sqrt of negative non-zero),
  divzero (rcp of ±0), overflow / underflow per IEEE 754 default handling (underflow = tininess
  after rounding AND inexact). Quiet NaN in → canonical qNaN out, invalid NOT raised for a quiet
  NaN operand on add/mul (numpy: no warning) — **match `fp_helpers.ref_op` exactly; it is the
  oracle, argue with it only via a failing directed case discussed in the block header**.
- Pipeline registers carry X before first fill: out_valid gating makes that harmless; the unit
  must not read its own outputs.

## Unit test contract (`tb/unit/test_<block>.py`)

cocotb, `gf-cocotb` style, TOPLEVEL = the unit. Use `fp_helpers.py`: `f2b/b2f` pack-unpack,
`ref_op(op, a, b)` → (result_bits, flags) via numpy with errstate capture. Required cases:
1. directed: ±0, ±inf, qNaN/sNaN, subnormal min/max, 1.0±ulp, rounding-boundary halfway cases,
   sqrt(4.0), rcp of powers of two, the benchmark's dt = 0.01;
2. 10,000 random ops: uniform bit patterns (filtered to finite where the op needs it) AND
   magnitude-window reals (1e-5..1e2, the benchmark range);
3. II/latency check: out_valid arrives exactly LATENCY cycles after in_valid, streams at II.
Pass = 0 mismatches (bits and flags). `make -C hw/grape_pipeline sim` must stay green
(TOPLEVEL/MODULE overridden per unit: `make sim TOPLEVEL=fp64_add MODULE=unit.test_fp64_add`).
