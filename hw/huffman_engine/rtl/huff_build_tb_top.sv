`default_nettype none

// Module: huff_build_tb_top
// Purpose: TB-ONLY wrapper for unit.test_builder — NOT part of the synthesized design (the
//          _tb_top suffix marks it; kept in the synthesizable subset anyway). Instantiates
//          huff_builder + huff_tables wired exactly as in the design, plus two small behavioral
//          memories standing in for huff_regs' lengths window ({t[2:0], sym[8:0]} -> 5 b,
//          1-cycle registered read) and folded count bins ({t[2:0], l[4:0]} -> 9 b comb read).
//          The test loads both through the simple len_wr_*/cnt_wr_* write ports and plays
//          huff_ctrl through start_i/alphabet_i/n_tables_i/mode_deflate_i; the tables read view
//          (cur_set_i select, flat set arrays, symtab/DBG read ports) is exported as top-level
//          pins. Wiring only — no logic beyond the two stub memories.
module huff_build_tb_top (
    input  logic         clk,               // System clock
    input  logic         rst_n,             // Active-low synchronous reset
    // Build control (as huff_ctrl would drive)
    input  logic         start_i,           // 1-cycle pulse: build n_tables_i tables
    input  logic         mode_deflate_i,    // 1 = DEFLATE EOB rule
    input  logic [8:0]   alphabet_i,        // Symbols per table, UQ9.0 (1..288)
    input  logic [2:0]   n_tables_i,        // Tables to build, UQ3.0 (1..6)
    // Lengths-window stub load port (stands in for huff_regs)
    input  logic         len_wr_en_i,       // Lengths write strobe
    input  logic [11:0]  len_wr_addr_i,     // {t[2:0], sym[8:0]}
    input  logic [4:0]   len_wr_data_i,     // Code length, UQ5.0
    // Count-bins stub load port (stands in for huff_regs' folded bins)
    input  logic         cnt_wr_en_i,       // Count write strobe
    input  logic [7:0]   cnt_wr_addr_i,     // {t[2:0], l[4:0]}
    input  logic [8:0]   cnt_wr_data_i,     // count[t][l], UQ9.0
    // Tables read view (as huff_decoder would use)
    input  logic [2:0]   cur_set_i,         // Active set select
    input  logic [10:0]  symtab_rd_addr_i,  // Symtab read address (registered read)
    input  logic [10:0]  dbg_rd_addr_i,     // DBG read address (comb, 0 during FILL)
    // Builder status
    output logic         busy_o,            // Build in progress
    output logic         build_done_o,      // 1-cycle pulse: all tables built
    output logic         err_table_o,       // 1-cycle pulse: Kraft overflow, build aborted
    output logic [15:0]  build_cycles_o,    // Max per-table build cycles, UQ16.0
    // Tables read-view outputs
    output logic [419:0] limit_la_flat_o,   // Active set's 20 limit_la, UQ21.0 each
    output logic [399:0] first_code_flat_o, // Active set's 20 first_code, UQ20.0 each
    output logic [219:0] base_flat_o,       // Active set's 20 base, UQ11.0 each
    output logic [10:0]  table_base_o,      // Active set's table_base, UQ11.0
    output logic [4:0]   eob_len_o,         // Active set's EOB length (0 = never latched)
    output logic [19:0]  eob_code_o,        // Active set's EOB code, UQ20.0
    output logic [9:0]   symtab_rd_data_o,  // Symtab read data (1 cycle — C1)
    output logic [9:0]   dbg_rd_data_o      // DBG read data
);

    // ---- huff_regs stand-in: lengths window + count bins --------------------------------------
    logic [4:0]  len_mem [0:4095];  // Lengths window stub: {t, sym} -> UQ5.0
    logic [8:0]  cnt_mem [0:255];   // Count bins stub: {t, l} -> UQ9.0

    logic [11:0] lengths_addr;      // Builder lengths read address
    logic [4:0]  lengths_data;      // Registered lengths read data (1 cycle)
    logic [7:0]  counts_addr;       // Builder counts read address
    logic [8:0]  counts_data;       // Combinational counts read data

    always_ff @(posedge clk) begin
        if (len_wr_en_i) begin
            len_mem[len_wr_addr_i] <= len_wr_data_i;
        end
        lengths_data <= len_mem[lengths_addr];
    end

    always_ff @(posedge clk) begin
        if (cnt_wr_en_i) begin
            cnt_mem[cnt_wr_addr_i] <= cnt_wr_data_i;
        end
    end

    always_comb begin
        counts_data = cnt_mem[counts_addr];
    end

    // ---- builder <-> tables wiring ------------------------------------------------------------
    logic        wr_set_en;       // Set entry write strobe
    logic [2:0]  wr_set;          // Destination set
    logic [4:0]  wr_l;            // Destination length
    logic [19:0] wr_first_code;   // first_code write data
    logic [20:0] wr_limit_la;     // limit_la write data
    logic [10:0] wr_base;         // base write data
    logic        tbase_wr_en;     // table_base write strobe
    logic [10:0] tbase;           // table_base write data
    logic        eob_wr_en;       // EOB latch strobe
    logic [4:0]  eob_len_w;       // EOB length write data
    logic [19:0] eob_code_w;      // EOB code write data
    logic        eob_clr;         // Clear-all-eob strobe
    logic        symtab_wr_en;    // Symtab write strobe
    logic [10:0] symtab_wr_addr;  // Symtab write address
    logic [9:0]  symtab_wr_data;  // Symtab write data
    logic        fill_active;     // FILL pass active (DBG gate)

    logic [19:0] tb_dbg_fc;    // DBG sink (unused in this TB)
    logic [10:0] tb_dbg_base;  // DBG sink

    huff_builder u_builder (
        .clk              (clk),
        .rst_n            (rst_n),
        .stop_i(1'b0), .start_i          (start_i),
        .mode_deflate_i   (mode_deflate_i),
        .alphabet_i       (alphabet_i),
        .n_tables_i       (n_tables_i),
        .lengths_addr_o   (lengths_addr),
        .lengths_data_i   (lengths_data),
        .counts_addr_o    (counts_addr),
        .counts_data_i    (counts_data),
        .wr_set_en_o      (wr_set_en),
        .wr_set_o         (wr_set),
        .wr_l_o           (wr_l),
        .wr_first_code_o  (wr_first_code),
        .wr_limit_la_o    (wr_limit_la),
        .wr_base_o        (wr_base),
        .tbase_wr_en_o    (tbase_wr_en),
        .tbase_o          (tbase),
        .eob_wr_en_o      (eob_wr_en),
        .eob_len_o        (eob_len_w),
        .eob_code_o       (eob_code_w),
        .eob_clr_o        (eob_clr),
        .symtab_wr_en_o   (symtab_wr_en),
        .symtab_wr_addr_o (symtab_wr_addr),
        .symtab_wr_data_o (symtab_wr_data),
        .busy_o           (busy_o),
        .fill_active_o    (fill_active),
        .build_done_o     (build_done_o),
        .err_table_o      (err_table_o),
        .build_cycles_o   (build_cycles_o)
    );

    huff_tables u_tables (
        .clk               (clk),
        .rst_n             (rst_n),
        .wr_set_en_i       (wr_set_en),
        .wr_set_i          (wr_set),
        .wr_l_i            (wr_l),
        .wr_first_code_i   (wr_first_code),
        .wr_limit_la_i     (wr_limit_la),
        .wr_base_i         (wr_base),
        .tbase_wr_en_i     (tbase_wr_en),
        .tbase_i           (tbase),
        .eob_wr_en_i       (eob_wr_en),
        .eob_len_i         (eob_len_w),
        .eob_code_i        (eob_code_w),
        .eob_clr_i         (eob_clr),
        .symtab_wr_en_i    (symtab_wr_en),
        .symtab_wr_addr_i  (symtab_wr_addr),
        .symtab_wr_data_i  (symtab_wr_data),
        .fill_active_i     (fill_active),
        .cur_set_i         (cur_set_i),
        .limit_la_flat_o   (limit_la_flat_o),
        .first_code_flat_o (first_code_flat_o),
        .base_flat_o       (base_flat_o),
        .table_base_o      (table_base_o),
        .eob_len_o         (eob_len_o),
        .eob_code_o        (eob_code_o),
        .symtab_rd_addr_i  (symtab_rd_addr_i),
        .symtab_rd_data_o  (symtab_rd_data_o),
        .dbg_set_i(3'd0), .dbg_l_i(5'd0), .dbg_first_code_o(tb_dbg_fc), .dbg_base_o(tb_dbg_base), .dbg_rd_addr_i     (dbg_rd_addr_i),
        .dbg_rd_data_o     (dbg_rd_data_o)
    );

    logic unused_tb2;              // DBG sink reduction
    assign unused_tb2 = (^tb_dbg_fc) ^ (^tb_dbg_base);

endmodule

`default_nettype wire
