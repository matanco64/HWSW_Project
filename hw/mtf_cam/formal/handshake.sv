`default_nettype none

// Module: handshake
// Purpose: Formal harness for the m_l AXI4-Stream handshake (testplan §3 line 152, F-06 / PRD-F6),
//          mirroring huffman formal/skid.sv. Scope: bound directly to mtf_pack (W=8), the only
//          registered-tvalid AXIS master in mtf_cam and the sole owner of the m_l tvalid/tready
//          handshake end-to-end -- so a focused packer-level property is complete without lifting
//          the whole mtf_cam top into BMC (documented scope, per the testplan note). Properties:
//            * tvalid holds with stable tdata/tkeep/tlast until tready (no dup/corrupt);
//            * a beat's tvalid falls only on a handshake or an explicit discard (S1: doorbell/reset
//              beat withdrawal) -- i.e. no beat is silently lost (flush/discard exempt);
//            * tvalid is registered and so never combinational on tready (o_valid_q; the stability
//              property is the observable consequence -- same argument as skid.sv).
//          Env: in_cnt is the packer's 1..W contract; reset assumed at t=0; all else free.
module handshake (
    input logic        clk,
    input logic        rst_n,
    input logic        in_valid,
    input logic [3:0]  in_cnt,          // $clog2(W+1) = 4 bits for W=8
    input logic [63:0] in_data,
    input logic        flush_normal,
    input logic        flush_err,
    input logic        discard,
    input logic        m_ready
);
    localparam int W = 8;

    logic        pack_ready_o, m_valid_o, m_last_o, idle_o;
    logic [63:0] m_data_o;
    logic [7:0]  m_keep_o;

    mtf_pack #(.W(W)) dut (
        .clk(clk), .rst_n(rst_n),
        .in_valid(in_valid), .in_cnt(in_cnt), .in_data(in_data),
        .pack_ready_o(pack_ready_o),
        .flush_normal(flush_normal), .flush_err(flush_err), .discard(discard),
        .m_ready(m_ready),
        .m_valid_o(m_valid_o), .m_data_o(m_data_o), .m_keep_o(m_keep_o),
        .m_last_o(m_last_o), .idle_o(idle_o)
    );

    logic unused;
    assign unused = ^{pack_ready_o, idle_o, 1'b0};

    // Reset assumed at t=0 (slang-safe: slang rejects reading a net inside an `initial` block).
    logic past_valid = 1'b0;
    always_ff @(posedge clk) past_valid <= 1'b1;
    always_comb if (!past_valid) assume (!rst_n);

    // Environment contract: the expander offers 1..W bytes when it offers any (mtf_pack §merge).
    always_comb if (rst_n) assume (!in_valid || (in_cnt >= 4'd1 && in_cnt <= 4'(W)));

    // --- safety: a valid beat carries at least one live lane -------------------------------------
    always_comb if (rst_n) begin
        assert (!m_valid_o || (m_keep_o != 8'd0));
    end

    // --- tvalid stability / no dup / no silent loss ----------------------------------------------
    always_ff @(posedge clk) begin
        if (past_valid && rst_n && $past(rst_n)) begin
            // held, un-handshaken beat is stable until taken or discarded (no dup/corrupt)
            if ($past(m_valid_o) && !$past(m_ready) && !$past(discard)) begin
                assert (m_valid_o);
                assert (m_data_o == $past(m_data_o));
                assert (m_keep_o == $past(m_keep_o));
                assert (m_last_o == $past(m_last_o));
            end
            // tvalid falls only after a handshake or an explicit discard (no silent beat loss)
            if ($past(m_valid_o) && !m_valid_o) begin
                assert ($past(m_ready) || $past(discard));
            end
        end
    end

    // --- cover: a full beat, a last beat handshaken, and backpressure held ------------------------
    always_ff @(posedge clk) if (rst_n) begin
        cover (m_valid_o && (m_keep_o == 8'hFF));         // a full W-lane beat
        cover (m_valid_o && m_ready && m_last_o);         // a TLAST beat handshaken
        cover (m_valid_o && !m_ready);                    // tvalid held under backpressure
    end

endmodule

`default_nettype wire
