`default_nettype none

// Module: mtf_run
// Purpose: RUNA/RUNB bijective-base-2 run accumulator (PRD-F3, MAS §5 Run block).
//          Accumulates n = SUM (1<<k) * (1 + s_k) over consecutive run symbols of a group
//          (s = 0 for RUNA, 1 for RUNB, k = 0,1,.. within the group). The overflow test uses a
//          22-bit sum comparing > 2^20 without wrap (M1); the stored count is RUN_W = 21 bits
//          (UQ21.0, holds 2^20). Tracks MAX_RUN, the largest run committed this invocation.
module mtf_run #(
    parameter int RUN_W = 21                         // Stored run width (holds 2^20), UQ21.0
) (
    input  logic              clk,                   // System clock
    input  logic              rst_n,                 // Active-low synchronous reset
    input  logic              clr,                   // Reset accumulator+index (doorbell, or after a run item is produced)
    input  logic              inv_clr,               // Per-invocation clear of MAX_RUN (doorbell only; R1)
    input  logic              acc_en,                // Accept one run symbol this cycle
    input  logic              run_bit,               // 0 = RUNA, 1 = RUNB (symbol value bit 0)
    input  logic              commit,                // A run item of the current n is enqueued (update MAX_RUN)
    output logic [RUN_W-1:0]  n_o,                   // Current accumulated run length, UQ21.0
    output logic              nonzero_o,             // n_o != 0 (a run group is pending)
    output logic              overflow_o,            // acc_en would push n > 2^20 (ERR_RUN, M1)
    output logic [RUN_W-1:0]  max_run_o              // Largest run committed this invocation
);

    localparam logic [21:0] RUN_MAX = 22'h10_0000;   // 2^20, UQ22.0

    logic [RUN_W-1:0] n_q;                           // Accumulator, UQ21.0
    logic [4:0]       k_q;                           // Run-symbol index within the group (bounded by overflow)
    logic [RUN_W-1:0] max_q;                         // MAX_RUN, UQ21.0

    logic [RUN_W-1:0] n_n;                           // Next accumulator
    logic [4:0]       k_n;                           // Next index
    logic [RUN_W-1:0] max_n;                         // Next MAX_RUN

    // 22-bit increment and sum (M1). base = 1<<k; RUNB doubles it. Bounded k keeps this wrap-free:
    // a valid group overflows by k<=20, and the sequencer stops acc_en at the first overflow.
    logic [21:0] base;                               // (1<<k), UQ22.0
    logic [21:0] incr;                               // base * (1 + run_bit), UQ22.0
    logic [21:0] sum;                                // n + incr, UQ22.0

    always_comb begin
        base = 22'd1 << k_q;
        incr = run_bit ? {base[20:0], 1'b0} : base;  // *2 for RUNB, *1 for RUNA
        sum  = {1'b0, n_q} + incr;

        // Overflow test is independent of acc_en (the sequencer breaks the accept/error loop
        // by gating acc_en on this flag externally, so this must not depend on acc_en, M1).
        overflow_o = (sum > RUN_MAX);

        n_n   = n_q;
        k_n   = k_q;
        max_n = max_q;

        if (acc_en && !overflow_o) begin
            n_n = sum[RUN_W-1:0];                     // sum <= 2^20 here, fits RUN_W
            k_n = k_q + 5'd1;
        end
        if (commit && (n_q > max_q)) begin
            max_n = n_q;
        end
        if (inv_clr) begin                           // R1: MAX_RUN is per-invocation — the doorbell
            max_n = {RUN_W{1'b0}};                   // clears it (doorbell in IDLE never coincides
        end                                          // with `commit` in DECODE, so this is race-free)
        if (clr) begin                               // clr wins: a produced/discarded group resets state
            n_n = {RUN_W{1'b0}};
            k_n = 5'd0;
        end
        if (!rst_n) begin
            n_n   = {RUN_W{1'b0}};
            k_n   = 5'd0;
            max_n = {RUN_W{1'b0}};
        end
    end

    always_ff @(posedge clk) begin
        n_q   <= n_n;
        k_q   <= k_n;
        max_q <= max_n;
    end

    assign n_o       = n_q;
    assign nonzero_o = (n_q != {RUN_W{1'b0}});
    assign max_run_o = max_q;

endmodule

`default_nettype wire
