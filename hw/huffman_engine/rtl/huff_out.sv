`default_nettype none

// Module: huff_out
// Purpose: 2-deep output skid on m_axis_sym (uArch §1/§8): tvalid never combinationally
//          depends on tready (PRD-F6); ADR-0006 withdrawal = flush on ERR/ABORT/doorbell
//          (ERR_LIMIT exempt — it drains, uArch §2/N3); SYMBOLS counts handshaken beats,
//          full_o backpressures the pipeline when both slots hold beats.
module huff_out (
    input  logic        clk,           // System clock
    input  logic        rst_n,         // Active-low synchronous reset
    // Push side (C2)
    input  logic        push_i,        // Push a beat (guaranteed !full_o by the pipeline)
    input  logic [31:0] push_data_i,   // Beat per MAS §2 (ADR-0006 encoding)
    input  logic        push_last_i,   // TLAST (EOB beat)
    input  logic        flush_i,       // Withdraw un-handshaken beats (ERR/ABORT/doorbell)
    // AXI-Stream out
    output logic [31:0] m_sym_tdata,   // Beat
    output logic        m_sym_tlast,   // TLAST
    output logic        m_sym_tvalid,  // Valid (registered)
    input  logic        m_sym_tready,  // Ready
    // Status
    output logic        full_o,        // Both slots occupied (stall C0..C2)
    output logic        empty_o,       // Nothing pending (DRAIN exit condition)
    output logic        beat_o,        // Pulse: a beat handshaked (SYMBOLS counter)
    output logic [1:0]  occ_o          // Occupied slots (issue-side almost-full gating, R1)
);

    // verilator coverage_off
    // Toggle exclusion (§5): beat skid holds {last, data}; the [27:12] distance field is 0 in bzip2 (the benchmark) and the top value bits track the alphabet.
    logic [32:0] slot0, slot1;         // {last, data}; slot0 is the head
    // verilator coverage_on
    logic        v0, v1;               // Occupancy
    logic        v0_n, v1_n;           // Next occupancy
    // verilator coverage_off
    logic [32:0] slot0_n, slot1_n;     // Next contents
    // verilator coverage_on
    logic        take;                 // Head handshakes this cycle

    assign m_sym_tdata  = slot0[31:0];
    assign m_sym_tlast  = slot0[32];
    // S1 (dv_signoff review) considered and REJECTED: masking the handshake with !flush_i
    // over-withdraws — on ERR the last valid beat already in the skid must still deliver in
    // the flush cycle (ERR_NOCODE delivers the N valid symbols before the erroring one;
    // golden/testplan expects SYMBOLS = N). The "flush-cycle transfer" the reviewer flagged is
    // the intended valid-beat delivery, not a leak. flush clears the NEXT state (v0_n/v1_n),
    // withdrawing only beats not yet handshaked after this cycle. Left as-is.
    assign m_sym_tvalid = v0;
    assign take   = v0 && m_sym_tready;
    assign full_o = v0 && v1;
    assign empty_o = !v0 && !v1;
    assign beat_o = take;
    assign occ_o  = {1'b0, v0} + {1'b0, v1};

    always_comb begin
        v0_n    = v0;
        v1_n    = v1;
        slot0_n = slot0;
        slot1_n = slot1;
        if (take) begin
            slot0_n = slot1;
            v0_n    = v1;
            v1_n    = 1'b0;
        end
        if (push_i) begin
            if (v0_n) begin
                slot1_n = {push_last_i, push_data_i};
                v1_n    = 1'b1;
            end else begin
                slot0_n = {push_last_i, push_data_i};
                v0_n    = 1'b1;
            end
        end
        if (flush_i || !rst_n) begin
            v0_n = 1'b0;
            v1_n = 1'b0;
        end
    end

    always_ff @(posedge clk) begin
        v0    <= v0_n;
        v1    <= v1_n;
        slot0 <= slot0_n;
        slot1 <= slot1_n;
    end

`ifdef SIMULATION
    always_comb begin
        assert (!(push_i && full_o)) else $error("huff_out: push while full");
    end
`endif

endmodule

`default_nettype wire
