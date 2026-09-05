`default_nettype none

// Module: fp64_sqrt_srt
// Purpose: IEEE-754 binary64 square root, correctly rounded RNE (bit-exact to numpy
//          sqrt, full subnormal support), canonical qNaN 0x7FF8000000000000 out.
//          Digit-recurrence (SRT radix-4 class: restoring recurrence retiring 2 result
//          bits per iteration) over a 56-bit root accumulator; the sticky bit comes
//          from the exact final remainder, which closes correct rounding (a binary64
//          sqrt can never land exactly on an RNE halfway point, so round-up reduces
//          to "round bit AND inexact").
//
// LATENCY = 30 (localparam, fixed for every input; special cases ±0/±inf/NaN/negative
//          and exact results all flow through the full pipe — no early exit).
// II = 2  (contract: in_valid never asserted in consecutive cycles; SVA below).
//          Up to LATENCY/II = 15 ops in flight. The recurrence datapath is shared
//          two-iterations-per-stage: 14 physical stages, each stage's single radix-4
//          iteration unit is time-multiplexed over 2 cycles per op (iteration 2s,
//          then 2s+1), so consecutive ops interleave through the same hardware.
//
// Cycle map for an op sampled at posedge E (in_valid high during the cycle ending E):
//   E      : unpack/normalize registered (pre-stage; subnormal LZC + shift inside)
//   E+1    : stage 0 loads the initial recurrence state
//   E+2..E+29 : 28 radix-4 iterations, one per cycle (stage s: edges E+2+2s, E+3+2s;
//               stage 13's second iteration feeds rounding/pack combinationally)
//   E+29   : rounded/packed result registered; out_valid (vshift bit 29) covers the
//            following cycle => out_valid exactly LATENCY = 30 edges after E.
//
// Number formats (uArch §4; TI Q notation):
//   x (radicand significand)  UQ2.52  in [1,4)      (exponent forced even)
//   root accumulator          UQ56.0  integer form = floor(sqrt(x)·2^55) when done
//                             (1 integer + 52 mantissa + round + 2 guard bits; the
//                             uArch's "55-bit root incl. guard/round" plus one more
//                             guard bit so 28 iterations retire exactly 56 bits)
//   partial remainder         UQ60.0  integer form (rem = radicand_prefix - root²,
//                             bounded by 2·root; two's-complement never needed in the
//                             restoring form — subtract only when it does not borrow)
//
// Verification: tb/unit/test_fp64_sqrt.py vs tb/unit/fp_helpers.ref_op("sqrt", a).

module fp64_sqrt_srt (
    input  logic        clk,       // System clock
    input  logic        rst_n,     // Sync active-low; clears the valid pipeline only
    input  logic        in_valid,  // One operation issued this cycle (II = 2 min spacing)
    input  logic [63:0] a,         // IEEE-754 binary64 operand
    output logic        out_valid, // Exactly LATENCY cycles after in_valid
    output logic [63:0] result,    // binary64, RNE, full subnormals, canonical qNaN
    output logic [3:0]  flags      // {invalid, divzero, overflow, underflow} w/ out_valid
);

    // ---------------------------------------------------------------- parameters --
    localparam int unsigned LATENCY = 30;  // fixed pipeline depth, every input
    localparam int unsigned NSTAGE  = 14;  // physical recurrence stages (2 iter each)
    localparam int unsigned DPW     = 172; // {root[55:0], rem[59:0], rad[55:0]}
    localparam int unsigned MTW     = 15;  // {expb[10:0], spec[1:0], inv, sign}

    // Special-case codes carried beside the datapath
    localparam logic [1:0] SP_CALC = 2'd0; // normal computation
    localparam logic [1:0] SP_ZERO = 2'd1; // ±0 in -> same signed zero out
    localparam logic [1:0] SP_INF  = 2'd2; // +inf in -> +inf out
    localparam logic [1:0] SP_NAN  = 2'd3; // NaN / negative non-zero -> canonical qNaN

    localparam logic [63:0] QNAN_BITS = 64'h7FF8_0000_0000_0000; // canonical qNaN
    localparam logic [63:0] PINF_BITS = 64'h7FF0_0000_0000_0000; // +infinity

    // ---------------------------------------------------------------- functions ---
    // Count leading zeros of a 52-bit fraction (subnormal normalization).
    function automatic logic [5:0] clz52(input logic [51:0] v);
        integer i; // scan index
        begin
            clz52 = 6'd52;
            for (i = 0; i < 52; i = i + 1) begin
                if (v[i]) begin
                    clz52 = 6'd51 - 6'(i); // last (highest) set bit wins
                end
            end
        end
    endfunction

    // One radix-4 iteration = two restoring radix-2 steps: retire 2 root bits,
    // consume 4 radicand bits. s = {root[55:0], rem[59:0], rad[55:0]}.
    function automatic logic [DPW-1:0] sqrt_iter(input logic [DPW-1:0] s);
        logic [55:0] rt0;  // root in,  UQ56.0
        logic [55:0] rt1;  // root after step 1
        logic [55:0] rt2;  // root after step 2
        logic [55:0] rd0;  // remaining radicand bits (top-aligned)
        logic [59:0] rm0;  // remainder in, UQ60.0
        logic [59:0] rm1a; // remainder with 2 radicand bits appended (step 1)
        logic [59:0] rm1;  // remainder after step 1
        logic [59:0] rm2a; // remainder with 2 radicand bits appended (step 2)
        logic [59:0] rm2;  // remainder after step 2
        logic [59:0] t1;   // trial subtrahend step 1: 4*root + 1
        logic [59:0] t2;   // trial subtrahend step 2: 4*root + 1
        logic        ge1;  // step-1 root bit (subtract did not borrow)
        logic        ge2;  // step-2 root bit
        begin
            rt0  = s[171:116];
            rm0  = s[115:56];
            rd0  = s[55:0];
            rm1a = (rm0 << 2) | {58'b0, rd0[55:54]};
            t1   = {2'b00, rt0, 2'b01};
            ge1  = rm1a >= t1;
            rm1  = ge1 ? (rm1a - t1) : rm1a;
            rt1  = (rt0 << 1) | {55'b0, ge1};
            rm2a = (rm1 << 2) | {58'b0, rd0[53:52]};
            t2   = {2'b00, rt1, 2'b01};
            ge2  = rm2a >= t2;
            rm2  = ge2 ? (rm2a - t2) : rm2a;
            rt2  = (rt1 << 1) | {55'b0, ge2};
            sqrt_iter = {rt2, rm2, (rd0 << 4)};
        end
    endfunction

    // ---------------------------------------------------------- valid shift chain --
    logic [LATENCY-1:0] vshift_q; // op-age one-hot pipeline: bit k = op sampled k+1 edges ago
    logic [LATENCY-1:0] vshift_d; // next valid pipeline value

    always_comb begin
        vshift_d = rst_n ? {vshift_q[LATENCY-2:0], in_valid} : {LATENCY{1'b0}};
    end

    always_ff @(posedge clk) begin
        vshift_q <= vshift_d;
    end

    // ------------------------------------------------------- pre-stage (unpack) ---
    logic        sign_c;    // operand sign
    logic [10:0] e_c;       // biased exponent field
    logic [51:0] f_c;       // fraction field
    logic        is_nan_c;  // any NaN
    logic        is_inf_c;  // ±infinity
    logic        is_zero_c; // ±0
    logic [5:0]  lz_c;      // leading zeros of subnormal fraction
    logic [52:0] m_c;       // normalized significand, UQ1.52 in [1,2)
    logic signed [13:0] eun_c;  // unbiased exponent (signed, [-1074, 1023])
    logic signed [13:0] er_c;   // result unbiased exponent = floor(eun/2)
    logic        odd_c;     // exponent parity
    logic [10:0] expb_c;    // biased result exponent, UQ11.0 in [486, 1534]
    logic [53:0] x_c;       // radicand significand, UQ2.52 in [1,4)
    logic [1:0]  spec_c;    // special-case code
    logic        inv_c;     // invalid flag (sNaN or negative non-zero)

    // Pre-stage registers (loaded on in_valid; consumed one cycle later)
    logic [53:0] x_q;       // registered radicand significand, UQ2.52
    logic [53:0] x_d;       // next value
    logic [10:0] expb_q;    // registered biased result exponent
    logic [10:0] expb_d;    // next value
    logic [1:0]  spec_q;    // registered special-case code
    logic [1:0]  spec_d;    // next value
    logic        inv_q;     // registered invalid flag
    logic        inv_d;     // next value
    logic        sign_q;    // registered operand sign (for -0 passthrough)
    logic        sign_d;    // next value

    always_comb begin
        sign_c    = a[63];
        e_c       = a[62:52];
        f_c       = a[51:0];
        is_nan_c  = (e_c == 11'h7FF) && (f_c != 52'b0);
        is_inf_c  = (e_c == 11'h7FF) && (f_c == 52'b0);
        is_zero_c = (e_c == 11'b0) && (f_c == 52'b0);

        lz_c = clz52(f_c);
        if (e_c == 11'b0) begin
            m_c   = {1'b0, f_c} << (lz_c + 6'd1);           // subnormal: shift MSB to bit 52
            eun_c = -14'sd1023 - $signed({8'b0, lz_c});
        end else begin
            m_c   = {1'b1, f_c};
            eun_c = $signed({3'b000, e_c}) - 14'sd1023;
        end
        odd_c  = eun_c[0];
        er_c   = eun_c >>> 1;                               // floor(E/2), incl. negative odd E
        expb_c = 11'($unsigned(er_c + 14'sd1023)); // in [486, 1534]: fits 11 bits
        x_c    = odd_c ? {m_c, 1'b0} : {1'b0, m_c};         // odd exponent: use 2·m, E-1

        if (is_nan_c) begin
            spec_c = SP_NAN;                                // qNaN quiet, sNaN invalid
        end else if (sign_c && !is_zero_c) begin
            spec_c = SP_NAN;                                // negative non-zero (incl. -inf)
        end else if (is_inf_c) begin
            spec_c = SP_INF;
        end else if (is_zero_c) begin
            spec_c = SP_ZERO;
        end else begin
            spec_c = SP_CALC;
        end
        inv_c = (is_nan_c && !f_c[51]) || (sign_c && !is_zero_c && !is_nan_c);

        // Register load (data path regs carry X before first fill; valid-qualified)
        x_d    = x_q;
        expb_d = expb_q;
        spec_d = spec_q;
        inv_d  = inv_q;
        sign_d = sign_q;
        if (in_valid) begin
            x_d    = x_c;
            expb_d = expb_c;
            spec_d = spec_c;
            inv_d  = inv_c;
            sign_d = sign_c;
        end
    end

    always_ff @(posedge clk) begin
        x_q    <= x_d;
        expb_q <= expb_d;
        spec_q <= spec_d;
        inv_q  <= inv_d;
        sign_q <= sign_d;
    end

    // ------------------------------------------------------- recurrence pipeline --
    // Initial state: root = 0, rem = 0, radicand register = top 56 bits of x·2^58
    // (the 112-bit radicand's remaining 56 bits are zero and are shifted in as such).
    logic [DPW-1:0] dp_init; // initial recurrence state from the pre-stage
    logic [MTW-1:0] mt_init; // initial meta bundle from the pre-stage

    assign dp_init = {56'b0, 60'b0, x_q, 2'b00};
    assign mt_init = {expb_q, spec_q, inv_q, sign_q};

    logic [DPW-1:0] dp_q   [0:NSTAGE-1]; // per-stage recurrence state register
    logic [DPW-1:0] dp_d   [0:NSTAGE-1]; // next state
    logic [DPW-1:0] dp_out [0:NSTAGE-1]; // shared iteration unit output
    logic [MTW-1:0] mt_q   [0:NSTAGE-1]; // per-stage meta register
    logic [MTW-1:0] mt_d   [0:NSTAGE-1]; // next meta

    generate
        for (genvar s = 0; s < NSTAGE; s++) begin : g_stage
            assign dp_out[s] = sqrt_iter(dp_q[s]);

            if (s == 0) begin : g_head
                // Stage 0 loads the initial state (vshift bit 0), then reloads its
                // own iteration output one cycle later (vshift bit 1).
                always_comb begin
                    dp_d[0] = dp_q[0];
                    mt_d[0] = mt_q[0];
                    if (vshift_q[0]) begin
                        dp_d[0] = dp_init;
                        mt_d[0] = mt_init;
                    end else if (vshift_q[1]) begin
                        dp_d[0] = dp_out[0];
                    end
                end
            end else begin : g_body
                // Stage s takes the previous stage's second-iteration output as its
                // handoff (vshift bit 2s), then its own first-iteration output
                // (vshift bit 2s+1). With II >= 2 the two enables never coincide.
                always_comb begin
                    dp_d[s] = dp_q[s];
                    mt_d[s] = mt_q[s];
                    if (vshift_q[2 * s]) begin
                        dp_d[s] = dp_out[s-1];
                        mt_d[s] = mt_q[s-1];
                    end else if (vshift_q[2 * s + 1]) begin
                        dp_d[s] = dp_out[s];
                    end
                end
            end

            always_ff @(posedge clk) begin
                dp_q[s] <= dp_d[s];
                mt_q[s] <= mt_d[s];
            end
        end
    endgenerate

    // --------------------------------------------------------- round and pack -----
    logic [55:0] q_w;      // final root: floor(sqrt(x)·2^55), UQ56.0
    logic [59:0] remf_w;   // final remainder (exactness witness), UQ60.0
    logic [55:0] radf_w;   // radicand register leftover (always 0; folded into sticky)
    logic        sticky_w; // any non-zero residue below the round bit
    logic        rnd_w;    // RNE round-up decision
    logic [53:0] mant_w;   // rounded significand incl. hidden bit and carry-out
    logic [10:0] expo_w;   // final biased exponent (carry adjust; unreachable for sqrt)
    logic [10:0] expb_p;   // piped biased exponent
    logic [1:0]  spec_p;   // piped special code
    logic        inv_p;    // piped invalid flag
    logic        sign_p;   // piped operand sign
    logic [63:0] comp_w;   // composed result

    always_comb begin
        {q_w, remf_w, radf_w}          = dp_out[NSTAGE-1];
        {expb_p, spec_p, inv_p, sign_p} = mt_q[NSTAGE-1];

        sticky_w = (remf_w != 60'b0) || (radf_w != 56'b0);
        // RNE: a binary64 sqrt is never exactly halfway (q[2]=1 with zero sticky is
        // impossible), so the LSB tie-break term q_w[3] is provably redundant but kept
        // for a self-evidently correct round-to-nearest-even expression.
        rnd_w  = q_w[2] && (q_w[3] || q_w[1] || q_w[0] || sticky_w);
        mant_w = {1'b0, q_w[55:3]} + {53'b0, rnd_w};
        // Carry out of rounding (mant = 2.0): provably unreachable for sqrt, handled
        // anyway. Invariant: exactly one of mant_w[53], mant_w[52] is set.
        expo_w = expb_p + {10'b0, (mant_w[53] & ~mant_w[52])};

        case (spec_p)
            SP_NAN:  comp_w = QNAN_BITS;
            SP_INF:  comp_w = PINF_BITS;
            SP_ZERO: comp_w = {sign_p, 63'b0};
            default: comp_w = {1'b0, expo_w, mant_w[51:0]};
        endcase
    end

    // ------------------------------------------------------------ output stage ----
    logic [63:0] res_q;  // result register
    logic [63:0] res_d;  // next result value
    logic [3:0]  flg_q;  // flags register
    logic [3:0]  flg_d;  // next flags value

    always_comb begin
        res_d = res_q;
        flg_d = flg_q;
        if (vshift_q[LATENCY-2]) begin
            res_d = comp_w;
            flg_d = {inv_p, 3'b000}; // sqrt raises only invalid; never dz/of/uf
        end
    end

    always_ff @(posedge clk) begin
        res_q <= res_d;
        flg_q <= flg_d;
    end

    assign out_valid = vshift_q[LATENCY-1];
    assign result    = res_q;
    assign flags     = out_valid ? flg_q : 4'b0000;

    // ------------------------------------------------------------ assertions ------
`ifdef VERILATOR
    // II = 2 contract (rtl_contracts.md): the static reservation table guarantees
    // in_valid is never asserted on consecutive cycles; this SVA catches violations.
    assert property (@(posedge clk) disable iff (!rst_n) in_valid |=> !in_valid)
        else $error("fp64_sqrt_srt: II=2 violated (in_valid on consecutive cycles)");
`endif

endmodule

`default_nettype wire
