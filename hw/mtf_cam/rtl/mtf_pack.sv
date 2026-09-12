`default_nettype none

// Module: mtf_pack
// Purpose: Beat packer for m_l (MAS §5, PRD-F6). Accumulates the byte stream from the expander
//          into W-lane beats. A full (W-byte) beat is emitted only when a further byte forces it
//          out, never speculatively, so the block's last beat is produced by the end-of-block
//          flush and always carries TLAST -- including the exact-multiple case where the last
//          beat is full (S3). TKEEP is contiguous from lane 0; unused lanes carry 0; a normal
//          flush sets TLAST, an error/abort flush emits the partial beat with no TLAST. tvalid
//          is registered and never depends combinationally on tready. An accepted doorbell or
//          reset (discard) withdraws a still-pending beat (S1).
module mtf_pack #(
    parameter int W = 8                               // Output lanes (bytes/beat)
) (
    input  logic               clk,                   // System clock
    input  logic               rst_n,                 // Active-low synchronous reset
    // Expander input side
    input  logic               in_valid,              // Bytes valid this cycle
    input  logic [$clog2(W+1)-1:0] in_cnt,            // Number of valid bytes (1..W)
    input  logic [W*8-1:0]     in_data,               // W lanes (low in_cnt lanes are live)
    output logic               pack_ready_o,          // Packer can accept bytes this cycle
    // Flush / discard control
    input  logic               flush_normal,          // End of block: emit remainder with TLAST
    input  logic               flush_err,             // Error/abort: emit remainder, no TLAST
    input  logic               discard,               // Doorbell/reset: withdraw a pending beat (S1)
    // m_l AXI4-Stream master (registered outputs)
    input  logic               m_ready,               // m_axis_l_tready
    output logic               m_valid_o,             // m_axis_l_tvalid
    output logic [W*8-1:0]     m_data_o,              // m_axis_l_tdata
    output logic [W-1:0]       m_keep_o,              // m_axis_l_tkeep
    output logic               m_last_o,              // m_axis_l_tlast
    output logic               idle_o                 // Buffer empty, no pending beat, not flushing
);

    localparam int LCW = $clog2(W + 1);               // Lane-count width (0..W)
    localparam int MW  = $clog2(2*W + 1);             // Merged-count width (0..2W)

    logic [7:0]     buf_arr [W];                       // Buffered bytes (low buf_cnt lanes live)
    logic [LCW-1:0] buf_cnt_q;                         // Buffered byte count (0..W)
    logic           flushing_q;                        // Flush pending, remainder not yet emitted
    logic           flush_last_q;                      // TLAST value for the pending flush beat
    logic [W*8-1:0] o_data_q;                          // Registered beat data
    logic [W-1:0]   o_keep_q;                          // Registered TKEEP
    logic           o_last_q;                          // Registered TLAST
    logic           o_valid_q;                         // Registered TVALID

    logic [7:0]     buf_n   [W];                        // Next buffer
    logic [LCW-1:0] buf_cnt_n;                          // Next buffer count
    logic           flushing_n;                         // Next flushing
    logic           flush_last_n;                       // Next flush-last
    logic [W*8-1:0] o_data_n;                           // Next beat data
    logic [W-1:0]   o_keep_n;                           // Next TKEEP
    logic           o_last_n;                           // Next TLAST
    logic           o_valid_n;                          // Next TVALID

    logic beat_leaving;                                 // Current beat handshaken this cycle
    logic o_free_next;                                  // o register free to load a new beat
    logic accept_in;                                    // Consume input this cycle
    logic flush_req;                                    // A flush pulse this cycle
    logic flush_active;                                 // Flush pulse or pending
    logic flush_last;                                   // TLAST for the flush beat

    assign beat_leaving = o_valid_q && m_ready;
    assign o_free_next  = !o_valid_q || m_ready;
    assign flush_req    = flush_normal || flush_err;
    assign flush_active = flush_req || flushing_q;
    assign flush_last   = flush_req ? flush_normal : flush_last_q;

    // Accept input only when not flushing and the o register can take a forced beat.
    assign pack_ready_o = !flush_active && o_free_next;
    assign accept_in    = in_valid && pack_ready_o;

    // Merge buffer ++ incoming into a 2W-lane staging array.
    logic [7:0]    cat [2*W];                            // buffer bytes then incoming bytes
    logic [MW-1:0] merged;                               // buf_cnt + in_cnt (0..2W)
    logic          emit_full;                            // Forced full-beat emit (merged > W)

    always_comb begin
        for (int i = 0; i < 2*W; i++) begin
            cat[i] = 8'd0;
        end
        for (int i = 0; i < W; i++) begin
            if (LCW'(i) < buf_cnt_q) begin
                cat[i] = buf_arr[i];
            end
        end
        merged = {{(MW-LCW){1'b0}}, buf_cnt_q};
        if (accept_in) begin
            for (int j = 0; j < W; j++) begin
                if (LCW'(j) < in_cnt) begin
                    cat[buf_cnt_q + LCW'(j)] = in_data[j*8 +: 8];
                end
            end
            merged = {{(MW-LCW){1'b0}}, buf_cnt_q} + {{(MW-LCW){1'b0}}, in_cnt};
        end
        emit_full = accept_in && (merged > MW'(W));
    end

    logic          emit_flush;                           // Flush the buffered remainder this cycle
    logic [LCW-1:0] flush_cnt;                            // Bytes in the flush beat
    // verilator lint_off UNUSEDSIGNAL
    logic [MW-1:0] retained;                              // merged - W in 1..W; top bit unused (result <= W)
    // verilator lint_on UNUSEDSIGNAL
    assign emit_flush = flush_active && (buf_cnt_q != {LCW{1'b0}}) && o_free_next;
    assign flush_cnt  = buf_cnt_q;
    assign retained   = merged - MW'(W);

    always_comb begin
        // Buffer next-state
        for (int i = 0; i < W; i++) begin
            buf_n[i] = buf_arr[i];
        end
        buf_cnt_n = buf_cnt_q;

        if (emit_flush) begin
            buf_cnt_n = {LCW{1'b0}};
        end else if (emit_full) begin
            for (int i = 0; i < W; i++) begin
                buf_n[i] = cat[W + i];
            end
            buf_cnt_n = retained[LCW-1:0];
        end else if (accept_in) begin
            for (int i = 0; i < W; i++) begin
                buf_n[i] = cat[i];
            end
            buf_cnt_n = merged[LCW-1:0];
        end

        // Flushing pending flag
        flushing_n   = flush_active && (buf_cnt_q != {LCW{1'b0}}) && !emit_flush;
        flush_last_n = flush_req ? flush_normal : flush_last_q;

        // Output beat register
        o_valid_n = o_valid_q && !m_ready;               // Hold until handshaken
        o_data_n  = o_data_q;
        o_keep_n  = o_keep_q;
        o_last_n  = o_last_q;

        if (emit_full) begin                             // Full non-last beat
            for (int l = 0; l < W; l++) begin
                o_data_n[l*8 +: 8] = cat[l];
            end
            o_keep_n  = {W{1'b1}};
            o_last_n  = 1'b0;
            o_valid_n = 1'b1;
        end else if (emit_flush) begin                   // Final/partial flush beat
            for (int l = 0; l < W; l++) begin
                if (LCW'(l) < flush_cnt) begin
                    o_data_n[l*8 +: 8] = buf_arr[l];
                end else begin
                    o_data_n[l*8 +: 8] = 8'd0;
                end
                o_keep_n[l] = (LCW'(l) < flush_cnt);
            end
            o_last_n  = flush_last;
            o_valid_n = 1'b1;
        end

        if (discard) begin                               // Withdraw a still-pending beat (S1)
            o_valid_n    = 1'b0;
            buf_cnt_n    = {LCW{1'b0}};
            flushing_n   = 1'b0;
            flush_last_n = 1'b0;
        end
        if (!rst_n) begin
            for (int i = 0; i < W; i++) begin
                buf_n[i] = 8'd0;
            end
            buf_cnt_n    = {LCW{1'b0}};
            flushing_n   = 1'b0;
            flush_last_n = 1'b0;
            o_valid_n    = 1'b0;
            o_data_n     = {(W*8){1'b0}};
            o_keep_n     = {W{1'b0}};
            o_last_n     = 1'b0;
        end
    end

    always_ff @(posedge clk) begin
        buf_cnt_q    <= buf_cnt_n;
        flushing_q   <= flushing_n;
        flush_last_q <= flush_last_n;
        o_data_q     <= o_data_n;
        o_keep_q     <= o_keep_n;
        o_last_q     <= o_last_n;
        o_valid_q    <= o_valid_n;
        for (int i = 0; i < W; i++) begin
            buf_arr[i] <= buf_n[i];
        end
    end

    assign m_valid_o = o_valid_q;
    assign m_data_o  = o_data_q;
    assign m_keep_o  = o_keep_q;
    assign m_last_o  = o_last_q;
    assign idle_o    = (buf_cnt_q == {LCW{1'b0}}) && !o_valid_q && !flushing_q;

    // verilator lint_off UNUSEDSIGNAL
    logic unused_beat_leaving;                            // beat_leaving documents intent; folded into o_valid_n
    assign unused_beat_leaving = beat_leaving;
    // verilator lint_on UNUSEDSIGNAL

endmodule

`default_nettype wire
