`default_nettype none

// Module: ctrl_arcs
// Purpose: Formal harness for huff_ctrl (testplan §6 property 1, grape fsm_arcs pattern):
//          the invocation FSM's outputs stay consistent (PREP/DECODE/DRAIN are mutually
//          exclusive and each implies BUSY) and every terminal state returns to IDLE — a
//          DONE/ABORTED/ERR set pulse is always followed by BUSY falling (no terminal-state
//          lock-up). All inputs free; reset assumed at t = 0. Compiled with rtl/huff_ctrl.sv
//          only (see synth/formal.sby).
module ctrl_arcs (
    input logic clk,
    input logic rst_n,
    input logic doorbell_i,
    input logic abort_i,
    input logic build_done_i,
    input logic err_table_i,
    input logic skip_done_i,
    input logic stall_i,
    input logic c0_valid_i,
    input logic eob_i,
    input logic nocode_i,
    input logic err_sel_i,
    input logic underrun_i,
    input logic err_symbol_i,
    input logic limit_hit_i,
    input logic out_empty_i,
    input logic eob_sent_i,
    input logic sel_drained_i,
    input logic mode_deflate_i
);

    logic busy_w, prep_w, decode_w, drain_w, start_pulse_w, done_set_w, aborted_set_w, flush_w;
    logic [5:0] err_set_w;

    huff_ctrl dut (
        .clk(clk), .rst_n(rst_n),
        .doorbell_i(doorbell_i), .abort_i(abort_i),
        .build_done_i(build_done_i), .err_table_i(err_table_i), .skip_done_i(skip_done_i),
        .stall_i(stall_i), .c0_valid_i(c0_valid_i), .eob_i(eob_i), .nocode_i(nocode_i),
        .err_sel_i(err_sel_i), .underrun_i(underrun_i), .err_symbol_i(err_symbol_i),
        .limit_hit_i(limit_hit_i), .out_empty_i(out_empty_i), .eob_sent_i(eob_sent_i),
        .sel_drained_i(sel_drained_i), .mode_deflate_i(mode_deflate_i),
        .busy_o(busy_w), .prep_o(prep_w), .decode_o(decode_w), .drain_o(drain_w),
        .start_pulse_o(start_pulse_w), .done_set_o(done_set_w), .aborted_set_o(aborted_set_w),
        .err_set_o(err_set_w), .flush_o(flush_w)
    );

    // reset assumed at t=0 (one cycle), free afterwards
    initial assume (!rst_n);
    logic past_valid;
    initial past_valid = 1'b0;
    always_ff @(posedge clk) past_valid <= 1'b1;

    // --- safety: state-decode outputs are consistent -----------------------------------
    // PREP/DECODE/DRAIN are mutually exclusive; each implies BUSY.
    always_comb begin
        if (rst_n) begin
            assert ($countones({prep_w, decode_w, drain_w}) <= 1);
            assert (!prep_w   || busy_w);
            assert (!decode_w || busy_w);
            assert (!drain_w  || busy_w);
            // a set-pulse is a terminal-state marker: at most one fires per cycle
            assert ($countones({done_set_w, aborted_set_w, |err_set_w}) <= 1);
            // flush only accompanies ERR/ABORT (never a clean DONE)
            assert (!flush_w || !done_set_w);
        end
    end

    // --- liveness of termination: a terminal set-pulse returns to IDLE next cycle -------
    // (S_DONE/S_ERR/S_ABORT all have next-state S_IDLE, so BUSY falls the cycle after the
    //  set pulse — no terminal lock-up.)
    always_ff @(posedge clk) begin
        if (past_valid && rst_n && $past(rst_n)) begin
            if ($past(done_set_w) || $past(aborted_set_w) || $past(|err_set_w)) begin
                assert (!busy_w);
            end
        end
    end

    // --- cover: the interesting states are reachable ------------------------------------
    always_ff @(posedge clk) begin
        if (rst_n) begin
            cover (decode_w);
            cover (drain_w);
            cover (done_set_w);
            cover (aborted_set_w);
            cover (|err_set_w);
        end
    end

    logic unused;
    assign unused = ^{start_pulse_w, 1'b0};

endmodule

`default_nettype wire
