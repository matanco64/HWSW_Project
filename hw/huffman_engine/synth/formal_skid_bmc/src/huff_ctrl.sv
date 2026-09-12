`default_nettype none

// Module: huff_ctrl
// Purpose: Invocation FSM (uArch §3.1): IDLE → PREP (BUILD ∥ SKIP) → DECODE → DRAIN →
//          DONE/ERR/ABORT. Aggregates the C0-visible stop events, applies the DRAIN abort
//          disposition (DONE wins after the EOB handshake — review N5), bounds ABORT
//          latency to symbol/word/table boundaries (PRD-F11), and drives the sticky-status
//          pulses into huff_regs. ERR_LIMIT is a drain-style stop raised at the LIMIT'th
//          handshake (uArch §2/N3).
module huff_ctrl (
    input  logic        clk,            // System clock
    input  logic        rst_n,          // Active-low synchronous reset
    // From huff_regs
    input  logic        doorbell_i,     // Accepted doorbell (config latched, checks passed)
    input  logic        abort_i,        // ABORT pulse
    // PREP inputs
    input  logic        build_done_i,   // All tables built
    input  logic        err_table_i,    // Kraft violation during PREFIX (pulse)
    input  logic        skip_done_i,    // START_BIT reached
    // DECODE inputs (evaluated only when issue_ok_o could fire)
    input  logic        stall_i,        // Pipeline frozen (skid full / selector / occ / deflate)
    input  logic        c0_valid_i,     // Aligner window valid (occ_ok)
    input  logic        eob_i,          // C0: EOB decoded
    input  logic        nocode_i,       // C0: no length matched
    input  logic        err_sel_i,      // Selector out of range (applied)
    input  logic        underrun_i,     // Aligner: consume past last valid bit
    input  logic        err_symbol_i,   // DEFLATE resolve: invalid code
    input  logic        limit_hit_i,    // The LIMIT'th beat handshaked (drain-style stop)
    // DRAIN inputs
    input  logic        out_empty_i,    // Output skid empty
    input  logic        eob_sent_i,     // EOB beat handshaked (TLAST out)
    input  logic        sel_drained_i,  // Selector TLAST consumed (bzip2)
    input  logic        mode_deflate_i, // Latched MODE
    // Control outputs
    output logic        busy_o,         // BUSY status bit
    output logic        prep_o,         // In PREP (builder + skip run)
    output logic        decode_o,       // In DECODE (issue enabled when !stall)
    output logic        drain_o,        // In DRAIN
    output logic        start_pulse_o,  // 1-cycle pulse entering DECODE (selector first pop)
    output logic        done_set_o,     // Pulse: DONE sticky
    output logic        aborted_set_o,  // Pulse: ABORTED sticky
    output logic [5:0]  err_set_o,      // Pulses: {LIMIT, SYMBOL, UNDERRUN, SELECTOR, NOCODE, TABLE}
    output logic        flush_o         // Withdraw output beats (ERR/ABORT; not ERR_LIMIT)
);

    typedef enum logic [2:0] {
        S_IDLE,                         // Waiting for a doorbell
        S_PREP,                         // BUILD ∥ SKIP
        S_DECODE,                       // Symbol loop
        S_DRAIN,                        // EOB seen; empty the skid, finish selectors
        S_DONE,                         // Set DONE, back to idle
        S_ERR,                          // Set the error sticky, flush
        S_ABORT                         // Set ABORTED, flush
    } state_t;

    state_t     state;                  // Current state
    state_t     state_n;                // Next state
    logic [5:0] err_n;                  // Error pulse set (next)
    logic       abort_pend;             // Abort latched until a boundary
    logic       abort_pend_n;           // Next value
    logic       start_pulse_n;          // Next start pulse

    always_comb begin
        state_n        = state;
        err_n          = 6'd0;
        abort_pend_n   = abort_pend | abort_i;
        start_pulse_n  = 1'b0;
        case (state)
            S_IDLE: begin
                abort_pend_n = 1'b0;    // ABORT while idle is a no-op (PRD-F11)
                if (doorbell_i) begin
                    state_n = S_PREP;
                end
            end
            S_PREP: begin
                if (err_table_i) begin
                    state_n = S_ERR;
                    err_n[0] = 1'b1;
                end else if (underrun_i) begin
                    state_n = S_ERR;    // R8: START_BIT beyond the stream
                    err_n[3] = 1'b1;
                end else if (abort_pend_n) begin
                    state_n = S_ABORT;  // table/word boundary: PREP steps are 1-cycle
                end else if (build_done_i && skip_done_i) begin
                    state_n       = S_DECODE;
                    start_pulse_n = 1'b1;
                end
            end
            S_DECODE: begin
                // C0 stop events (evaluated on un-stalled cycles with a valid window)
                if (!stall_i && c0_valid_i && eob_i) begin
                    state_n = S_DRAIN;
                end else if (!stall_i && c0_valid_i && nocode_i) begin
                    state_n = S_ERR;
                    err_n[1] = 1'b1;
                end else if (err_sel_i) begin
                    state_n = S_ERR;
                    err_n[2] = 1'b1;
                end else if (underrun_i) begin
                    state_n = S_ERR;
                    err_n[3] = 1'b1;
                end else if (err_symbol_i) begin
                    state_n = S_ERR;
                    err_n[4] = 1'b1;
                end else if (limit_hit_i) begin
                    state_n = S_ERR;    // drain-style: beats up to LIMIT already handshaked
                    err_n[5] = 1'b1;
                end else if (abort_pend_n) begin
                    state_n = S_ABORT;  // symbol boundary
                end
            end
            S_DRAIN: begin
                if (abort_pend_n && eob_sent_i && out_empty_i) begin
                    state_n = S_DONE;   // N3/MAS §8: abort after the EOB handshake — DONE
                end else if (abort_pend_n && !eob_sent_i) begin
                    state_n = S_ABORT;  // N5: abort before the EOB handshake
                end else if (out_empty_i && eob_sent_i
                             && (mode_deflate_i || sel_drained_i)) begin
                    state_n = S_DONE;   // R5/N5: TLAST handshaken, then DONE wins
                end
            end
            S_DONE:  state_n = S_IDLE;
            S_ERR:   state_n = S_IDLE;
            S_ABORT: state_n = S_IDLE;
            default: state_n = S_IDLE;
        endcase
        if (!rst_n) begin
            state_n      = S_IDLE;
            abort_pend_n = 1'b0;
            err_n        = 6'd0;
        end
    end

    always_ff @(posedge clk) begin
        state         <= state_n;
        abort_pend    <= abort_pend_n && !(state_n == S_ABORT || state_n == S_IDLE);
        start_pulse_o <= start_pulse_n;
        err_set_o     <= err_n;
        done_set_o    <= (state_n == S_DONE) && (state != S_DONE);
        aborted_set_o <= (state_n == S_ABORT) && (state != S_ABORT);
    end

    assign busy_o   = (state != S_IDLE);
    assign prep_o   = (state == S_PREP);
    assign decode_o = (state == S_DECODE);
    assign drain_o  = (state == S_DRAIN);
    assign flush_o  = (state == S_ERR) || (state == S_ABORT);

endmodule

`default_nettype wire
