// Include the shared helper package (guarded; see fp64_pkg.sv header).  The relative path
// resolves both against -Ihw/common/rtl (lint hook, Makefile.cocotb, documented lint
// command) and against this file's own directory (how Yosys searches for includes).
`include "../../grape_pipeline/rtl/fp64_pkg.sv"
`default_nettype none

// Module: fp64_add
// Purpose: IEEE-754 binary64 adder/subtractor (sub = 1 computes a - b).  3-stage pipeline,
//          II = 1, RNE only, full subnormals, canonical qNaN 0x7FF8000000000000 output,
//          flags = {invalid, divzero (constant 0 here), overflow, underflow}, bit-exact to
//          tb/unit/fp_helpers.ref_op (numpy binary64 semantics) per docs/rtl_contracts.md.
// LATENCY = 3 (localparam below; changing it requires re-running docs/schedule_model.py).
// Stage 1: unpack, classify, magnitude order, align (57-bit-frame shift with guard/round/
//          sticky collection).  Stage 2: add/subtract + leading-zero count.  Stage 3:
//          normalize, round (shared fp64_pkg::fp_round_pack), pack, special-case mux.
module fp64_add (
    input  logic        clk,        // clock
    input  logic        rst_n,      // sync active-low; clears the valid pipeline only
    input  logic        in_valid,   // one operation issued this cycle
    input  logic        sub,        // 1 = compute a - b instead of a + b
    input  logic [63:0] a,          // IEEE-754 binary64 operand a
    input  logic [63:0] b,          // IEEE-754 binary64 operand b
    output logic        out_valid,  // asserted exactly LATENCY cycles after in_valid
    output logic [63:0] result,     // rounded binary64 result
    output logic [3:0]  flags       // {invalid, divzero, overflow, underflow}
);

  localparam int unsigned LATENCY = 3;  // input-to-output register stages (contract: 3)

  // ---------------- stage 1 (combinational): unpack, order, align ----------------
  logic         [63:0] b_eff;      // b with its sign conditionally flipped by sub
  logic         [2:0]  cls_a;      // {nan, snan, inf} classification of a
  logic         [2:0]  cls_b;      // {nan, snan, inf} classification of b_eff
  logic                spec;       // result comes from the special-case path
  logic         [63:0] spec_res;   // special-case result value
  logic                spec_inv;   // special-case invalid flag (sNaN operand or inf - inf)
  logic                a_ge_b;     // |a| >= |b_eff| (raw-bit magnitude compare)
  logic         [63:0] op_l;       // magnitude-larger operand
  logic         [63:0] op_s;       // magnitude-smaller operand
  logic         [63:0] unp_l;      // {effective exponent, significand} of op_l
  logic         [63:0] unp_s;      // {effective exponent, significand} of op_s
  logic         [10:0] d_exp;      // alignment shift distance (exp_l - exp_s, >= 0)
  logic         [6:0]  d_c;        // d_exp clamped to 63 (beyond that all bits are sticky)
  logic         [55:0] a56;        // large significand in the {53 bits, G, R, S} frame
  logic        [119:0] wide_al;    // alignment shifter: keeps every lost bit for sticky
  logic         [55:0] b56;        // aligned small significand in the same frame
  logic                stk0;       // sticky OR of all alignment bits shifted below the frame

  always_comb begin
    b_eff    = {b[63] ^ sub, b[62:0]};
    cls_a    = fp64_pkg::fp_class(a[62:0]);
    cls_b    = fp64_pkg::fp_class(b_eff[62:0]);
    spec     = 1'b0;
    spec_res = fp64_pkg::CANON_QNAN;
    spec_inv = 1'b0;
    if (cls_a[2] || cls_b[2]) begin
      // Any NaN in -> canonical qNaN out; invalid only for a signaling NaN (the oracle
      // raises nothing for a quiet NaN operand).
      spec     = 1'b1;
      spec_res = fp64_pkg::CANON_QNAN;
      spec_inv = cls_a[1] | cls_b[1];
    end else if (cls_a[0] && cls_b[0]) begin
      spec = 1'b1;
      if (a[63] == b_eff[63]) begin
        spec_res = a;                        // inf + inf of one sign -> that infinity
      end else begin
        spec_res = fp64_pkg::CANON_QNAN;     // inf - inf -> invalid qNaN
        spec_inv = 1'b1;
      end
    end else if (cls_a[0]) begin
      spec     = 1'b1;
      spec_res = a;
    end else if (cls_b[0]) begin
      spec     = 1'b1;
      spec_res = b_eff;
    end
    // Magnitude ordering (raw-bit compare orders finite magnitudes, subnormals included).
    a_ge_b  = (a[62:0] >= b_eff[62:0]);
    op_l    = a_ge_b ? a : b_eff;
    op_s    = a_ge_b ? b_eff : a;
    unp_l   = fp64_pkg::fp_unpack(op_l[62:0]);
    unp_s   = fp64_pkg::fp_unpack(op_s[62:0]);
    d_exp   = unp_l[63:53] - unp_s[63:53];
    d_c     = (d_exp > 11'd63) ? 7'd63 : d_exp[6:0];
    a56     = {unp_l[52:0], 3'b000};
    wide_al = {unp_s[52:0], 3'b000, 64'd0} >> d_c;
    b56     = wide_al[119:64];
    stk0    = |wide_al[63:0];
  end

  // ---------------- stage 1 registers ----------------
  logic                s1_spec;      // special-case path selected
  logic         [63:0] s1_spec_res;  // special-case result
  logic                s1_spec_inv;  // special-case invalid flag
  logic                s1_sign_l;    // sign of the magnitude-larger operand
  logic                s1_eff_sub;   // operand signs differ -> effective subtraction
  logic signed  [12:0] s1_exp;       // effective biased exponent of the larger operand
  logic         [55:0] s1_a56;       // large significand ({53, G, R, S} frame)
  logic         [55:0] s1_b56;       // aligned small significand (same frame)
  logic                s1_stk;       // alignment sticky (non-zero bits below the frame)

  always_ff @(posedge clk) begin
    s1_spec     <= spec;
    s1_spec_res <= spec_res;
    s1_spec_inv <= spec_inv;
    s1_sign_l   <= op_l[63];
    s1_eff_sub  <= op_l[63] ^ op_s[63];
    s1_exp      <= $signed({2'b00, unp_l[63:53]});
    s1_a56      <= a56;
    s1_b56      <= b56;
    s1_stk      <= stk0;
  end

  // ---------------- stage 2 (combinational): add/subtract + leading-zero count -------------
  logic [57:0] r58;     // significand sum/difference (never negative; bit 57 always 0)
  logic [6:0]  lz;      // leading-zero count of r58[56:0] (57 when the difference is zero)
  logic        r_zero;  // exact-zero result (full cancellation or both operands zero)

  always_comb begin
    // Effective subtraction uses the sticky bit as a borrow: the true small operand is
    // b56 + eps with 0 < eps < 1 frame LSB when stk is set, so A - B floors to
    // A - b56 - 1 and the remaining non-zero fraction stays represented by sticky.
    if (s1_eff_sub) begin
      r58 = {2'b00, s1_a56} - {2'b00, s1_b56} - {57'd0, s1_stk};
    end else begin
      r58 = {2'b00, s1_a56} + {2'b00, s1_b56};
    end
    lz     = fp64_pkg::clz64({r58[56:0], 7'd0});
    r_zero = (r58 == 58'd0);
  end

  // ---------------- stage 2 registers ----------------
  logic                s2_spec;      // special-case path selected
  logic         [63:0] s2_spec_res;  // special-case result
  logic                s2_spec_inv;  // special-case invalid flag
  logic                s2_sign;      // sign of the magnitude-larger operand
  logic                s2_eff_sub;   // effective subtraction (for the zero-sign rule)
  logic signed  [12:0] s2_exp;       // effective biased exponent of the larger operand
  logic         [56:0] s2_r57;       // raw significand result (frame: G, R, S in bits 2:0)
  logic         [6:0]  s2_lz;        // leading-zero count of s2_r57
  logic                s2_stk;       // alignment sticky carried past the add/subtract
  logic                s2_zero;      // exact-zero datapath result

  always_ff @(posedge clk) begin
    s2_spec     <= s1_spec;
    s2_spec_res <= s1_spec_res;
    s2_spec_inv <= s1_spec_inv;
    s2_sign     <= s1_sign_l;
    s2_eff_sub  <= s1_eff_sub;
    s2_exp      <= s1_exp;
    s2_r57      <= r58[56:0];
    s2_lz       <= lz;
    s2_stk      <= s1_stk;
    s2_zero     <= r_zero;
  end

  // ---------------- stage 3 (combinational): normalize, round, pack, mux ----------------
  logic         [55:0] r56;       // r57 without its (zero-here) carry bit, for left shifts
  logic         [5:0]  shl;       // left normalization shift distance (lz - 1)
  logic         [55:0] rn;        // left-normalized significand frame (MSB at bit 55)
  logic         [52:0] sig_n;     // normalized 53-bit significand
  logic                grd_n;     // guard bit below sig_n
  logic                stk_n;     // sticky OR of everything below the guard
  logic signed  [12:0] e_norm;    // biased exponent of the leading 1 of sig_n
  logic                zero_sign; // sign of an exact-zero result (RNE: x - x -> +0)
  logic         [65:0] rp;        // {ovf, unf, result} from the shared round/pack helper
  logic         [63:0] result_n;  // next result value
  logic         [3:0]  flags_n;   // next flags value

  always_comb begin
    r56 = s2_r57[55:0];
    shl = s2_lz[5:0] - 6'd1;
    rn  = r56 << shl;
    if (s2_lz == 7'd0) begin
      // Carry out of the 53-bit frame: shift right by one; bits 2:0 collapse into sticky.
      sig_n  = s2_r57[56:4];
      grd_n  = s2_r57[3];
      stk_n  = (|s2_r57[2:0]) | s2_stk;
      e_norm = s2_exp + 13'sd1;
    end else begin
      // Left-normalize.  For lz >= 3 the alignment shift was <= 1, so sticky and the low
      // frame bits are zero and the shift brings in only zeros (classic GRS argument).
      sig_n  = rn[55:3];
      grd_n  = rn[2];
      stk_n  = (|rn[1:0]) | s2_stk;
      e_norm = s2_exp + 13'sd1 - $signed({6'd0, s2_lz});
    end
    zero_sign = s2_eff_sub ? 1'b0 : s2_sign;
    rp        = fp64_pkg::fp_round_pack(s2_sign, e_norm, sig_n, grd_n, stk_n);
    if (s2_spec) begin
      result_n = s2_spec_res;
      flags_n  = {s2_spec_inv, 3'b000};
    end else if (s2_zero) begin
      result_n = {zero_sign, 63'd0};
      flags_n  = 4'b0000;
    end else begin
      result_n = rp[63:0];
      flags_n  = {1'b0, 1'b0, rp[65], rp[64]};  // {invalid, divzero, overflow, underflow}
    end
  end

  // ------------- valid pipeline (the only reset state) and output registers -------------
  logic [LATENCY-1:0] vpipe;    // valid bit travelling with each stage
  logic [LATENCY-1:0] vpipe_n;  // next valid pipeline value

  always_comb begin
    vpipe_n = rst_n ? {vpipe[LATENCY-2:0], in_valid} : {LATENCY{1'b0}};
  end

  always_ff @(posedge clk) begin
    vpipe  <= vpipe_n;
    result <= result_n;
    flags  <= flags_n;
  end

  assign out_valid = vpipe[LATENCY-1];

endmodule

`default_nettype wire
