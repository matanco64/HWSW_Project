`default_nettype none

// Module: mtf_expand
// Purpose: Drain side (MAS §5, PRD-F7). Pops one item per completed item from item_fifo and
//          streams its bytes to the packer: an MTF-byte item is one byte in one cycle; a run
//          item RUN(n, byte0) is n copies of byte0 emitted W-at-a-time by a down-counter over
//          ceil(n/W) cycles. Byte lanes all carry the item byte (the packer's TKEEP/count picks
//          how many are live). Back-pressure (pack_ready low) stalls without loss; on flush the
//          in-flight item is discarded (a run pending at an error is dropped).
module mtf_expand #(
    parameter int W      = 8,                         // Output lanes (bytes/cycle)
    parameter int RUN_W  = 21,                         // Run width, UQ21.0
    parameter int ITEM_W = 30                          // Item width in bits
) (
    input  logic               clk,                   // System clock
    input  logic               rst_n,                 // Active-low synchronous reset
    input  logic               flush,                 // Discard the in-flight item (error/abort/doorbell)
    // item_fifo read side
    input  logic               fifo_rd_valid,         // Head item available
    input  logic [ITEM_W-1:0]  fifo_rd_data,          // Head item {is_run, n, byte}
    output logic               fifo_rd_en_o,          // Pop the head item
    // Packer input side
    input  logic               pack_ready,            // Packer can accept bytes this cycle
    output logic               out_valid_o,           // Bytes valid this cycle
    output logic [$clog2(W+1)-1:0] out_cnt_o,         // Number of valid bytes (1..W)
    output logic [W*8-1:0]     out_data_o,            // W lanes, each = the item byte
    output logic               idle_o                 // No item in flight
);

    localparam int LCW = $clog2(W + 1);               // Lane-count width

    logic             busy_q;                          // Item in flight
    logic [7:0]       byte_q;                          // Current item byte
    logic [RUN_W-1:0] rem_q;                           // Bytes remaining in the current item
    logic             busy_n;                          // Next busy
    logic [7:0]       byte_n;                          // Next byte
    logic [RUN_W-1:0] rem_n;                           // Next remaining

    // Decode the head item.
    logic             hd_is_run;                       // Head item is a run
    logic [7:0]       hd_byte;                          // Head item byte
    logic [RUN_W-1:0] hd_rem;                           // Head item byte count
    always_comb begin
        hd_byte   = fifo_rd_data[7:0];
        hd_is_run = fifo_rd_data[ITEM_W-1];
        hd_rem    = hd_is_run ? fifo_rd_data[8 +: RUN_W] : {{(RUN_W-1){1'b0}}, 1'b1};
    end

    // This-cycle byte count.
    logic [LCW-1:0]   this_cnt;                         // min(rem, W)
    logic             finishing;                        // rem <= W (item completes if accepted)
    always_comb begin
        finishing = (rem_q <= RUN_W'(W));
        this_cnt  = finishing ? rem_q[LCW-1:0] : LCW'(W);
    end

    always_comb begin
        busy_n = busy_q;
        byte_n = byte_q;
        rem_n  = rem_q;
        fifo_rd_en_o = 1'b0;

        if (!busy_q) begin
            if (fifo_rd_valid) begin
                fifo_rd_en_o = 1'b1;
                byte_n       = hd_byte;
                rem_n        = hd_rem;
                busy_n       = 1'b1;
            end
        end else if (pack_ready) begin
            if (finishing) begin
                if (fifo_rd_valid) begin
                    fifo_rd_en_o = 1'b1;               // Back-to-back: pop next item
                    byte_n       = hd_byte;
                    rem_n        = hd_rem;
                    busy_n       = 1'b1;
                end else begin
                    busy_n = 1'b0;
                end
            end else begin
                rem_n = rem_q - RUN_W'(W);
            end
        end

        if (flush) begin
            busy_n       = 1'b0;
            rem_n        = {RUN_W{1'b0}};
            fifo_rd_en_o = 1'b0;
        end
        if (!rst_n) begin
            busy_n       = 1'b0;
            byte_n       = 8'd0;
            rem_n        = {RUN_W{1'b0}};
            fifo_rd_en_o = 1'b0;
        end
    end

    always_ff @(posedge clk) begin
        busy_q <= busy_n;
        byte_q <= byte_n;
        rem_q  <= rem_n;
    end

    always_comb begin
        for (int l = 0; l < W; l++) begin
            out_data_o[l*8 +: 8] = byte_q;
        end
    end

    assign out_valid_o = busy_q;
    assign out_cnt_o   = this_cnt;
    assign idle_o      = !busy_q;

endmodule

`default_nettype wire
