`default_nettype none

// Module: mtf_list
// Purpose: The move-to-front list, an N_LIST-entry shift-register CAM (MAS §5/§7, PRD-F2/F4/F5).
//          INIT fills it from the 256-bit used map as the ascending sequence of used byte values,
//          one used byte per cycle via a lowest-set-bit priority encoder, so init takes exactly
//          N_USED cycles (S1). A rank read is an N_LIST:1 mux; a move-to-front is a parallel
//          one-cycle shift (rank 0 <- list[r], ranks 1..r <- old 0..r-1, ranks > r unchanged).
//          DBG_DATA reads list[dbg_sel] live (0 for sel >= N_USED or before the first init).
module mtf_list #(
    parameter int N_LIST = 256                       // List capacity / byte-value domain
) (
    input  logic                     clk,            // System clock
    input  logic                     rst_n,          // Active-low synchronous reset
    // Init
    input  logic                     init_start,     // Pulse: latch used map and begin the fill
    input  logic [N_LIST-1:0]        used_map,       // Byte b present iff used_map[b]
    output logic                     init_busy_o,    // Fill in progress (s_sym.tready held 0)
    output logic [$clog2(N_LIST):0]  n_used_o,       // Number of used bytes filled (UQ.0)
    // Rank read + move-to-front (symbol side)
    input  logic [$clog2(N_LIST)-1:0] rd_rank,       // Rank to read
    output logic [7:0]               rd_byte_o,      // list[rd_rank]
    output logic [7:0]               byte0_o,        // list[0] (rank-0 byte for run expansion)
    input  logic                     mv_en,          // Perform a move-to-front this cycle
    input  logic [$clog2(N_LIST)-1:0] mv_rank,       // Rank moved to the front
    // Debug read (AXI-Lite)
    input  logic [7:0]               dbg_sel,        // Rank whose byte DBG_DATA returns
    output logic [7:0]               dbg_data_o      // list[dbg_sel] (0 if sel >= N_USED)
);

    localparam int RW = $clog2(N_LIST);              // Rank/index width (8 for N_LIST=256)
    localparam int CW = RW + 1;                      // Count width (holds N_LIST)

    logic [7:0]        lst   [N_LIST];               // List entries (byte values)
    logic [7:0]        lst_n [N_LIST];               // Next list entries
    logic [N_LIST-1:0] rem_q;                        // Used bits not yet consumed by the fill
    logic [N_LIST-1:0] rem_n;                        // Next remaining
    logic              filling_q;                    // Fill in progress
    logic              filling_n;                    // Next fill flag
    logic [CW-1:0]     fill_idx_q;                   // Next entry to write / bytes filled so far
    logic [CW-1:0]     fill_idx_n;                   // Next fill index

    // Fill source: the used map on the init_start cycle (so the first byte is written that same
    // cycle, giving an N_USED-cycle fill), the remaining bits thereafter.
    logic [N_LIST-1:0] fill_src;                     // Source of remaining used bits
    logic              fill_active;                  // A fill cycle (init_start or still filling)
    logic [CW-1:0]     fill_base;                    // Index of the byte written this cycle
    assign fill_active = init_start || filling_q;
    assign fill_src    = init_start ? used_map : rem_q;
    assign fill_base   = init_start ? {CW{1'b0}} : fill_idx_q;

    // Lowest-set-bit priority encoder over the fill source (ascending byte value).
    logic [RW-1:0]     lsb_idx;                      // Index of the lowest remaining used byte
    logic              lsb_any;                      // Any remaining used byte
    always_comb begin
        lsb_idx = {RW{1'b0}};
        lsb_any = 1'b0;
        for (int i = N_LIST - 1; i >= 0; i--) begin
            if (fill_src[i]) begin
                lsb_idx = RW'(i);
                lsb_any = 1'b1;
            end
        end
    end

    // Next-state: fill (one byte/cycle) has priority over move-to-front; they never overlap
    // because s_sym.tready is 0 during the fill.
    always_comb begin
        for (int i = 0; i < N_LIST; i++) begin
            lst_n[i] = lst[i];
        end
        rem_n      = rem_q;
        filling_n  = filling_q;
        fill_idx_n = fill_idx_q;

        if (fill_active) begin
            if (lsb_any) begin
                lst_n[fill_base[RW-1:0]] = {{(8 - RW){1'b0}}, lsb_idx};
                rem_n                    = fill_src & ~(({{(N_LIST-1){1'b0}}, 1'b1}) << lsb_idx);
                fill_idx_n               = fill_base + CW'(1);
                filling_n                = (rem_n != {N_LIST{1'b0}});
            end else begin
                rem_n      = fill_src;
                filling_n  = 1'b0;
                fill_idx_n = fill_base;
            end
        end else if (mv_en) begin
            lst_n[0] = lst[mv_rank];
            for (int i = 1; i < N_LIST; i++) begin
                if (RW'(i) <= mv_rank) begin
                    lst_n[i] = lst[i - 1];
                end else begin
                    lst_n[i] = lst[i];
                end
            end
        end

        if (!rst_n) begin
            rem_n      = {N_LIST{1'b0}};
            filling_n  = 1'b0;
            fill_idx_n = {CW{1'b0}};
        end
    end

    always_ff @(posedge clk) begin
        rem_q      <= rem_n;
        filling_q  <= filling_n;
        fill_idx_q <= fill_idx_n;
        for (int i = 0; i < N_LIST; i++) begin
            lst[i] <= lst_n[i];
        end
    end

    assign init_busy_o = fill_active;                // High on every fill cycle (init_start..last)
    assign n_used_o    = fill_idx_q;
    assign rd_byte_o   = lst[rd_rank];
    assign byte0_o     = lst[0];

    logic sel_in_range;                              // dbg_sel < N_USED
    always_comb begin
        sel_in_range = ({1'b0, dbg_sel} < {{(9 - CW){1'b0}}, fill_idx_q});
        dbg_data_o   = sel_in_range ? lst[dbg_sel] : 8'd0;
    end

endmodule

`default_nettype wire
