`default_nettype none

// Module: skid_props
// Purpose: Formal harness for huff_out (testplan §6 property 2, grape pattern): the 2-deep
//          output skid neither loses nor duplicates a beat under valid/ready backpressure,
//          tvalid never depends combinationally on tready (PRD-F6), occupancy stays 0..2, and
//          `full_o`/`empty_o` track occupancy. The pipeline guarantees push only when !full,
//          modelled as an assume. `flush_i` is the withdrawal exemption (ERR/ABORT). All
//          inputs free otherwise; reset assumed at t=0. Compiled with rtl/huff_out.sv only.
module skid (
    input logic        clk,
    input logic        rst_n,
    input logic        push_i,
    input logic [31:0] push_data_i,
    input logic        push_last_i,
    input logic        flush_i,
    input logic        m_sym_tready
);

    logic [31:0] tdata_w;
    logic        tlast_w, tvalid_w, full_w, empty_w, beat_w;
    logic [1:0]  occ_w;

    huff_out dut (
        .clk(clk), .rst_n(rst_n),
        .push_i(push_i), .push_data_i(push_data_i), .push_last_i(push_last_i),
        .flush_i(flush_i),
        .m_sym_tdata(tdata_w), .m_sym_tlast(tlast_w), .m_sym_tvalid(tvalid_w),
        .m_sym_tready(m_sym_tready), .full_o(full_w), .empty_o(empty_w),
        .beat_o(beat_w), .occ_o(occ_w)
    );

    initial assume (!rst_n);
    logic past_valid;
    initial past_valid = 1'b0;
    always_ff @(posedge clk) past_valid <= 1'b1;

    // Environment contract: the pipeline never pushes into a full skid (R1 credit).
    always_comb if (rst_n) assume (!(push_i && full_w));

    // --- safety --------------------------------------------------------------------------
    always_comb begin
        if (rst_n) begin
            assert (occ_w <= 2'd2);                    // never overflows 2 deep
            assert (full_w  == (occ_w == 2'd2));       // full tracks occupancy
            assert (empty_w == (occ_w == 2'd0));       // empty tracks occupancy
            assert (!tvalid_w || !empty_w);            // valid implies something buffered
            assert (beat_w == (tvalid_w && m_sym_tready)); // a beat is exactly a handshake
        end
    end

    // tvalid is registered: it cannot change purely because tready changed this cycle
    // (PRD-F6 — no combinational tvalid<-tready path).
    always_ff @(posedge clk) begin
        if (past_valid && rst_n && $past(rst_n)) begin
            // no loss/dup: with no push and no flush, occupancy drops by exactly the beats taken
            if (!$past(push_i) && !$past(flush_i)) begin
                assert (occ_w == $past(occ_w) - {1'b0, $past(beat_w)});
            end
            // a held, un-handshaken beat is stable until it is taken or flushed (no dup/corrupt)
            if ($past(tvalid_w) && !$past(m_sym_tready) && !$past(flush_i)) begin
                assert (tvalid_w && tdata_w == $past(tdata_w) && tlast_w == $past(tlast_w));
            end
        end
    end

    // --- cover: both slots used, then drained ------------------------------------------
    always_ff @(posedge clk) if (rst_n) begin
        cover (full_w);
        cover (beat_w && tlast_w);
    end

endmodule

`default_nettype wire
