// Package: fp64_pkg
// Purpose: shared IEEE-754 binary64 unpack/classify/round helpers for the FP64 leaf units
//          (fp64_add.sv, fp64_mul.sv — rtl_contracts.md "Common FP64 unit interface").
//
// How this package is consumed (documented per hw-rtl instructions):
//   * Each unit `include`s this file (the guard below makes that idempotent within one
//     compilation unit) and references every item with an explicit fp64_pkg:: scope.
//     Yosys 0.68 rejects `import fp64_pkg::*;` inside a module body but accepts scoped
//     references, so no import is used anywhere.
//   * The include path used by the units is "../../grape_pipeline/rtl/fp64_pkg.sv", which
//     resolves (a) against -Ihw/common/rtl — present in the project lint hook, in
//     hw/common/Makefile.cocotb INCLUDE_DIRS, and in the documented direct lint command —
//     and (b) against the including file's own directory, which is how Yosys searches when
//     given rtl/fp64_add.sv alone.
`ifndef FP64_PKG_SV
`define FP64_PKG_SV
`default_nettype none

package fp64_pkg;

  localparam logic [63:0] CANON_QNAN = 64'h7FF8_0000_0000_0000;  // canonical quiet NaN output

  // Canonical qNaN accessor.  Exists so the constant has an in-package reference, which
  // keeps a standalone `verilator --lint-only -Wall fp64_pkg.sv` run free of UNUSEDPARAM;
  // the units reference fp64_pkg::CANON_QNAN directly.
  function automatic logic [63:0] fp_qnan();
    fp_qnan = CANON_QNAN;
  endfunction

  // Classification of a binary64 magnitude (sign bit excluded): returns {nan, snan, inf}.
  // Zero tests are a plain (x[62:0] == 0) compare at the call site.
  function automatic logic [2:0] fp_class(input logic [62:0] m);
    logic nan;   // NaN: exponent all-ones, fraction non-zero
    logic snan;  // signaling NaN: NaN with the quiet bit (fraction MSB) clear
    logic inf;   // infinity: exponent all-ones, fraction zero
    nan  = (m[62:52] == 11'h7FF) && (m[51:0] != 52'd0);
    snan = nan && !m[51];
    inf  = (m[62:52] == 11'h7FF) && (m[51:0] == 52'd0);
    fp_class = {nan, snan, inf};
  endfunction

  // Unpack a binary64 magnitude: returns {effective biased exponent (subnormals live at
  // biased exponent 1), 53-bit significand with the hidden bit made explicit}.
  function automatic logic [63:0] fp_unpack(input logic [62:0] m);
    logic [10:0] e;  // effective biased exponent
    logic [52:0] s;  // significand with explicit hidden bit (0 for zero/subnormal)
    e = (m[62:52] == 11'd0) ? 11'd1 : m[62:52];
    s = {(m[62:52] != 11'd0), m[51:0]};
    fp_unpack = {e, s};
  endfunction

  // Count of leading zeros of a 64-bit value (returns 64 for an all-zero input).
  function automatic logic [6:0] clz64(input logic [63:0] x);
    logic [6:0] n;  // running leading-zero count
    logic       f;  // set once the first 1 has been seen
    n = 7'd0;
    f = 1'b0;
    for (int i = 63; i >= 0; i--) begin
      if (!f) begin
        if (x[i]) begin
          f = 1'b1;
        end else begin
          n = n + 7'd1;
        end
      end
    end
    clz64 = n;
  endfunction

  // Round (RNE) + pack + IEEE-754 default overflow/underflow flags.
  //   sign   : result sign bit
  //   e_norm : biased exponent of the leading 1 of sig (signed; <= 0 means the value sits
  //            in the subnormal range and must be denormalized before rounding)
  //   sig    : 53-bit normalized significand, MSB = 1, value in [1, 2)
  //   g, s   : guard and sticky bits immediately below sig at the normalized position
  // Returns {ovf, unf, result[63:0]}.
  // Underflow matches numpy/x86 (tb/unit/fp_helpers.py oracle): tininess is judged AFTER
  // rounding with unbounded exponent range, and the flag is raised only when the delivered
  // (denormalized-rounded) result is also inexact.  This means a delivered minimum-normal
  // result can legitimately carry underflow = 1 (see the directed boundary tests).
  function automatic logic [65:0] fp_round_pack(
      input logic               sign,
      input logic signed [12:0] e_norm,
      input logic [52:0]        sig,
      input logic               g,
      input logic               s);
    logic [53:0]        ext;      // {sig, g}: bits that move together on denormalization
    logic signed [12:0] dsh;      // denormalization right-shift amount (1 - e_norm)
    logic [6:0]         dsh_c;    // dsh clamped to 63 (beyond that everything is sticky)
    logic [117:0]       wide;     // {ext, 64'b0} >> dsh_c: keeps every lost bit for sticky
    logic [52:0]        sig_d;    // significand at the delivery (possibly denormal) position
    logic               g_d;      // guard bit at the delivery position
    logic               s_d;      // sticky bit at the delivery position
    logic [10:0]        exp_pre;  // pre-round exponent field at the delivery position
    logic               up;       // RNE round-up decision at the delivery position
    logic               up_n;     // RNE round-up decision at the normalized position
    logic               carry_n;  // unbounded-exponent rounding carries out of sig
    logic               tiny;     // tininess after rounding with unbounded exponent
    logic [62:0]        mag;      // packed {exponent, fraction} after the rounding increment
    if (e_norm >= 13'sd2047) begin
      // Pre-round overflow: RNE maps every such magnitude to infinity.
      fp_round_pack = {1'b1, 1'b0, sign, 11'h7FF, 52'd0};
    end else begin
      ext = {sig, g};
      if (e_norm <= 13'sd0) begin
        dsh   = 13'sd1 - e_norm;
        dsh_c = (dsh > 13'sd63) ? 7'd63 : dsh[6:0];
        wide  = {ext, 64'd0} >> dsh_c;
        sig_d = wide[117:65];
        g_d   = wide[64];
        s_d   = s | (|wide[63:0]);
      end else begin
        dsh   = 13'sd0;
        dsh_c = 7'd0;
        wide  = 118'd0;
        sig_d = sig;
        g_d   = g;
        s_d   = s;
      end
      up = g_d & (s_d | sig_d[0]);
      // Exponent field before rounding: 0 in the subnormal range (sig_d[52] is always 0
      // after a denormalizing shift of >= 1; keeping it in the expression consumes the bit
      // truthfully), else e_norm itself.  The +up increment then propagates any carry from
      // the fraction into the exponent, which handles subnormal->minimum-normal, normal
      // exponent increments, and round-up-to-infinity in a single add.
      exp_pre = (e_norm <= 13'sd0) ? {10'd0, sig_d[52]} : e_norm[10:0];
      mag     = {exp_pre, sig_d[51:0]} + {62'd0, up};
      up_n    = g & (s | sig[0]);
      carry_n = (&sig) & up_n;
      tiny    = (e_norm < 13'sd0) | ((e_norm == 13'sd0) & ~carry_n);
      fp_round_pack = {(mag[62:52] == 11'h7FF), tiny & (g_d | s_d), sign, mag};
    end
  endfunction

endpackage

`default_nettype wire
`endif
