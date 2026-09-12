`default_nettype none

// Module: mtf_ctrl
// Purpose: Invocation FSM and symbol-side sequencer (MAS §3/§8, PRD-F1/F10/F11). Runs
//          IDLE -> INIT -> DECODE -> DRAIN -> {DONE|ERR|ABORT} -> IDLE. INIT triggers the list
//          fill (s_sym.tready held 0); DECODE accepts one ADR-0006 beat per cycle, decodes it
//          (value = tdata[8:0], TYPE = tdata[11:9]; TYPE 0 run/MTF, TYPE 3 EOB), drives the list
//          rank read + move-to-front and the run accumulator, and emits up to two item requests
//          per symbol (a terminating run item, then that symbol's MTF-byte item). It detects the
//          per-symbol errors ERR_RANK/ERR_RUN/ERR_UNDERRUN here and consumes the ERR_LIMIT signal
//          the top raises (byte/symbol budget). Any runtime error or an ABORT flushes the FIFO,
//          expander and pending run and flushes the packer's partial beat (no TLAST); a normal
//          EOB drain flushes it with TLAST.
module mtf_ctrl (
    input  logic        clk,                          // System clock
    input  logic        rst_n,                        // Active-low synchronous reset
    // Control from regs
    input  logic        doorbell_i,                   // Accepted-doorbell pulse
    input  logic        abort_i,                      // Abort request pulse
    // s_sym AXI4-Stream slave
    input  logic        sym_tvalid_i,                 // Beat valid
    input  logic [31:0] sym_tdata_i,                  // Beat data (ADR-0006)
    input  logic        sym_tlast_i,                  // Beat TLAST
    output logic        sym_tready_o,                 // Beat ready
    // List interface
    input  logic [8:0]  n_used_i,                     // N_USED (valid after init)
    input  logic        init_busy_i,                  // List fill in progress
    input  logic [7:0]  list_rd_byte_i,               // list[rd_rank]
    input  logic [7:0]  list_byte0_i,                 // list[0]
    output logic        init_start_o,                 // Begin the list fill
    output logic        init_active_o,                // In the INIT state (for INIT_CYCLES)
    output logic [7:0]  rd_rank_o,                    // Rank to read
    output logic        mv_en_o,                      // Move-to-front enable
    output logic [7:0]  mv_rank_o,                    // Rank moved to front
    // Run accumulator interface
    input  logic [20:0] run_n_i,                      // Current run length
    input  logic        run_nonzero_i,               // A run group is pending
    input  logic        run_overflow_i,              // acc would overflow (ERR_RUN)
    output logic        run_clr_o,                    // Reset the accumulator
    output logic        run_acc_o,                    // Accept one run symbol
    output logic        run_bit_o,                    // RUNA(0)/RUNB(1)
    // Item requests to the top (gated there by the byte budget, M3)
    output logic        item_run_valid_o,             // Terminating run item present
    output logic [20:0] item_run_n_o,                 // Run length
    output logic [7:0]  item_run_byte_o,              // Run byte (list[0])
    output logic        item_mtf_valid_o,             // MTF-byte item present
    output logic [7:0]  item_mtf_byte_o,              // MTF byte (list[rank])
    output logic        beat_accept_o,                // A beat was accepted this cycle
    output logic        is_eob_o,                     // Accepted beat is the EOB
    // ERR_LIMIT from the top (byte + symbol budget)
    input  logic        err_limit_i,                  // ERR_LIMIT this beat (stops the module)
    // FIFO / drain status
    input  logic        fifo_can_wr2_i,               // Item FIFO has >= 2 free slots
    input  logic        fifo_empty_i,                 // Item FIFO empty
    input  logic        exp_idle_i,                   // Expander idle
    input  logic        pack_idle_i,                  // Packer drained (no beat, empty buffer)
    // Flush / discard
    output logic        pipe_flush_o,                 // Discard FIFO + expander
    output logic        pack_flush_normal_o,          // Packer: emit remainder with TLAST
    output logic        pack_flush_err_o,             // Packer: emit remainder, no TLAST
    output logic        pack_discard_o,               // Packer: withdraw a pending beat (S1)
    // Status pulses to regs
    output logic        done_set_o,                   // DONE
    output logic        aborted_set_o,                // ABORTED
    output logic        err_rank_o,                   // ERR_RANK
    output logic        err_run_o,                    // ERR_RUN
    output logic        err_underrun_o,               // ERR_UNDERRUN
    output logic        busy_o                        // BUSY
);

    typedef enum logic [1:0] {
        S_IDLE,                                        // Waiting for a doorbell
        S_INIT,                                        // Filling the list
        S_DECODE,                                      // Accepting symbols
        S_DRAIN                                        // Post-EOB drain to the last beat
    } state_t;

    state_t state_q;                                   // Current state
    state_t state_n;                                   // Next state
    logic   flush_issued_q;                            // Normal drain flush issued
    logic   flush_issued_n;                            // Next

    // ---- beat decode ---------------------------------------------------------------------------
    logic [8:0] value;                                 // Symbol value
    logic [2:0] sym_type;                              // Symbol TYPE
    logic       is_type0;                              // Bzip2 run/MTF symbol
    logic       is_type3;                              // EOB
    logic       is_run;                                // RUNA/RUNB
    logic       valid_type0;                           // Valid TYPE-0 symbol (0..N_USED)
    logic       valid_eob;                             // Valid EOB (value == N_USED+1)
    logic       is_mtf;                                // Valid MTF symbol
    logic [7:0] rank;                                  // MTF rank = value - 1
    logic       beat_accept;                           // Beat handshaken this cycle

    assign value    = sym_tdata_i[8:0];
    assign sym_type = sym_tdata_i[11:9];

    // [27:12] distance and [31:28] are ignored on s_sym (MAS §2).
    // verilator lint_off UNUSEDSIGNAL
    logic [19:0] unused_tdata;                          // Sink for ignored beat bits
    // verilator lint_on UNUSEDSIGNAL
    assign unused_tdata = sym_tdata_i[31:12];

    always_comb begin
        is_type0    = (sym_type == 3'd0);
        is_type3    = (sym_type == 3'd3);
        is_run      = is_type0 && (value <= 9'd1);
        valid_type0 = is_type0 && (value <= n_used_i);            // 0,1 run; 2..N_USED MTF
        valid_eob   = is_type3 && (value == (n_used_i + 9'd1));
        is_mtf      = valid_type0 && (value >= 9'd2);
        rank        = value[7:0] - 8'd1;                          // valid only when is_mtf
        beat_accept = (state_q == S_DECODE) && sym_tvalid_i && sym_tready_o;
    end

    // ---- per-symbol error detection ------------------------------------------------------------
    logic err_underrun;                                // TLAST on a non-EOB beat
    logic err_rank;                                    // Bad type / rank / EOB mismatch
    logic err_run;                                     // Run overflow
    always_comb begin
        err_underrun = beat_accept && sym_tlast_i && !is_type3;
        err_rank     = beat_accept && !err_underrun && !valid_type0 && !valid_eob;
        err_run      = beat_accept && !err_underrun && !err_rank && is_run && run_overflow_i;
    end

    logic own_error;                                   // A ctrl-detected error this beat
    logic ext_error;                                   // ERR_LIMIT from the top
    assign own_error = err_underrun || err_rank || err_run;
    assign ext_error = err_limit_i;                    // top qualifies it with beat_accept & !own_error

    // ---- drain completion / abort --------------------------------------------------------------
    logic drain_ready;                                 // All bytes reached the packer
    logic done_now;                                    // Normal completion this cycle
    always_comb begin
        drain_ready = fifo_empty_i && exp_idle_i;
        done_now    = (state_q == S_DRAIN) && flush_issued_q && pack_idle_i;
    end

    logic abort_now;                                   // Honour an abort this cycle
    assign abort_now = abort_i && (state_q != S_IDLE) && !done_now;

    // ---- outputs / next-state ------------------------------------------------------------------
    always_comb begin
        state_n        = state_q;
        flush_issued_n = flush_issued_q;

        sym_tready_o        = 1'b0;
        init_start_o        = 1'b0;
        rd_rank_o           = 8'd0;
        mv_en_o             = 1'b0;
        mv_rank_o           = 8'd0;
        run_clr_o           = 1'b0;
        run_acc_o           = 1'b0;
        run_bit_o           = value[0];               // Ungated (used only when run_acc_o): breaks the overflow/accept loop
        item_run_valid_o    = 1'b0;
        item_run_n_o        = run_n_i;
        item_run_byte_o     = list_byte0_i;
        item_mtf_valid_o    = 1'b0;
        item_mtf_byte_o     = list_rd_byte_i;
        beat_accept_o       = beat_accept;
        is_eob_o            = beat_accept && valid_eob;
        pipe_flush_o        = 1'b0;
        pack_flush_normal_o = 1'b0;
        pack_flush_err_o    = 1'b0;
        pack_discard_o      = 1'b0;
        done_set_o          = 1'b0;
        aborted_set_o       = 1'b0;
        err_rank_o          = err_rank;
        err_run_o           = err_run;
        err_underrun_o      = err_underrun;
        rd_rank_o           = is_mtf ? rank : 8'd0;

        case (state_q)
            S_IDLE: begin
                if (doorbell_i) begin
                    init_start_o   = 1'b1;                    // Begin the fill on the doorbell cycle
                    run_clr_o      = 1'b1;                    // Reset the run accumulator
                    pack_discard_o = 1'b1;                    // Withdraw any stale pending beat (S1)
                    state_n        = S_INIT;
                end
            end

            S_INIT: begin
                if (abort_now) begin
                    aborted_set_o    = 1'b1;
                    pipe_flush_o     = 1'b1;
                    pack_flush_err_o = 1'b1;
                    state_n          = S_IDLE;
                end else if (!init_busy_i) begin             // Fill complete (>= 1 byte written)
                    state_n          = S_DECODE;
                end
            end

            S_DECODE: begin
                sym_tready_o = fifo_can_wr2_i && !abort_now;  // Accept when the FIFO has room (not while aborting)

                // Item production is a pure function of the beat (independent of ERR_LIMIT, which
                // the top derives from these very items); the top gates the actual enqueue.
                if (beat_accept && !own_error) begin
                    if (is_mtf) begin
                        item_run_valid_o = run_nonzero_i;    // Emit the pending run first
                        item_mtf_valid_o = 1'b1;             // Then this symbol's byte
                    end else if (valid_eob) begin
                        item_run_valid_o = run_nonzero_i;
                    end
                end

                // Datapath side-effects and next-state (may use ERR_LIMIT).
                if (abort_now) begin
                    aborted_set_o    = 1'b1;
                    pipe_flush_o     = 1'b1;
                    pack_flush_err_o = 1'b1;
                    state_n          = S_IDLE;
                end else if (beat_accept) begin
                    if (own_error || ext_error) begin
                        pipe_flush_o     = 1'b1;
                        pack_flush_err_o = 1'b1;
                        state_n          = S_IDLE;           // DONE=0, error flag set (regs)
                    end else if (is_run) begin
                        run_acc_o = 1'b1;
                    end else if (is_mtf) begin
                        mv_en_o   = 1'b1;
                        mv_rank_o = rank;
                        run_clr_o = 1'b1;
                    end else begin                            // valid_eob
                        run_clr_o      = 1'b1;
                        state_n        = S_DRAIN;
                        flush_issued_n = 1'b0;
                    end
                end
            end

            S_DRAIN: begin
                if (done_now) begin
                    done_set_o = 1'b1;
                    state_n    = S_IDLE;
                end else if (abort_now) begin
                    aborted_set_o    = 1'b1;
                    pipe_flush_o     = 1'b1;
                    pack_flush_err_o = 1'b1;
                    state_n          = S_IDLE;
                end else if (drain_ready && !flush_issued_q) begin
                    pack_flush_normal_o = 1'b1;              // Emit the last beat with TLAST
                    flush_issued_n      = 1'b1;
                end
            end

            default: begin
                state_n = S_IDLE;
            end
        endcase

        if (!rst_n) begin
            state_n        = S_IDLE;
            flush_issued_n = 1'b0;
        end
    end

    always_ff @(posedge clk) begin
        state_q        <= state_n;
        flush_issued_q <= flush_issued_n;
    end

    // INIT_CYCLES spans the doorbell cycle (init_start in IDLE) through the INIT state.
    assign init_active_o = init_start_o || (state_q == S_INIT);
    // BUSY rises the cycle the doorbell is accepted (MAS §8) and holds until the terminal state.
    assign busy_o        = (state_q != S_IDLE) || doorbell_i;

endmodule

`default_nettype wire
