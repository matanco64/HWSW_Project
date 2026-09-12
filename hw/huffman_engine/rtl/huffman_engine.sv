`default_nettype none

// Module: huffman_engine
// Purpose: Top level (uArch §1): axi_lite_if + huff_regs + huff_ctrl + huff_aligner +
//          huff_builder + huff_tables + huff_decoder + huff_selector + huff_deflate +
//          huff_out. Owns the C0→C1→C2 pipeline registers, the single stall, the consume
//          arbitration, the DEFLATE window remap (aligner convention: next stream bit at
//          window[5] ascending — remapped so the code's first bit sits at bit 19 for the
//          decoder), the counters and the error mapping (MAS §4 bits 9..15).
module huffman_engine #(
    parameter logic [31:0] VERSION = 32'd0             // git short SHA
) (
    input  logic        clk,                           // System clock
    input  logic        rst_n,                         // Active-low synchronous reset
    // AXI4-Lite slave (MAS §2)
    input  logic [11:0] s_axi_awaddr,
    input  logic [2:0]  s_axi_awprot,
    input  logic        s_axi_awvalid,
    output logic        s_axi_awready,
    input  logic [31:0] s_axi_wdata,
    input  logic [3:0]  s_axi_wstrb,
    input  logic        s_axi_wvalid,
    output logic        s_axi_wready,
    output logic [1:0]  s_axi_bresp,
    output logic        s_axi_bvalid,
    input  logic        s_axi_bready,
    input  logic [11:0] s_axi_araddr,
    input  logic [2:0]  s_axi_arprot,
    input  logic        s_axi_arvalid,
    output logic        s_axi_arready,
    output logic [31:0] s_axi_rdata,
    output logic [1:0]  s_axi_rresp,
    output logic        s_axi_rvalid,
    input  logic        s_axi_rready,
    // Bit stream in
    input  logic [31:0] s_axis_bits_tdata,
    input  logic [3:0]  s_axis_bits_tkeep,
    input  logic        s_axis_bits_tlast,
    input  logic        s_axis_bits_tvalid,
    output logic        s_axis_bits_tready,
    // Selector stream in (bzip2)
    input  logic [7:0]  s_axis_sel_tdata,
    input  logic        s_axis_sel_tlast,
    input  logic        s_axis_sel_tvalid,
    output logic        s_axis_sel_tready,
    // Symbol stream out
    output logic [31:0] m_axis_sym_tdata,
    output logic        m_axis_sym_tlast,
    output logic        m_axis_sym_tvalid,
    input  logic        m_axis_sym_tready,
    output logic        irq                            // Level interrupt
);

    // ---- register bus --------------------------------------------------------------------------
    logic        req_wr, req_rd, wr_err, wr_resp_hold, rd_err;
    logic [9:0]  wr_addr, rd_addr;
    logic [31:0] wr_data, rd_data;
    logic [3:0]  wr_strb;

    axi_lite_if #(.ADDR_W(12)) u_axi (
        .clk(clk), .rst_n(rst_n),
        .s_axi_awaddr(s_axi_awaddr), .s_axi_awprot(s_axi_awprot),
        .s_axi_awvalid(s_axi_awvalid), .s_axi_awready(s_axi_awready),
        .s_axi_wdata(s_axi_wdata), .s_axi_wstrb(s_axi_wstrb),
        .s_axi_wvalid(s_axi_wvalid), .s_axi_wready(s_axi_wready),
        .s_axi_bresp(s_axi_bresp), .s_axi_bvalid(s_axi_bvalid), .s_axi_bready(s_axi_bready),
        .s_axi_araddr(s_axi_araddr), .s_axi_arprot(s_axi_arprot),
        .s_axi_arvalid(s_axi_arvalid), .s_axi_arready(s_axi_arready),
        .s_axi_rdata(s_axi_rdata), .s_axi_rresp(s_axi_rresp),
        .s_axi_rvalid(s_axi_rvalid), .s_axi_rready(s_axi_rready),
        .req_wr_o(req_wr), .wr_addr_o(wr_addr), .wr_data_o(wr_data), .wr_strb_o(wr_strb),
        .wr_err_i(wr_err), .wr_resp_hold_i(wr_resp_hold),
        .req_rd_o(req_rd), .rd_addr_o(rd_addr), .rd_data_i(rd_data), .rd_err_i(rd_err)
    );

    // ---- regs ----------------------------------------------------------------------------------
    logic        doorbell, abort_p, busy, done_set, aborted_set;
    logic [6:0]  err_set;
    // verilator coverage_off
    // Toggle exclusion (testplan §5): invocation-lifetime counters, upper bits unreachable
    // (benchmark block 149k cycles/148k symbols/531k bits = 18..20 bits).
    logic [63:0] cycles_q;
    logic [31:0] symbols_q, bits_w;
    // verilator coverage_on
    logic [15:0] build_cycles;
    // verilator coverage_off
    logic [7:0]  overfetch_q;                          // FIFO-capped at 4; upper bits unreachable
    // verilator coverage_on
    logic        cfg_mode;
    // verilator coverage_off
    // Toggle exclusion (§5): doorbell-validated START_BIT/SYMBOL_LIMIT; upper bits unreachable.
    logic [31:0] cfg_start_bit, cfg_symbol_limit;
    // verilator coverage_on
    logic [8:0]  cfg_alphabet;
    logic [2:0]  cfg_n_tables;
    logic [11:0] lengths_addr;
    logic [4:0]  lengths_data;
    logic [7:0]  counts_addr;
    logic [8:0]  counts_data;
    logic [10:0] dbg_addr;
    logic [19:0] dbg_data;
    logic [2:0]  dbg_table;
    logic [1:0]  dbg_kind;
    logic [8:0]  dbg_index;

    // Declared before first use (Icarus elaborates instance-port expressions in order;
    // grape lesson: declare-before-use).
    logic build_busy;           // builder walking tables (counts read mux below)
    logic limit_stop;           // SYMBOL_LIMIT reached (C0 event gate)
    logic c0_ev_ok;             // C0 event qualifies (post-skid, post-limit)
    logic tail_short;           // code would consume past the last valid bit
    logic al_tail;              // aligner past TLAST (tail rule)
    logic [6:0]  al_occ_real;   // real (non-padded) aligner occupancy, UQ7.0
    logic [9:0]  dbg_sym_data;  // symtab DBG read data
    logic [19:0] dbg_fc;        // first_code DBG read data
    logic [10:0] dbg_base;      // base DBG read data
    logic        sel_set_valid; // selector applied this invocation (R3)
    logic [4:0]  c1_len;        // C1 code length (DEFLATE distance resolve)
    logic        out_full;      // output skid full (stall source)
    logic        out_beat;      // beat handshaken this cycle
    logic        out_tlast_q;   // TLAST of the parked beat
    logic        built_q;       // First build of the invocation completed (N5)

    huff_regs #(.VERSION(VERSION)) u_regs (
        .clk(clk), .rst_n(rst_n),
        .req_wr_i(req_wr), .wr_addr_i(wr_addr), .wr_data_i(wr_data), .wr_strb_i(wr_strb),
        .wr_err_o(wr_err), .wr_resp_hold_o(wr_resp_hold),
        .req_rd_i(req_rd), .rd_addr_i(rd_addr), .rd_data_o(rd_data), .rd_err_o(rd_err),
        .doorbell_o(doorbell), .abort_o(abort_p), .busy_i(busy),
        .done_set_i(done_set), .aborted_set_i(aborted_set), .err_set_i(err_set),
        .cycles_i(cycles_q), .symbols_i(symbols_q), .bits_i(bits_w),
        .build_cycles_i(build_cycles), .overfetch_i(overfetch_q),
        .dbg_data_i({12'd0, dbg_data}), .dbg_table_o(dbg_table), .dbg_kind_o(dbg_kind),
        .dbg_index_o(dbg_index),
        .cfg_mode_o(cfg_mode), .cfg_start_bit_o(cfg_start_bit),
        .cfg_alphabet_o(cfg_alphabet), .cfg_n_tables_o(cfg_n_tables),
        .cfg_symbol_limit_o(cfg_symbol_limit),
        .lengths_rd_addr_i(lengths_addr), .lengths_rd_data_o(lengths_data),
        .counts_rd_table_i(build_busy ? counts_addr[7:5] : dbg_table),
        .counts_rd_len_i(build_busy ? counts_addr[4:0] : dbg_index[4:0]),
        .counts_rd_data_o(counts_data),
        .irq_o(irq)
    );

    // ---- control -------------------------------------------------------------------------------
    logic prep, decode_en, drain, start_pulse, flush, ctrl_done, ctrl_aborted;
    logic [5:0] ctrl_err;
    logic build_done, err_table, fill_active;
    logic skip_done, underrun, occ_ok;
    logic stall, c0_valid, eob_c0, nocode_c0, err_sel, err_symbol, limit_hit;
    logic out_empty, eob_sent, sel_drained;

    huff_ctrl u_ctrl (
        .clk(clk), .rst_n(rst_n),
        .doorbell_i(doorbell), .abort_i(abort_p),
        .build_done_i(build_done), .err_table_i(err_table), .skip_done_i(skip_done),
        .stall_i(stall), .c0_valid_i(c0_valid),
        .eob_i(eob_c0 && !limit_stop && c0_ev_ok && !tail_short),
        .nocode_i(nocode_c0 && c0_ev_ok),
        .err_sel_i(err_sel),
        .underrun_i(underrun || (decode_en && c0_valid && !stall && tail_short && c0_ev_ok)),
        .err_symbol_i(err_symbol), .limit_hit_i(limit_hit),
        .out_empty_i(out_empty), .eob_sent_i(eob_sent), .sel_drained_i(sel_drained),
        .mode_deflate_i(cfg_mode),
        .busy_o(busy), .prep_o(prep), .decode_o(decode_en), .drain_o(drain),
        .start_pulse_o(start_pulse),
        .done_set_o(ctrl_done), .aborted_set_o(ctrl_aborted), .err_set_o(ctrl_err),
        .flush_o(flush)
    );
    assign done_set    = ctrl_done;
    assign aborted_set = ctrl_aborted;
    // MAS bits 9..15 = {PARAM, TABLE, NOCODE, SELECTOR, SYMBOL, LIMIT, UNDERRUN};
    // regs raises PARAM itself -> err_set_i[0] = 0 here. ctrl_err = {LIMIT,SYMBOL,UNDERRUN,SEL,NOCODE,TABLE}.
    assign err_set = {ctrl_err[3], ctrl_err[5], ctrl_err[4], ctrl_err[2],
                      ctrl_err[1], ctrl_err[0], 1'b0};

    // ---- aligner -------------------------------------------------------------------------------
    logic [19:0] window;
    logic [4:0]  consume;
    logic        consume_en;

    huff_aligner u_align (
        .clk(clk), .rst_n(rst_n),
        .s_axis_bits_tdata(s_axis_bits_tdata), .s_axis_bits_tkeep(s_axis_bits_tkeep),
        .s_axis_bits_tlast(s_axis_bits_tlast), .s_axis_bits_tvalid(s_axis_bits_tvalid),
        .s_axis_bits_tready(s_axis_bits_tready),
        .start_i(doorbell), .cfg_start_bit_i(cfg_start_bit), .mode_deflate_i(cfg_mode),
        .enable_i(busy),
        .consume_i(consume), .consume_en_i(consume_en),
        .window_o(window), .occ_ok_o(occ_ok), .skip_done_o(skip_done),
        .underrun_o(underrun), .tail_o(al_tail), .occ_real_o(al_occ_real),
        .bits_consumed_o(bits_w)
    );

    // ---- builder + tables ----------------------------------------------------------------------
    logic        wr_set_en, tbase_wr_en, eob_wr_en, eob_clr, symtab_wr_en;
    logic [2:0]  wr_set;
    logic [4:0]  wr_l, b_eob_len;
    logic [19:0] wr_first_code, b_eob_code;
    logic [20:0] wr_limit_la;
    logic [10:0] wr_base, tbase, symtab_wr_addr;
    logic [9:0]  symtab_wr_data;

    huff_builder u_build (
        .clk(clk), .rst_n(rst_n),
        .start_i(doorbell), .stop_i(flush), .mode_deflate_i(cfg_mode),
        .alphabet_i(cfg_alphabet), .n_tables_i(cfg_n_tables),
        .lengths_addr_o(lengths_addr), .lengths_data_i(lengths_data),
        .counts_addr_o(counts_addr), .counts_data_i(counts_data),
        .wr_set_en_o(wr_set_en), .wr_set_o(wr_set), .wr_l_o(wr_l),
        .wr_first_code_o(wr_first_code), .wr_limit_la_o(wr_limit_la), .wr_base_o(wr_base),
        .tbase_wr_en_o(tbase_wr_en), .tbase_o(tbase),
        .eob_wr_en_o(eob_wr_en), .eob_len_o(b_eob_len), .eob_code_o(b_eob_code),
        .eob_clr_o(eob_clr),
        .symtab_wr_en_o(symtab_wr_en), .symtab_wr_addr_o(symtab_wr_addr),
        .symtab_wr_data_o(symtab_wr_data),
        .busy_o(build_busy), .fill_active_o(fill_active),
        .build_done_o(build_done), .err_table_o(err_table), .build_cycles_o(build_cycles)
    );

    logic [2:0]   cur_set, sel_set;
    // verilator coverage_off
    // Toggle exclusion (§5): per-length canonical table params (limit_la/first_code/base), left-aligned UQ21/20/11 fields provisioned for MAXLEN=20 lengths; a given table populates a sparse subset and short codes leave upper bits 0.
    logic [419:0] limit_la_flat;
    logic [399:0] first_code_flat;
    logic [219:0] base_flat;
    // verilator coverage_on
    logic [10:0]  table_base, symtab_rd_addr;
    logic [4:0]   eob_len;
    logic [19:0]  eob_code;
    logic [9:0]   symtab_rd_data;

    huff_tables u_tab (
        .clk(clk), .rst_n(rst_n),
        .wr_set_en_i(wr_set_en), .wr_set_i(wr_set), .wr_l_i(wr_l),
        .wr_first_code_i(wr_first_code), .wr_limit_la_i(wr_limit_la), .wr_base_i(wr_base),
        .tbase_wr_en_i(tbase_wr_en), .tbase_i(tbase),
        .eob_wr_en_i(eob_wr_en), .eob_len_i(b_eob_len), .eob_code_i(b_eob_code),
        .eob_clr_i(eob_clr),
        .symtab_wr_en_i(symtab_wr_en), .symtab_wr_addr_i(symtab_wr_addr),
        .symtab_wr_data_i(symtab_wr_data),
        .fill_active_i(fill_active),
        .cur_set_i(cur_set),
        .limit_la_flat_o(limit_la_flat), .first_code_flat_o(first_code_flat),
        .base_flat_o(base_flat), .table_base_o(table_base),
        .eob_len_o(eob_len), .eob_code_o(eob_code),
        .symtab_rd_addr_i(symtab_rd_addr), .symtab_rd_data_o(symtab_rd_data),
        .dbg_rd_addr_i(dbg_addr), .dbg_rd_data_o(dbg_sym_data),
        .dbg_set_i(dbg_table), .dbg_l_i(dbg_index[4:0]),
        .dbg_first_code_o(dbg_fc), .dbg_base_o(dbg_base)
    );
    // R10: symtab DBG address = t*288 + index (the builder's table_base stride)
    assign dbg_addr = 11'({3'd0, dbg_table} * 9'd288) + 11'(dbg_index);
    // DBG_DATA mux by kind (MAS 0x114): 0 count, 1 first_code, 2 base, 3 symtab. Kind-0
    // counts share the builder's read port — DBG gets it when the builder is idle.
    // N5: MAS 0x118 — reads 0 for table >= N_TABLES, out-of-range index, or before the
    // first build of the invocation (built_q); kind-1 carries the full UQ20.0 first_code.
    logic dbg_ok;
    always_comb begin
        dbg_ok = ({29'd0, dbg_table} < {29'd0, cfg_n_tables}) && built_q
                 && ((dbg_kind == 2'd3) ? (dbg_index < cfg_alphabet)
                                        : (dbg_index >= 9'd1 && dbg_index <= 9'd20));
        dbg_data = 20'd0;
        if (dbg_ok) begin
            case (dbg_kind)
                2'd0:    dbg_data = build_busy ? 20'd0 : {11'd0, counts_data};
                2'd1:    dbg_data = dbg_fc;
                2'd2:    dbg_data = {9'd0, dbg_base};
                default: dbg_data = {10'd0, dbg_sym_data};
            endcase
        end
    end

    // ---- selector ------------------------------------------------------------------------------
    logic sel_stall, issue;

    huff_selector u_sel (
        .clk(clk), .rst_n(rst_n),
        .enable_i(decode_en && !cfg_mode),
        .clear_i(doorbell), .drain_i(drain && !cfg_mode),
        .start_i(start_pulse && !cfg_mode),
        .advance_i(issue && !cfg_mode),
        .n_tables_i(cfg_n_tables),
        .s_sel_tdata(s_axis_sel_tdata), .s_sel_tlast(s_axis_sel_tlast),
        .s_sel_tvalid(s_axis_sel_tvalid), .s_sel_tready(s_axis_sel_tready),
        .cur_set_o(sel_set), .set_valid_o(sel_set_valid), .sel_stall_o(sel_stall),
        .err_sel_o(err_sel), .drained_o(sel_drained)
    );

    // ---- DEFLATE engine ------------------------------------------------------------------------
    logic        dfl_busy, dfl_force_dist, dfl_dist_issue, dfl_emit;
    logic [4:0]  dfl_extra;
    logic [31:0] dfl_data;
    logic        c1_v, c1_eob, c1_dist;
    logic [8:0]  c1_sym;

    huff_deflate u_dfl (
        .clk(clk), .rst_n(rst_n),
        // narrower stall (out_full only) — the composite stall includes dfl_busy and would
        // be circular; the engine's own gates are occ_ok and the skid
        .mode_deflate_i(cfg_mode), .decode_en_i(decode_en), .stall_i(out_full),
        .c1_valid_i(c1_v && !c1_dist), .c1_sym_i(c1_sym),
        .c1_sym_valid_i(symtab_rd_data[9]),
        .window_i(window), .occ_ok_i(occ_ok),
        .extra_consume_o(dfl_extra),
        .dist_len_i(c1_len), .dist_sym_i(c1_sym), .dist_c1_valid_i(c1_v && c1_dist),
        .busy_o(dfl_busy), .force_dist_set_o(dfl_force_dist), .dist_issue_o(dfl_dist_issue),
        .err_symbol_o(err_symbol),
        .emit_o(dfl_emit), .emit_data_o(dfl_data)
    );

    // ---- decoder (C0) --------------------------------------------------------------------------
    logic [19:0] dec_window;
    // verilator coverage_off
    // Toggle exclusion (§5): C0 decode outputs — code_c0 is right-aligned (short codes leave upper bits 0).
    logic [4:0]  len_c0;
    logic [19:0] code_c0;
    logic [10:0] index_c0;
    // verilator coverage_on
    logic        match_c0;

    // DEFLATE remap: aligner gives next stream bit at window[5] ascending; the decoder wants
    // the code's first bit at bit 19 (agent convention note #4).
    always_comb begin
        dec_window = window;
        if (cfg_mode) begin
            for (int i = 0; i < 15; i++) begin
                dec_window[19 - i] = window[5 + i];
            end
            dec_window[4:0] = 5'd0;
        end
    end

    assign cur_set = cfg_mode ? (dfl_force_dist ? 3'd1 : 3'd0) : sel_set;

    huff_decoder #(.MAXLEN(20)) u_dec (
        .window_i(dec_window),
        .limit_la_i(limit_la_flat), .first_code_i(first_code_flat), .base_i(base_flat),
        .table_base_i(table_base), .eob_len_i(eob_len), .eob_code_i(eob_code),
        .len_o(len_c0), .code_o(code_c0), .index_o(index_c0),
        .match_o(match_c0), .eob_o(eob_c0), .nocode_o(nocode_c0)
    );

    // ---- pipeline: issue / C1 / C2 -------------------------------------------------------------
    logic [1:0]  out_occ;
    // verilator coverage_off
    // Toggle exclusion (testplan §5): issued_cnt bounded by SYMBOL_LIMIT (<= 2^27),
    // accepted_q by the block beat count; upper bits unreachable.
    logic [31:0] issued_cnt;
    logic [31:0] accepted_q;
    // verilator coverage_on

    // R1: an issue in flight (c1_v) plus skid occupancy must never exceed the 2 slots
    // R1 bound with the concurrent pop credited: slots after this cycle =
    // out_occ - out_beat + c1_v; issuing while that is <= 1 keeps the 2-deep skid safe.
    // Without the credit the loop ran at 1.5 cycles/symbol against a ready sink
    // (K1 1.5068 vs model 1.0068, caught by test_bench_block at bring-up). out_beat
    // reaches tvalid only through two registered stages, so no comb tvalid<-tready path.
    assign stall    = ({1'b0, out_occ} - {2'd0, out_beat} + {2'd0, c1_v} >= 3'd2)
                      || sel_stall
                      || (cfg_mode && dfl_busy && !dfl_dist_issue);
    assign c0_valid = occ_ok && skip_done;
    assign limit_stop = (issued_cnt >= cfg_symbol_limit);
    // R15: in DEFLATE mode, C0 outputs are meaningful only when the loop may issue
    assign c0_ev_ok = !cfg_mode || (dfl_dist_issue || (!dfl_busy && !c1_v));
    // R9: in the zero-padded tail, a decode reaching past the real bits is an underrun,
    // never an issued symbol
    assign tail_short = al_tail && ({2'd0, len_c0} > al_occ_real);
    // one C0 issue: normal decode (or the DEFLATE distance decode requested by the engine).
    // B8: a distance issue completes a pair whose beat was already admitted at its length
    // issue — limit_stop must not block it (blocking parked huff_deflate in D_DWAIT
    // forever: no beat, no limit_hit, livelock until the poll timeout).
    assign issue = decode_en && !stall && c0_valid && match_c0 && !eob_c0
                   && (!limit_stop || (cfg_mode && dfl_dist_issue)) && !tail_short
                   && (!cfg_mode || dfl_dist_issue || (!dfl_busy && !c1_v));
    logic eob_issue;                                   // EOB consumes its bits, then DRAIN
    assign eob_issue = decode_en && !stall && c0_valid && eob_c0 && !limit_stop
                       && !tail_short && c0_ev_ok;

    // consume arbitration: decode/eob consume len; DEFLATE extras consume dfl_extra
    always_comb begin
        consume    = 5'd0;
        consume_en = 1'b0;
        if (issue || eob_issue) begin
            consume    = len_c0;
            consume_en = 1'b1;
        end else if (cfg_mode && dfl_extra != 5'd0) begin
            consume    = dfl_extra;
            consume_en = 1'b1;
        end
    end

    assign symtab_rd_addr = index_c0;

    always_ff @(posedge clk) begin
        c1_v    <= (issue || eob_issue) && rst_n && !flush;
        // S5 (dv_signoff review): explicit reset for defense-in-depth/lint clarity — these are
        // safe only via the c1_v qualifier downstream; make the reset state defined.
        c1_eob  <= eob_issue && rst_n;
        c1_dist <= issue && cfg_mode && dfl_dist_issue && rst_n;
        c1_len  <= rst_n ? len_c0 : 5'd0;
        if (doorbell || !rst_n) begin
            issued_cnt <= 32'd0;
        end else if (issue && !(cfg_mode && dfl_dist_issue)) begin
            // B8: a DEFLATE distance decode completes the pair already counted at its
            // length issue — counting it double-counted pairs against SYMBOL_LIMIT
            issued_cnt <= issued_cnt + 32'd1;
        end
    end
    assign c1_sym = symtab_rd_data[8:0];

    // C2: beat formation and push (bzip2 + DEFLATE literals here; DEFLATE pairs via u_dfl)
    logic push, push_last;
    logic [31:0] push_data;
    always_comb begin
        push      = 1'b0;
        push_last = 1'b0;
        push_data = 32'd0;
        if (c1_v && c1_eob) begin
            push      = 1'b1;                         // TYPE 3 EOB, TLAST (MAS §2)
            push_last = 1'b1;
            push_data = {20'd0, 3'd3, c1_sym};
        end else if (c1_v && !c1_dist
                     && (!cfg_mode || (symtab_rd_data[9] && c1_sym < 9'd256))) begin
            push      = 1'b1;                         // TYPE 0 (bzip2) / TYPE 1 (DEFLATE literal)
            push_data = {20'd0, cfg_mode ? 3'd1 : 3'd0, c1_sym};
        end else if (dfl_emit && !underrun) begin
            // S2 (dv_signoff review): suppress the pair beat if an extra-bit consume overran
            // the last valid bit (aligner sticky underrun is high by D_EMIT) — a beat built
            // from zero-padded extras must never leave; ctrl routes to ERR_UNDERRUN instead.
            push      = 1'b1;                         // TYPE 2 length/distance pair
            push_data = dfl_data;
        end
    end

    huff_out u_out (
        .clk(clk), .rst_n(rst_n),
        .push_i(push), .push_data_i(push_data), .push_last_i(push_last),
        .flush_i(flush || doorbell),
        .m_sym_tdata(m_axis_sym_tdata), .m_sym_tlast(m_axis_sym_tlast),
        .m_sym_tvalid(m_axis_sym_tvalid), .m_sym_tready(m_axis_sym_tready),
        .full_o(out_full), .empty_o(out_empty), .beat_o(out_beat), .occ_o(out_occ)
    );

    // ---- counters and completion tracking ------------------------------------------------------
    always_ff @(posedge clk) begin
        if (doorbell) begin
            cycles_q    <= 64'd1;                     // accept cycle counts (PRD-F12)
            symbols_q   <= 32'd0;
            overfetch_q <= 8'd0;
            accepted_q  <= 32'd0;
            built_q     <= 1'b0;
            eob_sent    <= 1'b0;
            limit_hit   <= 1'b0;
            out_tlast_q <= 1'b0;
        end else begin
            if (busy) begin
                cycles_q <= cycles_q + 64'd1;
            end
            if (out_beat) begin
                symbols_q <= symbols_q + 32'd1;
                if (m_axis_sym_tlast) begin
                    eob_sent <= 1'b1;
                end
                limit_hit <= (symbols_q + 32'd1 >= cfg_symbol_limit) && !m_axis_sym_tlast;
            end else begin
                limit_hit <= 1'b0;
            end
            if (s_axis_bits_tvalid && s_axis_bits_tready) begin
                accepted_q <= accepted_q + 32'd1;
            end
            if (ctrl_done || ctrl_aborted || (|ctrl_err)) begin
                // R19 / MAS 0x054, clamped (N6): beats accepted beyond the last consumed bit
                if (accepted_q > ((cfg_start_bit + bits_w + 32'd31) >> 5)) begin
                    overfetch_q <= 8'(accepted_q - ((cfg_start_bit + bits_w + 32'd31) >> 5));
                end else begin
                    overfetch_q <= 8'd0;
                end
            end
            if (build_done) begin
                built_q <= 1'b1;                      // N5: DBG valid from the first build
            end
            out_tlast_q <= m_axis_sym_tlast;
        end
        if (!rst_n) begin
            cycles_q    <= 64'd0;
            symbols_q   <= 32'd0;
            overfetch_q <= 8'd0;
            accepted_q  <= 32'd0;
            built_q     <= 1'b0;
            eob_sent    <= 1'b0;
            limit_hit   <= 1'b0;
            out_tlast_q <= 1'b0;
        end
    end

    logic unused_top;                                  // Sinks
    assign unused_top = build_busy ^ (^code_c0) ^ (^VERSION)
                        ^ dbg_base[10] ^ sel_set_valid ^ out_tlast_q ^ prep;

endmodule

`default_nettype wire
