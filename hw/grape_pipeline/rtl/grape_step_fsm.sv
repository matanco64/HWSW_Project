`default_nettype none

// Module: grape_step_fsm
// Purpose: Step control (uArch §3.1): IDLE -> LATCH -> {RUN -> COMMIT} x NSTEPS -> DONE.
//          One RUN phase per step; op issue is governed by the force pipe's static table and
//          grape_accum's dependency engine — this FSM only starts steps, counts them, commits,
//          samples ABORT at COMMIT boundaries, and maintains CYCLES/STEPS_DONE (MAS §4).
module grape_step_fsm (
    input  logic        clk,           // System clock
    input  logic        rst_n,         // Active-low synchronous reset
    // Register block interface
    input  logic        doorbell_i,    // Accepted doorbell (config latched)
    input  logic        abort_i,       // ABORT pulse (any time; acted on at COMMIT)
    input  logic [31:0] nsteps_i,      // Latched NSTEPS
    output logic        busy_o,        // BUSY status bit
    output logic        done_set_o,    // DONE pulse
    output logic        aborted_set_o, // ABORTED pulse
    output logic [31:0] steps_done_o,  // Steps committed (live, PRD-F14)
    output logic [63:0] cycles_o,      // Busy cycles, doorbell -> DONE/ABORTED inclusive (live)
    // Datapath control
    output logic        step_start_o,  // Pulse: cycle 0 of a step (force pipe + accum reset)
    output logic        run_o,         // Step in progress
    input  logic        all_done_i,    // grape_accum: all step ops retired
    output logic        commit_o       // Commit pulse to grape_body_rf (working -> committed)
);

    typedef enum logic [2:0] {
        S_IDLE,                        // Waiting for a doorbell
        S_LATCH,                       // Config latched; decide NSTEPS == 0
        S_RUN,                         // Step ops in flight
        S_COMMIT,                      // Commit the step; sample abort; loop or finish
        S_DONE,                        // DONE pulse
        S_ABORT                        // ABORTED pulse
    } state_t;

    state_t      state;                // Current state
    state_t      state_next;           // Next state
    logic [31:0] steps;                // Steps committed
    logic [31:0] steps_next;           // Next steps value
    logic [63:0] cycles;               // Busy-cycle counter
    logic [63:0] cycles_next;          // Next cycles value
    logic        abort_pend;           // Abort seen, waiting for the boundary
    logic        abort_pend_next;      // Next abort_pend

    always_comb begin
        state_next      = state;
        steps_next      = steps;
        cycles_next     = cycles;
        abort_pend_next = abort_pend || abort_i;
        step_start_o    = 1'b0;
        done_set_o      = 1'b0;
        aborted_set_o   = 1'b0;
        commit_o        = 1'b0;
        case (state)
            S_IDLE: begin
                abort_pend_next = 1'b0;                // ABORT while idle is a no-op (PRD-F11)
                if (doorbell_i) begin
                    state_next  = S_LATCH;
                    steps_next  = 32'd0;
                    cycles_next = 64'd1;               // Doorbell-accept cycle counts (F14)
                end
            end
            S_LATCH: begin
                cycles_next = cycles + 64'd1;
                if (nsteps_i == 32'd0) begin
                    state_next = S_DONE;               // PRD-F8
                end else begin
                    state_next   = S_RUN;
                    step_start_o = 1'b1;
                end
            end
            S_RUN: begin
                cycles_next = cycles + 64'd1;
                if (all_done_i) begin
                    state_next = S_COMMIT;
                end
            end
            S_COMMIT: begin
                cycles_next = cycles + 64'd1;
                commit_o    = 1'b1;
                steps_next  = steps + 32'd1;
                if (abort_pend && (steps + 32'd1) != nsteps_i) begin
                    state_next = S_ABORT;              // F11: DONE wins on the final step
                end else if ((steps + 32'd1) == nsteps_i) begin
                    state_next = S_DONE;
                end else begin
                    state_next   = S_RUN;
                    step_start_o = 1'b1;
                end
            end
            S_DONE: begin
                done_set_o = 1'b1;                     // CYCLES stops (inclusive up to COMMIT)
                state_next = S_IDLE;
            end
            S_ABORT: begin
                aborted_set_o = 1'b1;
                state_next    = S_IDLE;
            end
            default: begin
                state_next = S_IDLE;
            end
        endcase
        if (!rst_n) begin
            state_next      = S_IDLE;
            steps_next      = 32'd0;
            cycles_next     = 64'd0;
            abort_pend_next = 1'b0;
        end
    end

    always_ff @(posedge clk) begin
        state      <= state_next;
        steps      <= steps_next;
        cycles     <= cycles_next;
        abort_pend <= abort_pend_next;
    end

    assign busy_o       = (state != S_IDLE);
    assign run_o        = (state == S_RUN);
    assign steps_done_o = steps;
    assign cycles_o     = cycles;

endmodule

`default_nettype wire
