`default_nettype none

// Module: fsm_arcs
// Purpose: Formal harness for grape_step_fsm (testplan §6 property 1): only the uArch §3.1
//          arcs are reachable and DONE_S/ABORT_S always return to IDLE. The state is decoded
//          from the DUT's output pulses (unique per state), so the assertions also prove the
//          outputs stay consistent with the state they claim. Inputs are free; reset is
//          assumed at t = 0. Lint note: compiled only with rtl/grape_step_fsm.sv (sby script).
module fsm_arcs (
    input logic        clk,           // Formal clock
    input logic        rst_n,         // Active-low reset (assumed at t=0)
    input logic        doorbell_i,    // Free input
    input logic        abort_i,       // Free input
    input logic [31:0] nsteps_i,      // Free input
    input logic        all_done_i     // Free input
);

    logic        busy_w;              // DUT busy
    logic        done_set_w;          // DUT DONE pulse
    logic        aborted_set_w;       // DUT ABORTED pulse
    logic [31:0] steps_done_w;        // DUT steps
    logic [63:0] cycles_w;            // DUT cycles
    logic        step_start_w;        // DUT step start
    logic        run_w;               // DUT run
    logic        commit_w;            // DUT commit

    grape_step_fsm dut (
        .clk(clk), .rst_n(rst_n),
        .doorbell_i(doorbell_i), .abort_i(abort_i), .nsteps_i(nsteps_i),
        .busy_o(busy_w), .done_set_o(done_set_w), .aborted_set_o(aborted_set_w),
        .steps_done_o(steps_done_w), .cycles_o(cycles_w),
        .step_start_o(step_start_w), .run_o(run_w), .all_done_i(all_done_i),
        .commit_o(commit_w)
    );

    // State decode from outputs — exactly one code per uArch §3.1 state
    localparam logic [2:0] IDLE = 3'd0, LATCH = 3'd1, RUN = 3'd2, COMMIT = 3'd3,
                           DONE_S = 3'd4, ABORT_S = 3'd5, BAD = 3'd7;
    logic [2:0] st;                   // Decoded state
    always_comb begin
        st = BAD;
        if (!busy_w && !run_w && !commit_w && !done_set_w && !aborted_set_w) st = IDLE;
        else if (busy_w && run_w && !commit_w && !done_set_w && !aborted_set_w) st = RUN;
        else if (busy_w && !run_w && commit_w && !done_set_w && !aborted_set_w) st = COMMIT;
        else if (busy_w && !run_w && !commit_w && done_set_w && !aborted_set_w) st = DONE_S;
        else if (busy_w && !run_w && !commit_w && !done_set_w && aborted_set_w) st = ABORT_S;
        else if (busy_w && !run_w && !commit_w && !done_set_w && !aborted_set_w) st = LATCH;
    end

    logic past_valid;                 // First-cycle guard
    logic [2:0] st_q;                 // Previous decoded state
    initial past_valid = 1'b0;
    always @(posedge clk) begin
        past_valid <= 1'b1;
        st_q <= st;
    end

    initial assume (!rst_n);          // Cycle 0 in reset, then free

    always @(posedge clk) begin
        if (rst_n) begin
            // Output encodings always decode to a real state
            assert (st != BAD);
        end
        if (past_valid && $past(rst_n) && rst_n) begin
            // Legal arc set — one property per source state (uArch §3.1)
            if (st_q == IDLE)    assert (st == IDLE || st == LATCH);
            if (st_q == LATCH)   assert (st == RUN || st == DONE_S);
            if (st_q == RUN)     assert (st == RUN || st == COMMIT);
            if (st_q == COMMIT)  assert (st == RUN || st == DONE_S || st == ABORT_S);
            if (st_q == DONE_S)  assert (st == IDLE);          // always returns
            if (st_q == ABORT_S) assert (st == IDLE);
            // LATCH with NSTEPS==0 goes straight to DONE (PRD-F8 arc)
            if (st_q == LATCH && $past(nsteps_i) == 32'd0)
                assert (st == DONE_S);
        end
    end

    // Reachability covers: every state
    always @(posedge clk) begin
        if (rst_n) begin
            cover (st == LATCH);
            cover (st == RUN);
            cover (st == COMMIT);
            cover (st == DONE_S);
            cover (st == ABORT_S);
        end
    end

endmodule

`default_nettype wire
