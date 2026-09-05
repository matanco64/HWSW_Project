// Include the shared helper package (guarded; see fp64_pkg.sv header).  The relative path
// resolves both against -Ihw/common/rtl (lint hook, Makefile.cocotb, documented lint
// command) and against this file's own directory (how Yosys searches for includes).
`include "../../grape_pipeline/rtl/fp64_pkg.sv"
`default_nettype none

// Module: fp64_mul
// Purpose: IEEE-754 binary64 multiplier.  3-stage pipeline, II = 1, RNE only, full
//          subnormals in and out (denormalization shift on output underflow), canonical
//          qNaN 0x7FF8000000000000 output, flags = {invalid, divzero (constant 0 here),
//          overflow, underflow}, bit-exact to tb/unit/fp_helpers.ref_op per
//          docs/rtl_contracts.md.
// LATENCY = 3 (localparam below; changing it requires re-running docs/schedule_model.py).
// Stage 1: unpack, classify, pre-normalize subnormal significands, and form two 53 x 27/26
//          partial products (splitting the 53 x 53 multiply so no stage carries the whole
//          tree — uArch section 6 timing budget).  Stage 2: sum the partial products and
//          normalize (product of [1,2) x [1,2) significands lands in [1,4)).  Stage 3:
//          round (shared fp64_pkg::fp_round_pack), pack, special-case mux.
module fp64_mul (
    input  logic        clk,        // clock
    input  logic        rst_n,      // sync active-low; clears the valid pipeline only
    input  logic        in_valid,   // one operation issued this cycle
    input  logic [63:0] a,          // IEEE-754 binary64 operand a
    input  logic [63:0] b,          // IEEE-754 binary64 operand b
    output logic        out_valid,  // asserted exactly LATENCY cycles after in_valid
    output logic [63:0] result,     // rounded binary64 product
    output logic [3:0]  flags       // {invalid, divzero, overflow, underflow}
);

  localparam int unsigned LATENCY = 3;  // input-to-output register stages (contract: 3)

  // ------- stage 1 (combinational): classify, pre-normalize, partial products -------
  logic         [2:0]  cls_a;    // {nan, snan, inf} classification of a
  logic         [2:0]  cls_b;    // {nan, snan, inf} classification of b
  logic                zero_a;   // a is +/-0
  logic                zero_b;   // b is +/-0
  logic                sign_p;   // product sign (a.sign XOR b.sign)
  logic                spec;     // result comes from the special-case path
  logic         [63:0] spec_res; // special-case result value
  logic                spec_inv; // special-case invalid flag (sNaN operand or 0 x inf)
  logic         [63:0] unp_a;    // {effective exponent, significand} of a
  logic         [63:0] unp_b;    // {effective exponent, significand} of b
  logic         [6:0]  lza;      // leading zeros of a's significand (0 for normal inputs)
  logic         [6:0]  lzb;      // leading zeros of b's significand (0 for normal inputs)
  logic         [52:0] sig_na;   // a's significand normalized so its MSB is bit 52
  logic         [52:0] sig_nb;   // b's significand normalized so its MSB is bit 52
  logic signed  [12:0] e_a;      // a's effective biased exponent after pre-normalization
  logic signed  [12:0] e_b;      // b's effective biased exponent after pre-normalization
  logic signed  [12:0] es;       // biased result exponent for a product in [1, 2)
  logic         [79:0] p_lo;     // partial product sig_na x sig_nb[26:0]
  logic         [78:0] p_hi;     // partial product sig_na x sig_nb[52:27]

  always_comb begin
    cls_a    = fp64_pkg::fp_class(a[62:0]);
    cls_b    = fp64_pkg::fp_class(b[62:0]);
    zero_a   = (a[62:0] == 63'd0);
    zero_b   = (b[62:0] == 63'd0);
    sign_p   = a[63] ^ b[63];
    spec     = 1'b0;
    spec_res = fp64_pkg::CANON_QNAN;
    spec_inv = 1'b0;
    if (cls_a[2] || cls_b[2]) begin
      // Any NaN in -> canonical qNaN out; invalid only for a signaling NaN (the oracle
      // raises nothing for a quiet NaN operand).
      spec     = 1'b1;
      spec_res = fp64_pkg::CANON_QNAN;
      spec_inv = cls_a[1] | cls_b[1];
    end else if ((cls_a[0] && zero_b) || (zero_a && cls_b[0])) begin
      spec     = 1'b1;                       // 0 x inf -> invalid qNaN
      spec_res = fp64_pkg::CANON_QNAN;
      spec_inv = 1'b1;
    end else if (cls_a[0] || cls_b[0]) begin
      spec     = 1'b1;
      spec_res = {sign_p, 11'h7FF, 52'd0};   // inf x finite non-zero -> signed infinity
    end else if (zero_a || zero_b) begin
      spec     = 1'b1;
      spec_res = {sign_p, 63'd0};            // 0 x finite -> signed exact zero, no flags
    end
    // Pre-normalize each significand: subnormal inputs are shifted so the MSB is bit 52
    // and the shift is charged to the effective exponent (which then goes below 1).
    unp_a  = fp64_pkg::fp_unpack(a[62:0]);
    unp_b  = fp64_pkg::fp_unpack(b[62:0]);
    lza    = fp64_pkg::clz64({unp_a[52:0], 11'd0});
    lzb    = fp64_pkg::clz64({unp_b[52:0], 11'd0});
    sig_na = unp_a[52:0] << lza[5:0];
    sig_nb = unp_b[52:0] << lzb[5:0];
    e_a    = $signed({2'b00, unp_a[63:53]}) - $signed({6'd0, lza});
    e_b    = $signed({2'b00, unp_b[63:53]}) - $signed({6'd0, lzb});
    es     = e_a + e_b - 13'sd1023;
    // 53 x 53 multiply split into two partial products (b sliced 27 + 26 bits).
    p_lo   = {27'd0, sig_na} * {53'd0, sig_nb[26:0]};
    p_hi   = {26'd0, sig_na} * {53'd0, sig_nb[52:27]};
  end

  // ---------------- stage 1 registers ----------------
  logic                s1_spec;      // special-case path selected
  logic         [63:0] s1_spec_res;  // special-case result
  logic                s1_spec_inv;  // special-case invalid flag
  logic                s1_sign;      // product sign
  logic signed  [12:0] s1_es;        // biased result exponent for a product in [1, 2)
  logic         [79:0] s1_plo;       // registered low partial product
  logic         [78:0] s1_phi;       // registered high partial product

  always_ff @(posedge clk) begin
    s1_spec     <= spec;
    s1_spec_res <= spec_res;
    s1_spec_inv <= spec_inv;
    s1_sign     <= sign_p;
    s1_es       <= es;
    s1_plo      <= p_lo;
    s1_phi      <= p_hi;
  end

  // ---------------- stage 2 (combinational): sum partial products + normalize ----------
  logic [105:0]       prod;     // full 106-bit significand product, value in [1, 4)
  logic               norm_hi;  // product MSB at bit 105 (value in [2, 4)): shift by one
  logic [52:0]        sig_n;    // normalized 53-bit significand
  logic               grd_n;    // guard bit below sig_n
  logic               stk_n;    // sticky OR of everything below the guard
  logic signed [12:0] e_norm;   // biased exponent of the leading 1 of sig_n

  always_comb begin
    prod    = {26'd0, s1_plo} + {s1_phi, 27'd0};
    norm_hi = prod[105];
    if (norm_hi) begin
      sig_n  = prod[105:53];
      grd_n  = prod[52];
      stk_n  = |prod[51:0];
      e_norm = s1_es + 13'sd1;
    end else begin
      sig_n  = prod[104:52];
      grd_n  = prod[51];
      stk_n  = |prod[50:0];
      e_norm = s1_es;
    end
  end

  // ---------------- stage 2 registers ----------------
  logic                s2_spec;      // special-case path selected
  logic         [63:0] s2_spec_res;  // special-case result
  logic                s2_spec_inv;  // special-case invalid flag
  logic                s2_sign;      // product sign
  logic signed  [12:0] s2_e;         // biased exponent of the leading 1
  logic         [52:0] s2_sig;       // normalized significand
  logic                s2_grd;       // guard bit
  logic                s2_stk;       // sticky bit

  always_ff @(posedge clk) begin
    s2_spec     <= s1_spec;
    s2_spec_res <= s1_spec_res;
    s2_spec_inv <= s1_spec_inv;
    s2_sign     <= s1_sign;
    s2_e        <= e_norm;
    s2_sig      <= sig_n;
    s2_grd      <= grd_n;
    s2_stk      <= stk_n;
  end

  // ---------------- stage 3 (combinational): round, pack, special-case mux ----------------
  logic [65:0] rp;        // {ovf, unf, result} from the shared round/pack helper
  logic [63:0] result_n;  // next result value
  logic [3:0]  flags_n;   // next flags value

  always_comb begin
    rp = fp64_pkg::fp_round_pack(s2_sign, s2_e, s2_sig, s2_grd, s2_stk);
    if (s2_spec) begin
      result_n = s2_spec_res;
      flags_n  = {s2_spec_inv, 3'b000};
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
