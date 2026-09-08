`default_nettype none

// Module: huff_tables
// Purpose: Canonical-table storage + read view (uArch section 5, rtl_contracts.md tables).
//          Storage: shared symtab 1,728 x 10 b {valid, sym[8:0]} (1W from the builder / 1R
//          registered for the decoder — C1; plus a DBG combinational read valid outside FILL),
//          and six per-set register groups: 20 x {limit_la UQ21.0, first_code UQ20.0,
//          base UQ11.0} + table_base UQ11.0 + eob_len UQ5.0 / eob_code UQ20.0.
//          table_base[t] = t * 288 is written by the builder (fixed stride, see huff_builder).
//          Read view: cur_set_i selects the active set; the 20 per-length entries are exported
//          flat (entry l occupies bits [(l-1)*W +: W]) for the decoder's parallel compares.
//          eob_clr_i clears ALL six eob_len latches in one cycle (PREP-entry clear, review N2).
//          Yosys 0.68 subset: 1-D unpacked memories only, packed vectors for the small per-set
//          scalars, no struct arrays, declare-before-use.
module huff_tables (
    input  logic         clk,               // System clock
    input  logic         rst_n,             // Active-low synchronous reset
    // Set write port (huff_builder)
    input  logic         wr_set_en_i,       // Write entry wr_l_i of set wr_set_i
    input  logic [2:0]   wr_set_i,          // Destination set index (0..5)
    input  logic [4:0]   wr_l_i,            // Destination length (1..20)
    input  logic [19:0]  wr_first_code_i,   // first_code[l], UQ20.0
    input  logic [20:0]  wr_limit_la_i,     // limit_la[l], UQ21.0
    input  logic [10:0]  wr_base_i,         // base[l], UQ11.0
    input  logic         tbase_wr_en_i,     // Write table_base of set wr_set_i
    input  logic [10:0]  tbase_i,           // table_base value, UQ11.0
    input  logic         eob_wr_en_i,       // Latch EOB (len, code) into set wr_set_i
    input  logic [4:0]   eob_len_i,         // EOB length, UQ5.0
    input  logic [19:0]  eob_code_i,        // EOB canonical code, UQ20.0
    input  logic         eob_clr_i,         // Clear ALL six eob_len latches
    // Symtab write port (huff_builder)
    input  logic         symtab_wr_en_i,    // Symtab write strobe
    input  logic [10:0]  symtab_wr_addr_i,  // Symtab write address (0..1727)
    input  logic [9:0]   symtab_wr_data_i,  // {valid, sym[8:0]}
    input  logic         fill_active_i,     // FILL pass active: DBG read returns 0
    // Active-set read view (huff_decoder / TB)
    input  logic [2:0]   cur_set_i,         // Active set select
    output logic [419:0] limit_la_flat_o,   // 20 x limit_la UQ21.0, entry l at [(l-1)*21 +: 21]
    output logic [399:0] first_code_flat_o, // 20 x first_code UQ20.0
    output logic [219:0] base_flat_o,       // 20 x base UQ11.0
    output logic [10:0]  table_base_o,      // Active set's table_base, UQ11.0
    output logic [4:0]   eob_len_o,         // Active set's EOB length (0 = never latched)
    output logic [19:0]  eob_code_o,        // Active set's EOB code
    // Symtab read ports
    input  logic [10:0]  symtab_rd_addr_i,  // Decoder read address
    output logic [9:0]   symtab_rd_data_o,  // Decoder read data (registered, 1 cycle — C1)
    input  logic [10:0]  dbg_rd_addr_i,     // DBG read address
    output logic [9:0]   dbg_rd_data_o,     // DBG read data (combinational, 0 during FILL)
    // DBG set-array reads (review R10: MAS 0x114 kinds 1/2)
    input  logic [2:0]   dbg_set_i,         // DBG table select
    input  logic [4:0]   dbg_l_i,           // DBG length index (1..20)
    output logic [19:0]  dbg_first_code_o,  // first_code[dbg_set][dbg_l]
    output logic [10:0]  dbg_base_o         // base[dbg_set][dbg_l]
);

    localparam int unsigned SET_ENTRIES  = 20;    // Lengths 1..20 per set
    localparam int unsigned SYMTAB_DEPTH = 1728;  // 6 sets x 288 symbols

    // ---- per-set entry storage: 6 x 20 entries, indexed set*20 + (l-1) ------------------------
    logic [20:0] limit_mem [0:119];   // limit_la entries, UQ21.0
    logic [19:0] first_mem [0:119];   // first_code entries, UQ20.0
    logic [10:0] base_mem  [0:119];   // base entries, UQ11.0
    logic [9:0]  symtab_mem [0:SYMTAB_DEPTH-1];  // {valid, sym[8:0]} entries

    // Small per-set scalars as packed vectors (Yosys-friendly, resettable)
    logic [65:0]  tbase_r;      // 6 x table_base UQ11.0
    logic [65:0]  tbase_next;   // Next table_base vector
    logic [29:0]  eob_len_r;    // 6 x eob_len UQ5.0
    logic [29:0]  eob_len_next; // Next eob_len vector
    logic [119:0] eob_code_r;   // 6 x eob_code UQ20.0
    logic [119:0] eob_code_next;// Next eob_code vector

    logic [6:0]  wr_idx;        // Entry write index: wr_set*20 + wr_l - 1
    logic [6:0]  wr_set_ext;    // wr_set_i zero-extended for offset math
    logic [4:0]  wr_set_x5;     // wr_set_i * 5 (eob_len vector offset)
    logic [6:0]  view_base;     // Read-view entry offset: cur_set*20
    logic [6:0]  cur_set_ext;   // cur_set_i zero-extended for offset math
    logic [4:0]  cur_set_x5;    // cur_set_i * 5 (eob_len vector offset)

    always_comb begin
        wr_set_ext  = {4'b0, wr_set_i};
        wr_idx      = wr_set_ext * 7'd20 + {2'b0, wr_l_i} - 7'd1;
        wr_set_x5   = {2'b0, wr_set_i} * 5'd5;
        cur_set_ext = {4'b0, cur_set_i};
        view_base   = cur_set_ext * 7'd20;
        cur_set_x5  = {2'b0, cur_set_i} * 5'd5;
    end

    // ---- set entry writes (memory-inference pattern) ------------------------------------------
    always_ff @(posedge clk) begin
        if (wr_set_en_i) begin
            limit_mem[wr_idx] <= wr_limit_la_i;
            first_mem[wr_idx] <= wr_first_code_i;
            base_mem[wr_idx]  <= wr_base_i;
        end
    end

    // ---- per-set scalars ----------------------------------------------------------------------
    always_comb begin
        tbase_next    = tbase_r;
        eob_len_next  = eob_len_r;
        eob_code_next = eob_code_r;
        if (eob_clr_i) begin
            eob_len_next = 30'd0;   // PREP-entry clear: all six latches at once
        end
        if (tbase_wr_en_i) begin
            tbase_next[wr_set_ext * 7'd11 +: 11] = tbase_i;
        end
        if (eob_wr_en_i) begin
            eob_len_next[wr_set_x5 +: 5]           = eob_len_i;
            eob_code_next[wr_set_ext * 7'd20 +: 20] = eob_code_i;
        end
        if (!rst_n) begin
            tbase_next    = 66'd0;
            eob_len_next  = 30'd0;
            eob_code_next = 120'd0;
        end
    end

    always_ff @(posedge clk) begin
        tbase_r    <= tbase_next;
        eob_len_r  <= eob_len_next;
        eob_code_r <= eob_code_next;
    end

    // ---- symtab: 1W + registered 1R (C1) ------------------------------------------------------
    always_ff @(posedge clk) begin
        if (symtab_wr_en_i) begin
            symtab_mem[symtab_wr_addr_i] <= symtab_wr_data_i;
        end
        symtab_rd_data_o <= symtab_mem[symtab_rd_addr_i];
    end

    // DBG combinational read: valid outside FILL only (uArch section 5 / MAS amendment)
    always_comb begin
        if (dbg_l_i >= 5'd1 && dbg_l_i <= 5'd20) begin
            dbg_first_code_o = first_mem[{4'b0, dbg_set_i} * 7'd20 + {2'b0, dbg_l_i} - 7'd1];
            dbg_base_o       = base_mem[{4'b0, dbg_set_i} * 7'd20 + {2'b0, dbg_l_i} - 7'd1];
        end else begin
            dbg_first_code_o = 20'd0;
            dbg_base_o       = 11'd0;
        end
        if (fill_active_i || (dbg_rd_addr_i >= 11'(SYMTAB_DEPTH))) begin
            dbg_rd_data_o = 10'd0;
        end else begin
            dbg_rd_data_o = symtab_mem[dbg_rd_addr_i];
        end
    end

    // ---- active-set read view (own comb block: keep the wide view out of guarded processes) ---
    always_comb begin
        for (int unsigned i = 0; i < SET_ENTRIES; i++) begin
            limit_la_flat_o[i*21 +: 21]   = limit_mem[view_base + 7'(i)];
            first_code_flat_o[i*20 +: 20] = first_mem[view_base + 7'(i)];
            base_flat_o[i*11 +: 11]       = base_mem[view_base + 7'(i)];
        end
    end

    always_comb begin
        table_base_o = tbase_r[cur_set_ext * 7'd11 +: 11];
        eob_len_o    = eob_len_r[cur_set_x5 +: 5];
        eob_code_o   = eob_code_r[cur_set_ext * 7'd20 +: 20];
    end

endmodule

`default_nettype wire
