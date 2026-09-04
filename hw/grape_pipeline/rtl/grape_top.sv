`default_nettype none

// Module: grape_pipeline
// Purpose: Top level (uArch §1): axi_lite_if + grape_regs + grape_body_rf + grape_step_fsm +
//          grape_force_pipe + grape_accum + shared FP64 units (3 add, 3 mul, sqrt, rcp;
//          ADR-0007). Issue merging: the static table (force pipe) owns its slots; grape_accum
//          drives only slots the table leaves free — ORed here, with an SVA that they never
//          collide. FP exception flags are OR-ed valid-qualified into grape_regs (PRD-F13).
module grape_pipeline #(
    parameter int          N_BODIES    = 5,            // Bodies (PRD-F6)
    parameter int          N_PAIRS_MAX = 10,           // Pair-list capacity
    parameter logic [31:0] VERSION     = 32'd0         // git short SHA
) (
    input  logic        clk,                           // System clock
    input  logic        rst_n,                         // Active-low synchronous reset
    // AXI4-Lite slave (MAS §2)
    input  logic [11:0] s_axi_awaddr,                  // Write address
    input  logic [2:0]  s_axi_awprot,                  // Ignored
    input  logic        s_axi_awvalid,                 // Write address valid
    output logic        s_axi_awready,                 // Write address ready
    input  logic [31:0] s_axi_wdata,                   // Write data
    input  logic [3:0]  s_axi_wstrb,                   // Byte strobes
    input  logic        s_axi_wvalid,                  // Write data valid
    output logic        s_axi_wready,                  // Write data ready
    output logic [1:0]  s_axi_bresp,                   // Write response
    output logic        s_axi_bvalid,                  // Write response valid
    input  logic        s_axi_bready,                  // Write response ready
    input  logic [11:0] s_axi_araddr,                  // Read address
    input  logic [2:0]  s_axi_arprot,                  // Ignored
    input  logic        s_axi_arvalid,                 // Read address valid
    output logic        s_axi_arready,                 // Read address ready
    output logic [31:0] s_axi_rdata,                   // Read data
    output logic [1:0]  s_axi_rresp,                   // Read response
    output logic        s_axi_rvalid,                  // Read data valid
    input  logic        s_axi_rready,                  // Read data ready
    output logic        irq                            // Level interrupt
);

    // ---- register bus --------------------------------------------------------------------------
    logic        req_wr;                               // Write pulse
    logic [9:0]  wr_addr;                              // Write word address
    logic [31:0] wr_data;                              // Write data
    logic [3:0]  wr_strb;                              // Strobes
    logic        wr_err;                               // Write SLVERR
    logic        wr_resp_hold;                         // BRESP hold
    logic        req_rd;                               // Read pulse
    logic [9:0]  rd_addr;                              // Read word address
    logic [31:0] rd_data;                              // Read data
    logic        rd_err;                               // Read SLVERR

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

    // ---- control / config ----------------------------------------------------------------------
    logic                       doorbell;              // Accepted doorbell
    logic                       abort_req;             // Abort pulse
    logic                       busy;                  // FSM busy
    logic                       done_set;              // DONE pulse
    logic                       aborted_set;           // ABORTED pulse
    logic [3:0]                 fp_flags_set;          // {invalid, divzero, overflow, underflow}
    logic [31:0]                steps_done;            // Live steps
    logic [63:0]                cycles;                // Live cycles
    logic [63:0]                dt;                    // Latched dt
    logic [31:0]                nsteps;                // Latched NSTEPS
    logic [7:0]                 npairs;                // Latched NPAIRS
    logic [N_PAIRS_MAX*16-1:0]  pairs;                 // Latched pair list
    logic [N_BODIES*7*64-1:0]   body_pending;          // Pending body window
    logic [N_BODIES*7*64-1:0]   body_committed;        // Committed bank
    logic [N_BODIES*7*64-1:0]   body_working;          // Working bank

    grape_regs #(
        .N_BODIES(N_BODIES), .N_PAIRS_MAX(N_PAIRS_MAX), .VERSION(VERSION)
    ) u_regs (
        .clk(clk), .rst_n(rst_n),
        .req_wr_i(req_wr), .wr_addr_i(wr_addr), .wr_data_i(wr_data), .wr_strb_i(wr_strb),
        .wr_err_o(wr_err), .wr_resp_hold_o(wr_resp_hold),
        .req_rd_i(req_rd), .rd_addr_i(rd_addr), .rd_data_o(rd_data), .rd_err_o(rd_err),
        .doorbell_o(doorbell), .abort_o(abort_req),
        .busy_i(busy), .done_set_i(done_set), .aborted_set_i(aborted_set),
        .fp_flags_set_i(fp_flags_set), .steps_done_i(steps_done), .cycles_i(cycles),
        .dt_o(dt), .nsteps_o(nsteps), .npairs_o(npairs), .pairs_o(pairs),
        .body_pending_o(body_pending), .body_committed_i(body_committed),
        .irq_o(irq)
    );

    // ---- step FSM ------------------------------------------------------------------------------
    logic step_start;                                  // Cycle-0 pulse
    logic run;                                         // Step in flight
    logic all_done;                                    // Step ops retired
    logic commit;                                      // Commit pulse

    grape_step_fsm u_fsm (
        .clk(clk), .rst_n(rst_n),
        .doorbell_i(doorbell), .abort_i(abort_req), .nsteps_i(nsteps),
        .busy_o(busy), .done_set_o(done_set), .aborted_set_o(aborted_set),
        .steps_done_o(steps_done), .cycles_o(cycles),
        .step_start_o(step_start), .run_o(run), .all_done_i(all_done), .commit_o(commit)
    );

    // ---- body RF -------------------------------------------------------------------------------
    logic        rf_wr_en;                             // Accum write enable
    logic [2:0]  rf_wr_body;                           // Accum write body
    logic [2:0]  rf_wr_field;                          // Accum write field
    logic [63:0] rf_wr_data;                           // Accum write data

    grape_body_rf #(
        .N_BODIES(N_BODIES)
    ) u_rf (
        .clk(clk), .rst_n(rst_n),
        .load_en_i(doorbell), .load_flat_i(body_pending),
        .working_flat_o(body_working),
        .wr_en_i(rf_wr_en), .wr_body_i(rf_wr_body), .wr_field_i(rf_wr_field),
        .wr_data_i(rf_wr_data),
        .commit_en_i(commit), .committed_flat_o(body_committed)
    );

    // ---- FP64 units ----------------------------------------------------------------------------
    // Issue merge: force pipe owns table slots; accum uses free slots only (SVA below).
    logic [2:0]        fp_add_valid, ac_add_valid, add_valid;   // ADD issue valids
    logic [2:0]        fp_add_sub, ac_add_sub, add_sub;         // Subtract selects
    logic [3*64-1:0]   fp_add_a, ac_add_a, add_a;               // ADD operand a
    logic [3*64-1:0]   fp_add_b, ac_add_b, add_b;               // ADD operand b
    logic [2:0]        add_ovalid;                              // ADD result valids
    logic [3*64-1:0]   add_r;                                   // ADD results
    logic [2:0]        fp_mul_valid, ac_mul_valid, mul_valid;   // MUL issue valids
    logic [3*64-1:0]   fp_mul_a, ac_mul_a, mul_a;               // MUL operand a
    logic [3*64-1:0]   fp_mul_b, ac_mul_b, mul_b;               // MUL operand b
    logic [2:0]        mul_ovalid;                              // MUL result valids
    logic [3*64-1:0]   mul_r;                                   // MUL results
    logic              sqrt_valid;                              // SQRT issue
    logic [63:0]       sqrt_a;                                  // SQRT operand
    logic              sqrt_ovalid;                             // SQRT result valid
    logic [63:0]       sqrt_r;                                  // SQRT result
    logic              rcp_valid;                               // RCP issue
    logic [63:0]       rcp_a;                                   // RCP operand
    logic              rcp_ovalid;                              // RCP result valid
    logic [63:0]       rcp_r;                                   // RCP result
    logic [2:0]        add_free;                                // Table-free ADD slots
    logic [2:0]        mul_free;                                // Table-free MUL slots
    logic [3:0]        add_flags [3];                           // Per-ADD flags
    logic [3:0]        mul_flags [3];                           // Per-MUL flags
    logic [3:0]        sqrt_flags;                              // SQRT flags
    logic [3:0]        rcp_flags;                               // RCP flags

    always_comb begin
        add_valid = fp_add_valid | ac_add_valid;
        add_sub   = fp_add_sub | ac_add_sub;
        add_a     = '0;
        add_b     = '0;
        mul_valid = fp_mul_valid | ac_mul_valid;
        mul_a     = '0;
        mul_b     = '0;
        for (int u = 0; u < 3; u++) begin
            add_a[u*64 +: 64] = fp_add_valid[u] ? fp_add_a[u*64 +: 64] : ac_add_a[u*64 +: 64];
            add_b[u*64 +: 64] = fp_add_valid[u] ? fp_add_b[u*64 +: 64] : ac_add_b[u*64 +: 64];
            mul_a[u*64 +: 64] = fp_mul_valid[u] ? fp_mul_a[u*64 +: 64] : ac_mul_a[u*64 +: 64];
            mul_b[u*64 +: 64] = fp_mul_valid[u] ? fp_mul_b[u*64 +: 64] : ac_mul_b[u*64 +: 64];
        end
    end

`ifdef SIMULATION
    always_comb begin
        assert ((fp_add_valid & ac_add_valid) == 3'b000)
            else $error("grape_top: ADD slot collision table/accum");
        assert ((fp_mul_valid & ac_mul_valid) == 3'b000)
            else $error("grape_top: MUL slot collision table/accum");
    end
`endif

    generate
        for (genvar u = 0; u < 3; u++) begin : g_add
            fp64_add u_add (
                .clk(clk), .rst_n(rst_n),
                .in_valid(add_valid[u]), .sub(add_sub[u]),
                .a(add_a[u*64 +: 64]), .b(add_b[u*64 +: 64]),
                .out_valid(add_ovalid[u]), .result(add_r[u*64 +: 64]), .flags(add_flags[u])
            );
            fp64_mul u_mul (
                .clk(clk), .rst_n(rst_n),
                .in_valid(mul_valid[u]),
                .a(mul_a[u*64 +: 64]), .b(mul_b[u*64 +: 64]),
                .out_valid(mul_ovalid[u]), .result(mul_r[u*64 +: 64]), .flags(mul_flags[u])
            );
        end
    endgenerate

    fp64_sqrt_srt u_sqrt (
        .clk(clk), .rst_n(rst_n),
        .in_valid(sqrt_valid), .a(sqrt_a),
        .out_valid(sqrt_ovalid), .result(sqrt_r), .flags(sqrt_flags)
    );

    fp64_rcp_nr u_rcp (
        .clk(clk), .rst_n(rst_n),
        .in_valid(rcp_valid), .a(rcp_a),
        .out_valid(rcp_ovalid), .result(rcp_r), .flags(rcp_flags)
    );

    // Valid-qualified sticky-flag aggregation (uArch §9): units assert flags only with out_valid.
    always_comb begin
        fp_flags_set = 4'b0000;
        for (int u = 0; u < 3; u++) begin
            fp_flags_set = fp_flags_set
                           | (add_ovalid[u] ? add_flags[u] : 4'b0000)
                           | (mul_ovalid[u] ? mul_flags[u] : 4'b0000);
        end
        fp_flags_set = fp_flags_set
                       | (sqrt_ovalid ? sqrt_flags : 4'b0000)
                       | (rcp_ovalid ? rcp_flags : 4'b0000);
    end

    // ---- datapath engines ----------------------------------------------------------------------
    logic [N_PAIRS_MAX*6*64-1:0] force_flat;           // Force terms
    logic [N_PAIRS_MAX-1:0]      force_ready;          // Per-pair ready

    grape_force_pipe #(
        .N_BODIES(N_BODIES), .N_PAIRS_MAX(N_PAIRS_MAX)
    ) u_force (
        .clk(clk), .rst_n(rst_n),
        .step_start_i(step_start), .run_i(run),
        .npairs_i(npairs), .pairs_i(pairs), .dt_i(dt), .working_flat_i(body_working),
        .add_valid_o(fp_add_valid), .add_sub_o(fp_add_sub), .add_a_o(fp_add_a), .add_b_o(fp_add_b),
        .add_ovalid_i(add_ovalid), .add_r_i(add_r),
        .mul_valid_o(fp_mul_valid), .mul_a_o(fp_mul_a), .mul_b_o(fp_mul_b),
        .mul_ovalid_i(mul_ovalid), .mul_r_i(mul_r),
        .sqrt_valid_o(sqrt_valid), .sqrt_a_o(sqrt_a),
        .sqrt_ovalid_i(sqrt_ovalid), .sqrt_r_i(sqrt_r),
        .rcp_valid_o(rcp_valid), .rcp_a_o(rcp_a),
        .rcp_ovalid_i(rcp_ovalid), .rcp_r_i(rcp_r),
        .add_free_o(add_free), .mul_free_o(mul_free),
        .force_flat_o(force_flat), .force_ready_o(force_ready)
    );

    grape_accum #(
        .N_BODIES(N_BODIES), .N_PAIRS_MAX(N_PAIRS_MAX)
    ) u_accum (
        .clk(clk), .rst_n(rst_n),
        .step_start_i(step_start), .run_i(run),
        .npairs_i(npairs), .pairs_i(pairs), .dt_i(dt), .working_flat_i(body_working),
        .force_flat_i(force_flat), .force_ready_i(force_ready),
        .add_free_i(add_free), .mul_free_i(mul_free),
        .add_valid_o(ac_add_valid), .add_sub_o(ac_add_sub), .add_a_o(ac_add_a), .add_b_o(ac_add_b),
        .add_ovalid_i(add_ovalid), .add_r_i(add_r),
        .mul_valid_o(ac_mul_valid), .mul_a_o(ac_mul_a), .mul_b_o(ac_mul_b),
        .mul_ovalid_i(mul_ovalid), .mul_r_i(mul_r),
        .wr_en_o(rf_wr_en), .wr_body_o(rf_wr_body), .wr_field_o(rf_wr_field),
        .wr_data_o(rf_wr_data),
        .all_done_o(all_done)
    );

endmodule

`default_nettype wire
