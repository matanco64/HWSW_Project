`default_nettype none

// Module: mtf_cam
// Purpose: Top level (MAS §1/§7). Instantiates axi_lite_if + mtf_regs + mtf_ctrl + mtf_list +
//          mtf_run + item_fifo + mtf_expand + mtf_pack and owns the pieces that span them: the
//          two-sided split (symbol side vs drain side across the item FIFO), the 2-wide item
//          enqueue (a terminating run item plus the symbol's MTF byte, M2), the enqueue-after-
//          check byte-budget gate (M3), the CYCLES/SYMBOLS_IN/BYTES_OUT/INIT_CYCLES/MAX_RUN
//          counters and bytes-committed accumulator, the ERR_LIMIT (byte + symbol) mapping, and
//          the three-port protocol assertions.
module mtf_cam #(
    parameter int          W       = 8,              // Output lanes (bytes/beat), 4/8/16
    parameter int          N_LIST  = 256,            // List capacity / byte-value domain
    parameter int          D       = 8,              // Item-FIFO depth (>= 2)
    parameter int          RUN_W   = 21,             // Run width (holds 2^20)
    parameter logic [31:0] VERSION = 32'd0           // git short SHA
) (
    input  logic            clk,                     // System clock
    input  logic            rst_n,                   // Active-low synchronous reset
    // AXI4-Lite slave (MAS §2)
    input  logic [11:0]     s_axi_awaddr,            // Write address
    input  logic [2:0]      s_axi_awprot,            // Ignored
    input  logic            s_axi_awvalid,           // Write address valid
    output logic            s_axi_awready,           // Write address ready
    input  logic [31:0]     s_axi_wdata,             // Write data
    input  logic [3:0]      s_axi_wstrb,             // Byte strobes
    input  logic            s_axi_wvalid,            // Write data valid
    output logic            s_axi_wready,            // Write data ready
    output logic [1:0]      s_axi_bresp,             // Write response
    output logic            s_axi_bvalid,            // Write response valid
    input  logic            s_axi_bready,            // Write response ready
    input  logic [11:0]     s_axi_araddr,            // Read address
    input  logic [2:0]      s_axi_arprot,            // Ignored
    input  logic            s_axi_arvalid,           // Read address valid
    output logic            s_axi_arready,           // Read address ready
    output logic [31:0]     s_axi_rdata,             // Read data
    output logic [1:0]      s_axi_rresp,             // Read response
    output logic            s_axi_rvalid,            // Read data valid
    input  logic            s_axi_rready,            // Read data ready
    // AXI4-Stream slave s_sym (symbol beats, ADR-0006)
    input  logic [31:0]     s_axis_sym_tdata,        // Symbol beat
    input  logic            s_axis_sym_tvalid,       // Beat valid
    output logic            s_axis_sym_tready,       // Beat ready
    input  logic            s_axis_sym_tlast,        // Beat TLAST (EOB)
    // AXI4-Stream master m_l (L-vector bytes, W lanes)
    output logic [8*W-1:0]  m_axis_l_tdata,          // Packed bytes (byte 0 in [7:0])
    output logic [W-1:0]    m_axis_l_tkeep,          // Contiguous-from-lane-0 keep
    output logic            m_axis_l_tvalid,         // Beat valid (registered)
    input  logic            m_axis_l_tready,         // Beat ready
    output logic            m_axis_l_tlast,          // Last beat of the block
    // Interrupt
    output logic            irq                      // Level IRQ
);

    localparam int ITEM_W = 1 + RUN_W + 8;           // {is_run, n, byte}
    localparam int KCW    = $clog2(W + 1);           // TKEEP popcount width

    // ---- register bus --------------------------------------------------------------------------
    logic        req_wr;                             // Write pulse
    logic [9:0]  wr_addr;                            // Write word address
    logic [31:0] wr_data;                            // Write data
    logic [3:0]  wr_strb;                            // Strobes
    logic        wr_err;                             // Write SLVERR
    logic        wr_resp_hold;                       // BRESP hold
    logic        req_rd;                             // Read pulse
    logic [9:0]  rd_addr;                            // Read word address
    logic [31:0] rd_data;                            // Read data
    logic        rd_err;                             // Read SLVERR

    axi_lite_if #(
        .ADDR_W(12)
    ) u_axi (
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

    // ---- inter-block wires ---------------------------------------------------------------------
    logic              doorbell;                     // Accepted doorbell
    logic              abort_req;                    // Abort pulse
    logic              busy;                         // FSM busy
    logic [N_LIST-1:0] used_map;                     // Used map
    logic [31:0]       symbol_limit;                 // SYMBOL_LIMIT
    logic [31:0]       bytes_limit;                  // BYTES_LIMIT
    logic [7:0]        dbg_sel;                      // DBG_SEL
    logic [7:0]        dbg_data;                     // DBG_DATA

    logic              done_set;                     // DONE pulse
    logic              aborted_set;                  // ABORTED pulse
    logic              err_rank;                     // ERR_RANK pulse
    logic              err_run;                      // ERR_RUN pulse
    logic              err_underrun;                 // ERR_UNDERRUN pulse
    logic              err_limit;                    // ERR_LIMIT pulse (byte + symbol)

    // List
    logic              init_start;                   // Begin fill
    logic              init_active;                  // In INIT
    logic              init_busy;                    // Fill in progress
    logic [8:0]        n_used;                       // N_USED
    logic [7:0]        rd_rank;                      // Rank to read
    logic [7:0]        list_rd_byte;                 // list[rd_rank]
    logic [7:0]        list_byte0;                   // list[0]
    logic              mv_en;                        // Move-to-front
    logic [7:0]        mv_rank;                      // Move rank

    // Run
    logic              run_clr;                      // Clear accumulator
    logic              run_acc;                      // Accept run symbol
    logic              run_bit;                      // RUNA/RUNB
    logic              run_commit;                   // Run item enqueued (MAX_RUN)
    logic [RUN_W-1:0]  run_n;                        // Current run
    logic              run_nonzero;                  // Run pending
    logic              run_overflow;                 // Would overflow
    logic [RUN_W-1:0]  max_run;                      // MAX_RUN

    // Item requests (ctrl -> enqueue gate)
    logic              item_run_valid;               // Run item present
    logic [RUN_W-1:0]  item_run_n;                   // Run length
    logic [7:0]        item_run_byte;                // Run byte
    logic              item_mtf_valid;               // MTF item present
    logic [7:0]        item_mtf_byte;                // MTF byte
    logic              beat_accept;                  // Beat accepted
    logic              is_eob;                       // EOB beat

    // Flush
    logic              pipe_flush;                   // FIFO + expander flush
    logic              pack_flush_normal;            // Packer flush (TLAST)
    logic              pack_flush_err;               // Packer flush (no TLAST)
    logic              pack_discard;                 // Packer withdraw pending beat

    // FIFO
    logic              fifo_wr_a_en;                 // Enqueue item A
    logic [ITEM_W-1:0] fifo_wr_a_data;               // Item A
    logic              fifo_wr_b_en;                 // Enqueue item B
    logic [ITEM_W-1:0] fifo_wr_b_data;               // Item B
    logic              fifo_can_wr2;                 // >= 2 free slots
    logic              fifo_rd_en;                   // Pop
    logic              fifo_rd_valid;                // Head valid
    logic [ITEM_W-1:0] fifo_rd_data;                 // Head item
    logic              fifo_empty;                   // Empty

    // Expander -> packer
    logic              exp_out_valid;                // Bytes valid
    logic [KCW-1:0]    exp_out_cnt;                  // Byte count
    logic [8*W-1:0]    exp_out_data;                 // Byte lanes
    logic              exp_idle;                     // Expander idle
    logic              pack_ready;                   // Packer accepts bytes
    logic              pack_idle;                    // Packer drained

    // Counters
    logic [63:0]       cycles_q,      cycles_n;      // CYCLES
    logic [31:0]       symbols_in_q,  symbols_in_n;  // SYMBOLS_IN
    logic [31:0]       bytes_out_q,   bytes_out_n;   // BYTES_OUT
    logic [8:0]        init_cycles_q, init_cycles_n; // INIT_CYCLES
    logic [31:0]       committed_q,   committed_n;   // Bytes committed (M3 budget)

    // ---- register file -------------------------------------------------------------------------
    mtf_regs #(
        .W(W), .D(D), .N_LIST(N_LIST), .VERSION(VERSION)
    ) u_regs (
        .clk(clk), .rst_n(rst_n),
        .req_wr_i(req_wr), .wr_addr_i(wr_addr), .wr_data_i(wr_data), .wr_strb_i(wr_strb),
        .wr_err_o(wr_err), .wr_resp_hold_o(wr_resp_hold),
        .req_rd_i(req_rd), .rd_addr_i(rd_addr), .rd_data_o(rd_data), .rd_err_o(rd_err),
        .doorbell_o(doorbell), .abort_o(abort_req), .busy_i(busy),
        .done_set_i(done_set), .aborted_set_i(aborted_set),
        .err_rank_i(err_rank), .err_run_i(err_run), .err_limit_i(err_limit),
        .err_underrun_i(err_underrun),
        .cycles_i(cycles_q), .symbols_in_i(symbols_in_q), .bytes_out_i(bytes_out_q),
        .init_cycles_i(init_cycles_q), .max_run_i(max_run),
        .used_map_o(used_map), .symbol_limit_o(symbol_limit), .bytes_limit_o(bytes_limit),
        .dbg_sel_o(dbg_sel), .dbg_data_i(dbg_data),
        .irq_o(irq)
    );

    // ---- control / sequencer -------------------------------------------------------------------
    mtf_ctrl u_ctrl (
        .clk(clk), .rst_n(rst_n),
        .doorbell_i(doorbell), .abort_i(abort_req),
        .sym_tvalid_i(s_axis_sym_tvalid), .sym_tdata_i(s_axis_sym_tdata),
        .sym_tlast_i(s_axis_sym_tlast), .sym_tready_o(s_axis_sym_tready),
        .n_used_i(n_used), .init_busy_i(init_busy),
        .list_rd_byte_i(list_rd_byte), .list_byte0_i(list_byte0),
        .init_start_o(init_start), .init_active_o(init_active),
        .rd_rank_o(rd_rank), .mv_en_o(mv_en), .mv_rank_o(mv_rank),
        .run_n_i(run_n), .run_nonzero_i(run_nonzero), .run_overflow_i(run_overflow),
        .run_clr_o(run_clr), .run_acc_o(run_acc), .run_bit_o(run_bit),
        .item_run_valid_o(item_run_valid), .item_run_n_o(item_run_n), .item_run_byte_o(item_run_byte),
        .item_mtf_valid_o(item_mtf_valid), .item_mtf_byte_o(item_mtf_byte),
        .beat_accept_o(beat_accept), .is_eob_o(is_eob),
        .err_limit_i(err_limit),
        .fifo_can_wr2_i(fifo_can_wr2), .fifo_empty_i(fifo_empty),
        .exp_idle_i(exp_idle), .pack_idle_i(pack_idle),
        .pipe_flush_o(pipe_flush), .pack_flush_normal_o(pack_flush_normal),
        .pack_flush_err_o(pack_flush_err), .pack_discard_o(pack_discard),
        .done_set_o(done_set), .aborted_set_o(aborted_set),
        .err_rank_o(err_rank), .err_run_o(err_run), .err_underrun_o(err_underrun),
        .busy_o(busy)
    );

    // ---- list ----------------------------------------------------------------------------------
    mtf_list #(
        .N_LIST(N_LIST)
    ) u_list (
        .clk(clk), .rst_n(rst_n),
        .init_start(init_start), .used_map(used_map),
        .init_busy_o(init_busy), .n_used_o(n_used),
        .rd_rank(rd_rank), .rd_byte_o(list_rd_byte), .byte0_o(list_byte0),
        .mv_en(mv_en), .mv_rank(mv_rank),
        .dbg_sel(dbg_sel), .dbg_data_o(dbg_data)
    );

    // ---- run accumulator -----------------------------------------------------------------------
    mtf_run #(
        .RUN_W(RUN_W)
    ) u_run (
        .clk(clk), .rst_n(rst_n),
        .clr(run_clr), .inv_clr(doorbell), .acc_en(run_acc), .run_bit(run_bit), .commit(run_commit),
        .n_o(run_n), .nonzero_o(run_nonzero), .overflow_o(run_overflow), .max_run_o(max_run)
    );

    // ---- ERR_LIMIT and 2-wide enqueue (M2, M3) -------------------------------------------------
    logic              ctrl_error;                   // ctrl-detected error this beat
    logic              has_i0;                       // A first item is offered
    logic              i1_present;                   // A second item is offered
    logic [RUN_W-1:0]  i0_bytes;                     // Bytes of the first item
    logic [32:0]       c1;                           // committed + i0 bytes
    logic [32:0]       c2;                           // c1 + i1 byte
    logic              i0_exceed;                    // First item over budget
    logic              i1_exceed;                    // Second item over budget
    logic              err_limit_byte;               // Byte-budget ERR_LIMIT (M3)
    logic              err_limit_sym;                // Symbol-count ERR_LIMIT
    logic [31:0]       sym_next;                     // symbols_in + 1
    logic              total_error;                  // Any error this beat
    logic              clean_beat;                   // Accepted, no error -> enqueue

    always_comb begin
        ctrl_error  = err_rank || err_run || err_underrun;
        has_i0      = item_run_valid || item_mtf_valid;
        i1_present  = item_run_valid && item_mtf_valid;
        i0_bytes    = item_run_valid ? item_run_n : {{(RUN_W-1){1'b0}}, 1'b1};

        c1 = {1'b0, committed_q} + (has_i0     ? {{(33-RUN_W){1'b0}}, i0_bytes} : 33'd0);
        c2 = c1                  + (i1_present ? 33'd1 : 33'd0);

        i0_exceed = has_i0     && (c1 > {1'b0, bytes_limit});
        i1_exceed = i1_present && (c2 > {1'b0, bytes_limit});
        err_limit_byte = i0_exceed || i1_exceed;

        sym_next      = symbols_in_q + 32'd1;
        err_limit_sym = beat_accept && !is_eob && (symbol_limit != 32'd0)
                        && (sym_next == symbol_limit);

        err_limit  = beat_accept && !ctrl_error && (err_limit_byte || err_limit_sym);
        total_error = ctrl_error || err_limit;
        clean_beat  = beat_accept && !total_error;

        // Port A = the first item (run if present, else the MTF byte); port B = the MTF byte.
        fifo_wr_a_en   = clean_beat && has_i0;
        fifo_wr_a_data = item_run_valid ? {1'b1, item_run_n, item_run_byte}
                                        : {1'b0, {RUN_W{1'b0}}, item_mtf_byte};
        fifo_wr_b_en   = clean_beat && i1_present;
        fifo_wr_b_data = {1'b0, {RUN_W{1'b0}}, item_mtf_byte};

        run_commit     = fifo_wr_a_en && item_run_valid;
    end

    item_fifo #(
        .D(D), .ITEM_W(ITEM_W)
    ) u_fifo (
        .clk(clk), .rst_n(rst_n), .flush(pipe_flush),
        .wr_a_en(fifo_wr_a_en), .wr_a_data(fifo_wr_a_data),
        .wr_b_en(fifo_wr_b_en), .wr_b_data(fifo_wr_b_data),
        .can_wr2_o(fifo_can_wr2),
        .rd_en(fifo_rd_en), .rd_valid_o(fifo_rd_valid), .rd_data_o(fifo_rd_data),
        .empty_o(fifo_empty)
    );

    // ---- expander ------------------------------------------------------------------------------
    mtf_expand #(
        .W(W), .RUN_W(RUN_W), .ITEM_W(ITEM_W)
    ) u_expand (
        .clk(clk), .rst_n(rst_n), .flush(pipe_flush),
        .fifo_rd_valid(fifo_rd_valid), .fifo_rd_data(fifo_rd_data), .fifo_rd_en_o(fifo_rd_en),
        .pack_ready(pack_ready),
        .out_valid_o(exp_out_valid), .out_cnt_o(exp_out_cnt), .out_data_o(exp_out_data),
        .idle_o(exp_idle)
    );

    // ---- packer --------------------------------------------------------------------------------
    mtf_pack #(
        .W(W)
    ) u_pack (
        .clk(clk), .rst_n(rst_n),
        .in_valid(exp_out_valid), .in_cnt(exp_out_cnt), .in_data(exp_out_data),
        .pack_ready_o(pack_ready),
        .flush_normal(pack_flush_normal), .flush_err(pack_flush_err), .discard(pack_discard),
        .m_ready(m_axis_l_tready), .m_valid_o(m_axis_l_tvalid), .m_data_o(m_axis_l_tdata),
        .m_keep_o(m_axis_l_tkeep), .m_last_o(m_axis_l_tlast), .idle_o(pack_idle)
    );

    // ---- counters ------------------------------------------------------------------------------
    logic           m_hs;                            // m_l handshake this cycle
    logic [KCW-1:0] keep_pop;                        // TKEEP popcount
    assign m_hs = m_axis_l_tvalid && m_axis_l_tready;
    always_comb begin
        keep_pop = {KCW{1'b0}};
        for (int l = 0; l < W; l++) begin
            keep_pop = keep_pop + {{(KCW-1){1'b0}}, m_axis_l_tkeep[l]};
        end
    end

    always_comb begin
        cycles_n      = cycles_q;
        symbols_in_n  = symbols_in_q;
        bytes_out_n   = bytes_out_q;
        init_cycles_n = init_cycles_q;
        committed_n   = committed_q;

        if (busy) begin
            cycles_n = cycles_q + 64'd1;
        end
        if (beat_accept) begin
            symbols_in_n = symbols_in_q + 32'd1;
        end
        if (m_hs) begin
            bytes_out_n = bytes_out_q + {{(32-KCW){1'b0}}, keep_pop};
        end
        if (init_active) begin
            init_cycles_n = init_cycles_q + 9'd1;
        end
        committed_n = committed_q
                      + (fifo_wr_a_en ? {{(32-RUN_W){1'b0}}, i0_bytes} : 32'd0)
                      + (fifo_wr_b_en ? 32'd1 : 32'd0);

        if (doorbell) begin                          // Restart counters at the accepted doorbell
            cycles_n      = 64'd0;
            symbols_in_n  = 32'd0;
            bytes_out_n   = 32'd0;
            init_cycles_n = 9'd0;
            committed_n   = 32'd0;
        end
        if (!rst_n) begin
            cycles_n      = 64'd0;
            symbols_in_n  = 32'd0;
            bytes_out_n   = 32'd0;
            init_cycles_n = 9'd0;
            committed_n   = 32'd0;
        end
    end

    always_ff @(posedge clk) begin
        cycles_q      <= cycles_n;
        symbols_in_q  <= symbols_in_n;
        bytes_out_q   <= bytes_out_n;
        init_cycles_q <= init_cycles_n;
        committed_q   <= committed_n;
    end

    // ---- protocol assertions (three ports) -----------------------------------------------------
    // Concurrent SVA: Verilator-only (VERILATOR is auto-defined; cocotb_run arms them with
    // --assert). Icarus (-g2012) and Yosys `synth` cannot parse `assert property`, so guarding
    // these on SIMULATION broke `make sim-icarus` (dv-bringup step 3); the 4-state Icarus X-check
    // relies on the pyuvm monitors' is_resolvable asserts, not these. Matches the
    // fp64_rcp_nr/fp64_sqrt_srt `ifdef VERILATOR` convention.
`ifdef VERILATOR
    // m_l: tvalid is registered and never withdrawn or mutated under back-pressure (PRD-F6).
    property p_ml_stable;
        @(posedge clk) disable iff (!rst_n)
        (m_axis_l_tvalid && !m_axis_l_tready && !pack_discard)
        |=> (m_axis_l_tvalid && $stable(m_axis_l_tdata) && $stable(m_axis_l_tkeep)
             && $stable(m_axis_l_tlast));
    endproperty
    a_ml_stable: assert property (p_ml_stable)
        else $error("mtf_cam: m_l beat changed under back-pressure");

    // m_l: a valid beat has a contiguous-from-lane-0 non-zero TKEEP (S3).
    property p_ml_keep_contig;
        @(posedge clk) disable iff (!rst_n)
        m_axis_l_tvalid |-> ((m_axis_l_tkeep != {W{1'b0}})
                             && (((m_axis_l_tkeep + W'(1)) & m_axis_l_tkeep) == {W{1'b0}}));
    endproperty
    a_ml_keep_contig: assert property (p_ml_keep_contig)
        else $error("mtf_cam: m_l TKEEP not contiguous from lane 0");

    // item FIFO: a second-port write implies a first-port write (M2), and only with room.
    property p_fifo_b_implies_a;
        @(posedge clk) disable iff (!rst_n)
        fifo_wr_b_en |-> fifo_wr_a_en;
    endproperty
    a_fifo_b_implies_a: assert property (p_fifo_b_implies_a)
        else $error("mtf_cam: item FIFO port B without port A");

    property p_fifo_room;
        @(posedge clk) disable iff (!rst_n)
        fifo_wr_a_en |-> fifo_can_wr2;
    endproperty
    a_fifo_room: assert property (p_fifo_room)
        else $error("mtf_cam: item FIFO enqueue without reserved slots");

    // M3: committed bytes never exceed BYTES_LIMIT (enqueue-after-check gate).
    property p_bytes_budget;
        @(posedge clk) disable iff (!rst_n)
        busy |-> (committed_q <= bytes_limit);
    endproperty
    a_bytes_budget: assert property (p_bytes_budget)
        else $error("mtf_cam: committed bytes exceeded BYTES_LIMIT");

    // s_sym accepted only while ready; terminal status pulses are mutually exclusive.
    property p_done_abort_excl;
        @(posedge clk) disable iff (!rst_n)
        !(done_set && aborted_set);
    endproperty
    a_done_abort_excl: assert property (p_done_abort_excl)
        else $error("mtf_cam: DONE and ABORTED asserted together");
`endif

endmodule

`default_nettype wire
