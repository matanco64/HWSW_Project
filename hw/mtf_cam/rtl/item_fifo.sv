`default_nettype none

// Module: item_fifo
// Purpose: Item queue decoupling the symbol side from the drain side (PRD-F7). Depth D items,
//          each ITEM_W bits (an opaque {is_run, n, byte} record packed by the top). It has a
//          2-wide write port (M2): a single symbol can enqueue up to two items in one cycle
//          (a terminating run item followed by that symbol's MTF-byte item). Read is 1-wide.
//          The full-gate reserves two slots: can_wr2_o rises only when >= 2 slots are free, so
//          the symbol side (which offers <= 2 items/cycle) never overflows. flush clears it.
module item_fifo #(
    parameter int D      = 8,                        // Depth in items (>= 2)
    parameter int ITEM_W = 30                         // Item width in bits
) (
    input  logic               clk,                  // System clock
    input  logic               rst_n,                // Active-low synchronous reset
    input  logic               flush,                // Drop all contents (error/abort/doorbell)
    // 2-wide write port: b is the second item and requires a (wr_b_en -> wr_a_en)
    input  logic               wr_a_en,              // Write item A
    input  logic [ITEM_W-1:0]  wr_a_data,            // Item A payload
    input  logic               wr_b_en,              // Write item B (second)
    input  logic [ITEM_W-1:0]  wr_b_data,            // Item B payload
    output logic               can_wr2_o,            // >= 2 free slots (symbol side may accept a symbol)
    // 1-wide read port
    input  logic               rd_en,                // Pop the head item this cycle
    output logic               rd_valid_o,           // Head item present (FIFO not empty)
    output logic [ITEM_W-1:0]  rd_data_o,            // Head item payload
    output logic               empty_o               // FIFO empty (no items, used by drain-complete)
);

    localparam int PW = (D <= 1) ? 1 : $clog2(D);    // Pointer width
    localparam int CW = $clog2(D + 1);               // Count width (0..D)

    logic [ITEM_W-1:0] mem [D];                       // Item storage
    logic [PW-1:0]     wptr_q;                        // Write pointer
    logic [PW-1:0]     rptr_q;                        // Read pointer
    logic [CW-1:0]     cnt_q;                         // Occupancy (0..D)

    logic [PW-1:0]     wptr_n;                        // Next write pointer
    logic [PW-1:0]     rptr_n;                        // Next read pointer
    logic [CW-1:0]     cnt_n;                         // Next occupancy

    logic              do_wa;                         // Effective write A
    logic              do_wb;                         // Effective write B
    logic              do_rd;                         // Effective read
    logic [1:0]        n_wr;                          // Number of writes this cycle (0..2)
    logic [PW-1:0]     wa_addr;                        // Address for write A
    logic [PW-1:0]     wb_addr;                        // Address for write B (wptr + 1)

    always_comb begin
        do_wa = wr_a_en;
        do_wb = wr_b_en;                              // Caller guarantees wr_b_en -> wr_a_en
        do_rd = rd_en && (cnt_q != {CW{1'b0}});

        n_wr    = {1'b0, do_wa} + {1'b0, do_wb};
        wa_addr = wptr_q;
        wb_addr = (wptr_q == PW'(D - 1)) ? PW'(0) : (wptr_q + PW'(1));

        // Next pointers/count
        wptr_n = wptr_q;
        if (do_wa) begin
            wptr_n = (wa_addr == PW'(D - 1)) ? PW'(0) : (wa_addr + PW'(1));
        end
        if (do_wb) begin
            wptr_n = (wb_addr == PW'(D - 1)) ? PW'(0) : (wb_addr + PW'(1));
        end

        rptr_n = rptr_q;
        if (do_rd) begin
            rptr_n = (rptr_q == PW'(D - 1)) ? PW'(0) : (rptr_q + PW'(1));
        end

        cnt_n = cnt_q + {{(CW-2){1'b0}}, n_wr} - {{(CW-1){1'b0}}, do_rd};

        if (flush) begin
            wptr_n = PW'(0);
            rptr_n = PW'(0);
            cnt_n  = {CW{1'b0}};
        end
        if (!rst_n) begin
            wptr_n = PW'(0);
            rptr_n = PW'(0);
            cnt_n  = {CW{1'b0}};
        end
    end

    always_ff @(posedge clk) begin
        wptr_q <= wptr_n;
        rptr_q <= rptr_n;
        cnt_q  <= cnt_n;
        if (do_wa) begin
            mem[wa_addr] <= wr_a_data;
        end
        if (do_wb) begin
            mem[wb_addr] <= wr_b_data;
        end
    end

    assign rd_data_o  = mem[rptr_q];
    assign rd_valid_o = (cnt_q != {CW{1'b0}});
    assign empty_o    = (cnt_q == {CW{1'b0}});
    assign can_wr2_o  = (cnt_q <= CW'(D - 2));         // >= 2 free slots

endmodule

`default_nettype wire
