`default_nettype none

// Module: huff_regs
// Purpose: Register decoder for huffman_engine behind axi_lite_if (MAS §4 incl. the 2026-09-08
//          amendments). Implements the ADR-0005 header (ID/VERSION/CTRL/STATUS/IRQ), live
//          counters, pending/latched configuration (MODE/START_BIT/ALPHABET/N_TABLES/
//          SYMBOL_LIMIT), DBG_SEL/DBG_DATA, and the lengths window at per-table 48-word
//          strides (6 x 5-bit fields per word, single stored copy) with folded count bins
//          maintained by RMW on every full-strobe lengths write (uArch §3.2): decrement the 6
//          old fields' bins, increment the 6 new; a field > MAXLEN feeds the per-table invalid
//          bin. Doorbell-time checks: ERR_PARAM (MAS §4 F9) else ERR_TABLE (nonzero invalid
//          bin of a used table; DEFLATE also bins 16..20). BRESP held during the decision
//          (ADR-0005). Builder read ports: lengths_rd ({t, sym} -> 5 b, 1-cycle registered),
//          counts_rd ((t, l) -> 9 b, combinational).
//          Yosys 0.68 subset: no unpacked localparam arrays, no fn-call bit-selects, no struct
//          arrays; declare before use (Icarus).
module huff_regs #(
    parameter logic [31:0] VERSION = 32'd0             // git short SHA (synthesis parameter)
) (
    input  logic        clk,                           // System clock
    input  logic        rst_n,                         // Active-low synchronous reset
    // Register bus (axi_lite_if)
    input  logic        req_wr_i,                      // Write pulse
    input  logic [9:0]  wr_addr_i,                     // Write word address
    input  logic [31:0] wr_data_i,                     // Write data
    input  logic [3:0]  wr_strb_i,                     // Byte strobes
    output logic        wr_err_o,                      // SLVERR (cycle after req_wr_i)
    output logic        wr_resp_hold_o,                // Hold BRESP during doorbell decision
    input  logic        req_rd_i,                      // Read pulse
    input  logic [9:0]  rd_addr_i,                     // Read word address
    output logic [31:0] rd_data_o,                     // Read data (cycle after req_rd_i)
    output logic        rd_err_o,                      // SLVERR
    // Control / status exchange with the core FSM
    output logic        doorbell_o,                    // Accepted-doorbell pulse (config latched now)
    output logic        abort_o,                       // Abort request pulse
    input  logic        busy_i,                        // Core FSM busy
    input  logic        done_set_i,                    // DONE pulse
    input  logic        aborted_set_i,                 // ABORTED pulse
    input  logic [6:0]  err_set_i,                     // Error pulses -> STATUS bits 15:9
                                                       // ([0] ERR_PARAM .. [6] ERR_UNDERRUN)
    // Live counters (core FSM / datapath)
    input  logic [63:0] cycles_i,                      // Busy-cycle counter, UQ64.0
    input  logic [31:0] symbols_i,                     // m_sym beats handshaken, UQ32.0
    input  logic [31:0] bits_i,                        // Bits consumed since START_BIT, UQ32.0
    input  logic [15:0] build_cycles_i,                // Longest single table build, UQ16.0
    input  logic [7:0]  overfetch_i,                   // Over-fetched s_bits beats, UQ8.0
    // Debug select / data (huff_tables provides the selected word)
    input  logic [31:0] dbg_data_i,                    // Selected built-table entry (live)
    output logic [2:0]  dbg_table_o,                   // DBG_SEL table field (live)
    output logic [1:0]  dbg_kind_o,                    // DBG_SEL kind field (live)
    output logic [8:0]  dbg_index_o,                   // DBG_SEL index field (live)
    // Latched configuration (valid from doorbell_o until the next one)
    output logic        cfg_mode_o,                    // 0 = bzip2, 1 = DEFLATE
    output logic [31:0] cfg_start_bit_o,               // First code bit, UQ32.0
    output logic [8:0]  cfg_alphabet_o,                // Symbols per table, UQ9.0
    output logic [2:0]  cfg_n_tables_o,                // Tables in use, UQ3.0
    output logic [31:0] cfg_symbol_limit_o,            // Symbol beat limit, UQ32.0
    // Builder read ports
    input  logic [11:0] lengths_rd_addr_i,             // {table[2:0], sym[8:0]}
    output logic [4:0]  lengths_rd_data_o,             // Length of (t, sym), UQ5.0 (1-cycle)
    input  logic [2:0]  counts_rd_table_i,             // Count-bin table select
    input  logic [4:0]  counts_rd_len_i,               // Count-bin length select (1..20)
    output logic [8:0]  counts_rd_data_o,              // count[t][l], UQ9.0 (combinational)
    // Interrupt
    output logic        irq_o                          // Level IRQ (registered)
);

    localparam logic [31:0] ID_VALUE = 32'h4855_4631;  // ASCII "HUF1"
    localparam int          N_LEN_W  = 288;            // Lengths-window words (6 tables x 48)
    localparam int          N_BINS   = 120;            // Count bins (6 tables x 20 lengths)
    localparam logic [4:0]  MAXLEN   = 5'd20;          // Longest legal code length (bzip2)

    // STATUS sticky bit positions (MAS §4)
    localparam int B_DONE = 1;                         // DONE
    localparam int B_ABRT = 2;                         // ABORTED
    localparam int B_EBSY = 8;                         // ERR_BUSY
    localparam int B_EPRM = 9;                         // ERR_PARAM
    localparam int B_ETBL = 10;                        // ERR_TABLE

    // ---- storage -------------------------------------------------------------------------------
    logic        mode_pend;                            // Pending MODE
    logic [31:0] start_bit_pend;                       // Pending START_BIT
    logic [8:0]  alphabet_pend;                        // Pending ALPHABET
    logic [2:0]  n_tables_pend;                        // Pending N_TABLES
    logic [31:0] sym_limit_pend;                       // Pending SYMBOL_LIMIT
    logic        mode_l;                               // Latched MODE
    logic [31:0] start_bit_l;                          // Latched START_BIT
    logic [8:0]  alphabet_l;                           // Latched ALPHABET
    logic [2:0]  n_tables_l;                           // Latched N_TABLES
    logic [31:0] sym_limit_l;                          // Latched SYMBOL_LIMIT
    logic [2:0]  dbg_table;                            // DBG_SEL table (live, writable while BUSY)
    logic [1:0]  dbg_kind;                             // DBG_SEL kind
    logic [8:0]  dbg_index;                            // DBG_SEL index
    logic [29:0] len_words [N_LEN_W];                  // Lengths window (6 x UQ5.0 per word)
    logic [8:0]  cnt [N_BINS];                         // Folded count bins, UQ9.0 (t*20 + l-1)
    logic [8:0]  inv_cnt [6];                          // Per-table invalid bins (field > MAXLEN)
    logic [15:0] sticky;                               // STATUS sticky bits [15:1] (bit 0 unused)
    logic [15:1] irq_en;                               // IRQ_EN mask
    logic        irq_q;                                // Registered IRQ
    logic        db_pending;                           // Doorbell decision window (this cycle)
    logic        db_hold;                              // BRESP hold flag

    // ---- ERR_PARAM (combinational over pending config, MAS §4 F9) ------------------------------
    logic        err_param;                            // Doorbell rejection: parameters
    always_comb begin
        err_param = 1'b0;
        if (sym_limit_pend == 32'd0 || sym_limit_pend > 32'h0800_0000) begin
            err_param = 1'b1;                          // SYMBOL_LIMIT outside 1..2^27
        end
        if (mode_pend) begin                           // DEFLATE
            if (n_tables_pend != 3'd2) begin
                err_param = 1'b1;
            end
            if (alphabet_pend < 9'd257 || alphabet_pend > 9'd288) begin
                err_param = 1'b1;
            end
        end else begin                                 // bzip2
            if (n_tables_pend == 3'd0 || n_tables_pend > 3'd6) begin
                err_param = 1'b1;
            end
            if (alphabet_pend < 9'd3 || alphabet_pend > 9'd288) begin
                err_param = 1'b1;
            end
        end
    end

    // ---- ERR_TABLE at the doorbell (folded bins of used tables, uArch §3.2) --------------------
    logic        err_table_db;                         // Doorbell rejection: table lengths
    always_comb begin
        err_table_db = 1'b0;
        for (int t = 0; t < 6; t++) begin
            if (t[2:0] < n_tables_pend) begin
                if (inv_cnt[t] != 9'd0) begin
                    err_table_db = 1'b1;               // Length > MAXLEN in a used table
                end
                if (mode_pend) begin                   // DEFLATE: MAXLEN_eff = 15
                    for (int l = 16; l <= 20; l++) begin
                        if (cnt[t*20 + l - 1] != 9'd0) begin
                            err_table_db = 1'b1;
                        end
                    end
                end
            end
        end
    end

    // ---- address decode ------------------------------------------------------------------------
    // Word address map (byte offset / 4): see MAS §4.
    function automatic logic addr_mapped(input logic [9:0] a);
        logic m;
        m = 1'b0;
        if (a <= 10'h005) begin
            m = 1'b1;                                  // 0x000-0x014 header
        end
        if (a >= 10'h006 && a <= 10'h00F) begin
            m = 1'b1;                                  // 0x018-0x03C reserved
        end
        if (a >= 10'h010 && a <= 10'h015) begin
            m = 1'b1;                                  // 0x040-0x054 counters
        end
        if (a >= 10'h016 && a <= 10'h03F) begin
            m = 1'b1;                                  // 0x058-0x0FC reserved
        end
        if (a >= 10'h040 && a <= 10'h046) begin
            m = 1'b1;                                  // 0x100-0x118 config + DBG
        end
        if (a >= 10'h047 && a <= 10'h0FF) begin
            m = 1'b1;                                  // 0x11C-0x3FC reserved
        end
        if (a >= 10'h100 && a <= 10'h21F) begin
            m = 1'b1;                                  // 0x400-0x87C lengths window
        end
        addr_mapped = m;                               // 0x880-0xFFC unmapped -> SLVERR
    endfunction

    logic        wr_len_hit;                           // Write targets a lengths-window word
    // verilator lint_off UNUSEDSIGNAL
    logic [9:0]  wr_len_off;                           // wr_addr - 0x100 (bit 9 unused: range-checked)
    logic [8:0]  wr_len_tbl9;                          // idx / 48 (bits 8:3 unused: quotient <= 5)
    // verilator lint_on UNUSEDSIGNAL
    logic [8:0]  wr_len_idx;                           // Window word index 0..287
    logic [2:0]  wr_len_tbl;                           // Addressed table 0..5
    logic [29:0] wr_len_old;                           // Stored word being replaced (RMW read)
    logic [6:0]  cnt_wr_base;                          // First bin index of the addressed table
    always_comb begin
        wr_len_off  = wr_addr_i - 10'h100;
        wr_len_idx  = wr_len_off[8:0];
        wr_len_hit  = (wr_addr_i >= 10'h100) && (wr_addr_i <= 10'h21F);
        wr_len_tbl9 = wr_len_idx / 9'd48;
        wr_len_tbl  = wr_len_tbl9[2:0];
        wr_len_old  = len_words[wr_len_idx];
        cnt_wr_base = {4'd0, wr_len_tbl} * 7'd20;
    end

    // Read-side lengths-window offset (same map as the write side)
    // verilator lint_off UNUSEDSIGNAL
    logic [9:0]  rd_len_off;                           // rd_addr - 0x100 (bit 9 unused: range-checked)
    // verilator lint_on UNUSEDSIGNAL
    logic [8:0]  rd_len_idx;                           // Window word index 0..287
    always_comb begin
        rd_len_off = rd_addr_i - 10'h100;
        rd_len_idx = rd_len_off[8:0];
    end

    logic        cfg_write;                            // Write to a latched-class config register
    always_comb begin
        cfg_write = wr_len_hit
                    || (wr_addr_i >= 10'h040 && wr_addr_i <= 10'h044);
    end

    // ---- write path ----------------------------------------------------------------------------
    function automatic logic [31:0] apply_strb(input logic [31:0] old, input logic [31:0] neu,
                                               input logic [3:0] strb);
        logic [31:0] r;
        r = old;
        for (int b = 0; b < 4; b++) begin
            if (strb[b]) begin
                r[b*8 +: 8] = neu[b*8 +: 8];
            end
        end
        apply_strb = r;
    endfunction

    // Next-state
    logic        mode_pend_n;
    logic [31:0] start_bit_pend_n;
    logic [8:0]  alphabet_pend_n;
    logic [2:0]  n_tables_pend_n;
    logic [31:0] sym_limit_pend_n;
    logic        mode_l_n;
    logic [31:0] start_bit_l_n;
    logic [8:0]  alphabet_l_n;
    logic [2:0]  n_tables_l_n;
    logic [31:0] sym_limit_l_n;
    logic [2:0]  dbg_table_n;
    logic [1:0]  dbg_kind_n;
    logic [8:0]  dbg_index_n;
    logic [29:0] len_words_n [N_LEN_W];
    logic [8:0]  cnt_n [N_BINS];
    logic [8:0]  inv_cnt_n [6];
    logic [15:0] sticky_n;
    logic [15:1] irq_en_n;
    logic        irq_n;
    logic        db_pending_n;
    logic        db_hold_n;
    logic        doorbell_n;
    logic        abort_n;
    logic        wr_err_n;
    logic [31:0] rd_data_n;
    logic        rd_err_n;
    // verilator lint_off UNUSEDSIGNAL
    // Reserved bits of the staged 32-bit write word are RAZ/WI (MAS §4); Yosys: no fn-call
    // bit-selects, so apply_strb results land in full-width temporaries first.
    logic [31:0] mode_tmp;                             // apply_strb temp (bit 0 used)
    logic [31:0] alpha_tmp;                            // apply_strb temp (bits 8:0 used)
    logic [31:0] ntab_tmp;                             // apply_strb temp (bits 2:0 used)
    logic [31:0] dbg_tmp;                              // apply_strb temp (bits 16:8,5:4,2:0 used)
    logic [31:0] w1c_tmp;                              // apply_strb temp (bits 15:1 used)
    logic [31:0] irqen_tmp;                            // apply_strb temp (bits 15:1 used)
    // verilator lint_on UNUSEDSIGNAL
    logic [3:0]  inc_c;                                // Fields of the new word equal to l, UQ4.0
    logic [3:0]  dec_c;                                // Fields of the old word equal to l, UQ4.0

    always_comb begin
        mode_tmp  = 32'd0;
        alpha_tmp = 32'd0;
        ntab_tmp  = 32'd0;
        dbg_tmp   = 32'd0;
        w1c_tmp   = 32'd0;
        irqen_tmp = 32'd0;
        inc_c     = 4'd0;
        dec_c     = 4'd0;
        mode_pend_n      = mode_pend;
        start_bit_pend_n = start_bit_pend;
        alphabet_pend_n  = alphabet_pend;
        n_tables_pend_n  = n_tables_pend;
        sym_limit_pend_n = sym_limit_pend;
        mode_l_n      = mode_l;
        start_bit_l_n = start_bit_l;
        alphabet_l_n  = alphabet_l;
        n_tables_l_n  = n_tables_l;
        sym_limit_l_n = sym_limit_l;
        dbg_table_n   = dbg_table;
        dbg_kind_n    = dbg_kind;
        dbg_index_n   = dbg_index;
        for (int w = 0; w < N_LEN_W; w++) begin
            len_words_n[w] = len_words[w];
        end
        for (int c = 0; c < N_BINS; c++) begin
            cnt_n[c] = cnt[c];
        end
        for (int t = 0; t < 6; t++) begin
            inv_cnt_n[t] = inv_cnt[t];
        end
        sticky_n     = sticky;
        irq_en_n     = irq_en;
        db_pending_n = 1'b0;
        db_hold_n    = db_hold;
        doorbell_n   = 1'b0;
        abort_n      = 1'b0;
        wr_err_n     = 1'b0;
        rd_data_n    = 32'd0;
        rd_err_n     = 1'b0;

        // sticky set inputs from the core FSM
        if (done_set_i) begin
            sticky_n[B_DONE] = 1'b1;
        end
        if (aborted_set_i) begin
            sticky_n[B_ABRT] = 1'b1;
        end
        for (int k = 0; k < 7; k++) begin
            if (err_set_i[k]) begin
                sticky_n[B_EPRM + k] = 1'b1;           // STATUS bits 15:9 (MAS §4)
            end
        end

        // ---- write decode ----
        if (req_wr_i) begin
            if (!addr_mapped(wr_addr_i)) begin
                wr_err_n = 1'b1;
            end else if (cfg_write) begin
                if (busy_i) begin
                    sticky_n[B_EBSY] = 1'b1;           // ignored + ERR_BUSY (MAS §4)
                end else begin
                    if (wr_addr_i == 10'h040) begin    // MODE
                        mode_tmp = apply_strb({31'd0, mode_pend}, wr_data_i, wr_strb_i);
                        mode_pend_n = mode_tmp[0];
                    end
                    if (wr_addr_i == 10'h041) begin    // START_BIT
                        start_bit_pend_n = apply_strb(start_bit_pend, wr_data_i, wr_strb_i);
                    end
                    if (wr_addr_i == 10'h042) begin    // ALPHABET
                        alpha_tmp = apply_strb({23'd0, alphabet_pend}, wr_data_i, wr_strb_i);
                        alphabet_pend_n = alpha_tmp[8:0];
                    end
                    if (wr_addr_i == 10'h043) begin    // N_TABLES
                        ntab_tmp = apply_strb({29'd0, n_tables_pend}, wr_data_i, wr_strb_i);
                        n_tables_pend_n = ntab_tmp[2:0];
                    end
                    if (wr_addr_i == 10'h044) begin    // SYMBOL_LIMIT
                        sym_limit_pend_n = apply_strb(sym_limit_pend, wr_data_i, wr_strb_i);
                    end
                    // Lengths window: full-strobe writes only (MAS amendment 2026-09-08 --
                    // wstrb != 4'hF ignored whole); RMW the folded count bins (uArch §3.2).
                    if (wr_len_hit && wr_strb_i == 4'hF) begin
                        len_words_n[wr_len_idx] = wr_data_i[29:0];
                        for (int l = 1; l <= 20; l++) begin
                            inc_c = 4'd0;
                            dec_c = 4'd0;
                            for (int f = 0; f < 6; f++) begin
                                if (wr_data_i[f*5 +: 5] == l[4:0]) begin
                                    inc_c = inc_c + 4'd1;
                                end
                                if (wr_len_old[f*5 +: 5] == l[4:0]) begin
                                    dec_c = dec_c + 4'd1;
                                end
                            end
                            cnt_n[cnt_wr_base + l[6:0] - 7'd1] =
                                cnt[cnt_wr_base + l[6:0] - 7'd1]
                                + {5'd0, inc_c} - {5'd0, dec_c};
                        end
                        inc_c = 4'd0;
                        dec_c = 4'd0;
                        for (int f = 0; f < 6; f++) begin
                            if (wr_data_i[f*5 +: 5] > MAXLEN) begin
                                inc_c = inc_c + 4'd1;
                            end
                            if (wr_len_old[f*5 +: 5] > MAXLEN) begin
                                dec_c = dec_c + 4'd1;
                            end
                        end
                        inv_cnt_n[wr_len_tbl] = inv_cnt[wr_len_tbl]
                                                + {5'd0, inc_c} - {5'd0, dec_c};
                    end
                end
            end else begin
                // header / writable-while-BUSY registers
                if (wr_addr_i == 10'h002 && wr_strb_i[0]) begin   // CTRL (WP; byte 0 strobed)
                    if (wr_data_i[1]) begin
                        abort_n = 1'b1;                // ABORT wins over DOORBELL (MAS §4)
                        if (wr_data_i[0] && busy_i) begin
                            sticky_n[B_EBSY] = 1'b1;   // the doorbell half was ignored (MAS §8)
                        end
                    end else if (wr_data_i[0]) begin
                        if (busy_i) begin
                            sticky_n[B_EBSY] = 1'b1;
                        end else begin
                            db_pending_n = 1'b1;       // decide next cycle (BRESP held)
                            db_hold_n    = 1'b1;
                        end
                    end
                end
                if (wr_addr_i == 10'h003) begin        // STATUS W1C
                    w1c_tmp = apply_strb(32'd0, wr_data_i, wr_strb_i);
                    sticky_n = sticky_n & ~w1c_tmp[15:0];
                end
                if (wr_addr_i == 10'h004) begin        // IRQ_EN (writable while BUSY)
                    irqen_tmp = apply_strb({16'd0, irq_en, 1'b0}, wr_data_i, wr_strb_i);
                    irq_en_n = irqen_tmp[15:1];
                end
                if (wr_addr_i == 10'h045) begin        // DBG_SEL (writable while BUSY)
                    dbg_tmp = apply_strb({15'd0, dbg_index, 2'b00, dbg_kind, 1'b0, dbg_table},
                                         wr_data_i, wr_strb_i);
                    dbg_table_n = dbg_tmp[2:0];
                    dbg_kind_n  = dbg_tmp[5:4];
                    dbg_index_n = dbg_tmp[16:8];
                end
                // ID, VERSION, counters, IRQ_STATUS, DBG_DATA, reserved: write ignored, OKAY
            end
        end

        // ---- doorbell decision (cycle after the CTRL write; BRESP held meanwhile) ----
        if (db_pending) begin
            db_hold_n = 1'b0;
            if (err_param) begin
                sticky_n[B_EPRM] = 1'b1;               // rejected: parameters (MAS §8)
            end else if (err_table_db) begin
                sticky_n[B_ETBL] = 1'b1;               // rejected: length > MAXLEN of the mode
            end else begin
                doorbell_n    = 1'b1;
                mode_l_n      = mode_pend;
                start_bit_l_n = start_bit_pend;
                alphabet_l_n  = alphabet_pend;
                n_tables_l_n  = n_tables_pend;
                sym_limit_l_n = sym_limit_pend;
            end
        end

        // ---- read decode ----
        if (req_rd_i) begin
            if (!addr_mapped(rd_addr_i)) begin
                rd_err_n = 1'b1;
            end else begin
                case (rd_addr_i)
                    10'h000: rd_data_n = ID_VALUE;
                    10'h001: rd_data_n = VERSION;
                    10'h002: rd_data_n = 32'd0;        // CTRL reads 0
                    10'h003: rd_data_n = {16'd0, sticky[15:1], busy_i};
                    10'h004: rd_data_n = {16'd0, irq_en, 1'b0};
                    10'h005: rd_data_n = {16'd0, sticky[15:1] & irq_en[15:1], 1'b0};
                    10'h010: rd_data_n = cycles_i[31:0];
                    10'h011: rd_data_n = cycles_i[63:32];
                    10'h012: rd_data_n = symbols_i;
                    10'h013: rd_data_n = bits_i;
                    10'h014: rd_data_n = {16'd0, build_cycles_i};
                    10'h015: rd_data_n = {24'd0, overfetch_i};
                    10'h040: rd_data_n = {31'd0, busy_i ? mode_l : mode_pend};
                    10'h041: rd_data_n = busy_i ? start_bit_l : start_bit_pend;
                    10'h042: rd_data_n = {23'd0, busy_i ? alphabet_l : alphabet_pend};
                    10'h043: rd_data_n = {29'd0, busy_i ? n_tables_l : n_tables_pend};
                    10'h044: rd_data_n = busy_i ? sym_limit_l : sym_limit_pend;
                    10'h045: rd_data_n = {15'd0, dbg_index, 2'b00, dbg_kind, 1'b0, dbg_table};
                    10'h046: rd_data_n = dbg_data_i;   // live (huff_tables)
                    default: begin
                        rd_data_n = 32'd0;             // reserved reads 0
                        if (rd_addr_i >= 10'h100 && rd_addr_i <= 10'h21F) begin
                            // single stored copy (MAS §4): same value idle and BUSY
                            rd_data_n = {2'b00, len_words[rd_len_idx]};
                        end
                    end
                endcase
            end
        end

        // ---- IRQ ----
        irq_n = |(sticky_n[15:1] & irq_en_n[15:1]);

        // ---- reset ----
        if (!rst_n) begin
            mode_pend_n      = 1'b0;
            start_bit_pend_n = 32'd0;
            alphabet_pend_n  = 9'd0;
            n_tables_pend_n  = 3'd0;
            sym_limit_pend_n = 32'd0;
            mode_l_n      = 1'b0;
            start_bit_l_n = 32'd0;
            alphabet_l_n  = 9'd0;
            n_tables_l_n  = 3'd0;
            sym_limit_l_n = 32'd0;
            dbg_table_n   = 3'd0;
            dbg_kind_n    = 2'd0;
            dbg_index_n   = 9'd0;
            for (int w = 0; w < N_LEN_W; w++) begin
                len_words_n[w] = 30'd0;
            end
            for (int c = 0; c < N_BINS; c++) begin
                cnt_n[c] = 9'd0;
            end
            for (int t = 0; t < 6; t++) begin
                inv_cnt_n[t] = 9'd0;
            end
            sticky_n     = 16'd0;
            irq_en_n     = 15'd0;
            irq_n        = 1'b0;
            db_pending_n = 1'b0;
            db_hold_n    = 1'b0;
            doorbell_n   = 1'b0;
            abort_n      = 1'b0;
            wr_err_n     = 1'b0;
            rd_err_n     = 1'b0;
            rd_data_n    = 32'd0;
        end
    end

    // ---- builder lengths read port ({t, sym} -> field, 1-cycle registered) ---------------------
    logic [2:0]  lrd_t;                                // Addressed table
    logic [8:0]  lrd_sym;                              // Symbol within the table
    logic [8:0]  lrd_div6;                             // sym / 6 (word within the table)
    // verilator lint_off UNUSEDSIGNAL
    logic [8:0]  lrd_mod6;                             // sym % 6 (bits 8:3 unused: remainder <= 5)
    logic [29:0] lrd_shifted;                          // Word shifted down (bits 29:5 unused)
    // verilator lint_on UNUSEDSIGNAL
    logic [8:0]  lrd_idx;                              // Window word index = t*48 + sym/6
    logic [4:0]  lrd_sh;                               // Field shift = (sym % 6) * 5, UQ5.0
    logic [4:0]  lengths_rd_n;                         // Next lengths_rd_data_o
    always_comb begin
        lrd_t       = lengths_rd_addr_i[11:9];
        lrd_sym     = lengths_rd_addr_i[8:0];
        lrd_div6    = lrd_sym / 9'd6;
        lrd_mod6    = lrd_sym % 9'd6;
        lrd_idx     = {1'b0, lrd_t, 5'd0} + {2'b00, lrd_t, 4'd0} + lrd_div6;  // t*48 + sym/6
        lrd_sh      = {lrd_mod6[2:0], 2'b00} + {2'b00, lrd_mod6[2:0]};        // mod6 * 5
        lrd_shifted = len_words[lrd_idx] >> lrd_sh;
        lengths_rd_n = lrd_shifted[4:0];
    end

    // ---- builder counts read port ((t, l) -> bin, combinational) -------------------------------
    logic [6:0] crd_idx;                               // Flattened bin index t*20 + l - 1
    always_comb begin
        crd_idx = {4'd0, counts_rd_table_i} * 7'd20 + {2'd0, counts_rd_len_i} - 7'd1;
        counts_rd_data_o = 9'd0;
        if (counts_rd_table_i < 3'd6
            && counts_rd_len_i >= 5'd1 && counts_rd_len_i <= 5'd20) begin
            counts_rd_data_o = cnt[crd_idx];
        end
    end

    always_ff @(posedge clk) begin
        mode_pend      <= mode_pend_n;
        start_bit_pend <= start_bit_pend_n;
        alphabet_pend  <= alphabet_pend_n;
        n_tables_pend  <= n_tables_pend_n;
        sym_limit_pend <= sym_limit_pend_n;
        mode_l      <= mode_l_n;
        start_bit_l <= start_bit_l_n;
        alphabet_l  <= alphabet_l_n;
        n_tables_l  <= n_tables_l_n;
        sym_limit_l <= sym_limit_l_n;
        dbg_table   <= dbg_table_n;
        dbg_kind    <= dbg_kind_n;
        dbg_index   <= dbg_index_n;
        sticky      <= sticky_n;
        irq_en      <= irq_en_n;
        irq_q       <= irq_n;
        db_pending  <= db_pending_n;
        db_hold     <= db_hold_n;
        doorbell_o  <= doorbell_n;
        abort_o     <= abort_n;
        wr_err_o    <= wr_err_n;
        rd_data_o   <= rd_data_n;
        rd_err_o    <= rd_err_n;
        lengths_rd_data_o <= lengths_rd_n;
        for (int w = 0; w < N_LEN_W; w++) begin
            len_words[w] <= len_words_n[w];
        end
        for (int c = 0; c < N_BINS; c++) begin
            cnt[c] <= cnt_n[c];
        end
        for (int t = 0; t < 6; t++) begin
            inv_cnt[t] <= inv_cnt_n[t];
        end
    end

    assign wr_resp_hold_o     = db_hold;
    assign irq_o              = irq_q;
    assign cfg_mode_o         = mode_l;
    assign cfg_start_bit_o    = start_bit_l;
    assign cfg_alphabet_o     = alphabet_l;
    assign cfg_n_tables_o     = n_tables_l;
    assign cfg_symbol_limit_o = sym_limit_l;
    assign dbg_table_o        = dbg_table;
    assign dbg_kind_o         = dbg_kind;
    assign dbg_index_o        = dbg_index;

endmodule

`default_nettype wire
