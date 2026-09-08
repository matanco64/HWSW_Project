`default_nettype none

// Module: huff_selector
// Purpose: bzip2 selector FSM (uArch §3.3): 50-symbol counter, 1-deep selector skid fed by
//          s_axis_sel, 0-cycle table-set switch, ERR_SELECTOR when the applied value is out
//          of range. In DEFLATE mode the stream is never popped and cur_set is fixed by
//          huff_ctrl. Pop happens on `advance_i` (symbol issued) and at `start_i` (before
//          symbol 0). Empty skid at a needed pop stalls via sel_stall_o (PRD-F6).
module huff_selector (
    input  logic       clk,            // System clock
    input  logic       rst_n,          // Active-low synchronous reset
    input  logic       enable_i,       // bzip2 DECODE active (gates tready)
    input  logic       clear_i,        // Doorbell: reset skid/drained (R12 cross-invocation)
    input  logic       drain_i,        // DRAIN: accept and discard selectors to TLAST (R4)
    input  logic       start_i,        // Pulse: consume the first selector (before symbol 0)
    input  logic       advance_i,      // Pulse: one symbol issued (C0 accepted)
    input  logic [2:0] n_tables_i,     // Latched N_TABLES (range check)
    // Selector stream
    input  logic [7:0] s_sel_tdata,    // Selector in [2:0]
    input  logic       s_sel_tlast,    // Last selector
    input  logic       s_sel_tvalid,   // Valid
    output logic       s_sel_tready,   // Ready (skid has room, enabled)
    // Decode-side view
    output logic [2:0] cur_set_o,      // Active table set
    output logic       set_valid_o,    // A selector has been applied this invocation (R3)
    output logic       sel_stall_o,    // Need a selector, skid empty
    output logic       err_sel_o,      // Applied selector >= N_TABLES, or exhausted (R13)
    output logic       drained_o       // TLAST selector consumed
);

    logic [5:0] sym_cnt;               // 0..49 within the current selector run (UQ6.0)
    logic [5:0] sym_cnt_n;             // Next value
    logic [2:0] skid_val;              // Buffered next selector
    logic       skid_v;                // Skid valid
    logic       skid_last;             // Buffered TLAST
    logic       skid_v_n;              // Next skid valid
    logic [2:0] cur_set;               // Active set
    logic [2:0] cur_set_n;             // Next active set
    logic       started;               // First selector consumed
    logic       started_n;             // Next value
    logic       drained;               // TLAST consumed
    logic       drained_n;             // Next value
    logic       pending;               // A pop is owed (switch point reached, skid was empty)
    logic       pending_n;             // Next value
    logic       need_pop;              // Pop wanted this cycle (new or owed)
    logic       pop_ok;                // Skid can supply it

    assign cur_set_o = cur_set;

    always_comb begin
        // The pop for the NEXT symbol is requested at this symbol's issue (sym_cnt == 49) or
        // at start_i; with the skid full it resolves the same cycle (0-cycle switch). With
        // the skid empty it latches into `pending`, and sel_stall_o (a REGISTERED condition —
        // no advance_i circularity) freezes C0 until the skid refills.
        need_pop  = enable_i && (pending || start_i || (advance_i && sym_cnt == 6'd49));
        pop_ok    = skid_v;
        // R3: symbol 0 must wait for the first applied selector — set_valid gates C0 issue
        // in the top, so the registered `pending` has a cycle to take effect.
        // R3/N4: symbol 0 (and the DECODE-entry cycle itself) stalls until the first
        // selector has APPLIED (set_valid registers the cycle after the pop) — no exemption.
        // N10: pending stalls through its own resolution cycle (the pop's cur_set registers
        // at the edge) — a boundary refill can never issue on the old set. Self-clearing.
        sel_stall_o = pending || (enable_i && !set_valid_o);
        err_sel_o = (need_pop && pop_ok && ({29'd0, skid_val} >= {29'd0, n_tables_i}))
                    || (pending && !skid_v && drained_o);   // R13: exhausted mid-block
        s_sel_tready = (enable_i && !skid_v) || (drain_i && !drained_o);  // R4: drain to TLAST
        // next state
        sym_cnt_n = sym_cnt;
        cur_set_n = cur_set;
        skid_v_n  = skid_v;
        started_n = started;
        drained_n = drained;
        pending_n = need_pop && !pop_ok;
        if (need_pop && pop_ok) begin
            cur_set_n = skid_val;
            skid_v_n  = 1'b0;
            sym_cnt_n = 6'd0;
            started_n = 1'b1;
            if (skid_last) begin
                drained_n = 1'b1;
            end
        end else if (enable_i && advance_i) begin
            sym_cnt_n = sym_cnt + 6'd1;
        end
        if (s_sel_tvalid && s_sel_tready) begin
            skid_v_n = !drain_i;                 // drain accepts discard (R4)
            if (drain_i && s_sel_tlast) begin
                drained_n = 1'b1;
            end
        end
        if (drain_i && skid_v) begin             // N2: a surplus TLAST parked in the skid
            skid_v_n = 1'b0;
            if (skid_last) begin
                drained_n = 1'b1;
            end
        end
        if (!rst_n || (!enable_i && !drain_i)) begin
            sym_cnt_n = 6'd0;
            pending_n = 1'b0;
            if (!rst_n || clear_i) begin
                skid_v_n  = 1'b0;
                cur_set_n = 3'd0;
                drained_n = 1'b0;
                started_n = 1'b0;
            end
        end
        if (clear_i) begin                       // R12: doorbell resets invocation state
            skid_v_n  = 1'b0;
            drained_n = 1'b0;
            started_n = 1'b0;
            sym_cnt_n = 6'd0;
            pending_n = 1'b0;
        end
    end

    always_ff @(posedge clk) begin
        sym_cnt <= sym_cnt_n;
        pending <= pending_n;
        cur_set <= cur_set_n;
        skid_v  <= skid_v_n;
        started <= started_n;
        drained <= drained_n;
        if (s_sel_tvalid && s_sel_tready) begin
            skid_val  <= s_sel_tdata[2:0];
            skid_last <= s_sel_tlast;
        end
    end

    assign drained_o   = drained;
    assign set_valid_o = started;

    logic unused_ok;                   // Sink (tdata[7:3] ignored per MAS §2)
    assign unused_ok = ^s_sel_tdata[7:3];

endmodule

`default_nettype wire
