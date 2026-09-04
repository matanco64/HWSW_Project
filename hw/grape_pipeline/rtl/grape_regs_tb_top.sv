`default_nettype none

// Module: grape_regs_tb_top
// Purpose: TB-ONLY wrapper for unit.test_regs — NOT part of the synthesized design (excluded
//          from synthesis; the _tb_top suffix marks it). Instantiates the AXI4-Lite handshake
//          cell (axi_lite_if), the register decoder (grape_regs) and the body register file
//          (grape_body_rf) wired exactly as in the MAS (§4, §7): register bus between the
//          handshake cell and the decoder, pending body window -> body RF load at the accepted
//          doorbell, committed bank back to the decoder for the BUSY-time BODY window reads.
//          The step-FSM side (busy/done/aborted/fp flags/counters) and the body RF datapath
//          ports are exposed as top-level pins so the cocotb test can play the step FSM.
//          Wiring only — no logic.
module grape_regs_tb_top #(
    parameter int          N_BODIES    = 5,            // Bodies (PRD-F6)
    parameter int          N_PAIRS_MAX = 10,           // Pair-list capacity
    parameter logic [31:0] VERSION     = 32'd0         // VERSION register value
) (
    input  logic                      clk,             // System clock
    input  logic                      rst_n,           // Active-low synchronous reset
    // AXI4-Lite slave (driven by cocotbext-axi AxiLiteMaster)
    input  logic [11:0]               s_axi_awaddr,    // Write byte address
    input  logic [2:0]                s_axi_awprot,    // Ignored
    input  logic                      s_axi_awvalid,   // Write address valid
    output logic                      s_axi_awready,   // Write address ready
    input  logic [31:0]               s_axi_wdata,     // Write data
    input  logic [3:0]                s_axi_wstrb,     // Write byte strobes
    input  logic                      s_axi_wvalid,    // Write data valid
    output logic                      s_axi_wready,    // Write data ready
    output logic [1:0]                s_axi_bresp,     // Write response
    output logic                      s_axi_bvalid,    // Write response valid
    input  logic                      s_axi_bready,    // Write response ready
    input  logic [11:0]               s_axi_araddr,    // Read byte address
    input  logic [2:0]                s_axi_arprot,    // Ignored
    input  logic                      s_axi_arvalid,   // Read address valid
    output logic                      s_axi_arready,   // Read address ready
    output logic [31:0]               s_axi_rdata,     // Read data
    output logic [1:0]                s_axi_rresp,     // Read response
    output logic                      s_axi_rvalid,    // Read data valid
    input  logic                      s_axi_rready,    // Read data ready
    // Step-FSM side (driven by the test)
    input  logic                      busy_i,          // Step FSM busy
    input  logic                      done_set_i,      // DONE pulse
    input  logic                      aborted_set_i,   // ABORTED pulse
    input  logic [3:0]                fp_flags_set_i,  // {invalid, divzero, overflow, underflow}
    input  logic [31:0]               steps_done_i,    // Live steps counter
    input  logic [63:0]               cycles_i,        // Live busy-cycle counter
    // Body RF datapath write/commit side (driven by the test)
    input  logic                      bwr_en_i,        // Working-bank write enable
    input  logic [2:0]                bwr_body_i,      // Working-bank write body index
    input  logic [2:0]                bwr_field_i,     // Working-bank write field index (0..6)
    input  logic [63:0]               bwr_data_i,      // Working-bank write data
    input  logic                      commit_en_i,     // Commit pulse (working -> committed)
    // Body RF working bank (observable by the test)
    output logic [N_BODIES*7*64-1:0]  working_flat_o,  // Working bank, flattened
    // Decoder outputs (observable by the test)
    output logic                      doorbell_o,      // Accepted-doorbell pulse
    output logic                      abort_o,         // Abort request pulse
    output logic                      irq_o,           // Level IRQ
    output logic                      wr_resp_hold_o,  // BRESP hold (doorbell decision window)
    output logic [63:0]               dt_o,            // Latched DT
    output logic [31:0]               nsteps_o,        // Latched NSTEPS
    output logic [7:0]                npairs_o,        // Latched NPAIRS
    output logic [N_PAIRS_MAX*16-1:0] pairs_o          // Latched pair list
);

    // Register bus between the handshake cell and the decoder (MAS §4.1)
    logic                     req_wr;                  // One-cycle write pulse
    logic [9:0]               wr_addr;                 // Write word address
    logic [31:0]              wr_data;                 // Write data
    logic [3:0]               wr_strb;                 // Write byte strobes
    logic                     wr_err;                  // Write SLVERR
    logic                     req_rd;                  // One-cycle read pulse
    logic [9:0]               rd_addr;                 // Read word address
    logic [31:0]              rd_data;                 // Read data
    logic                     rd_err;                  // Read SLVERR

    // Body state exchange (MAS §4 pending/committed rules)
    logic [N_BODIES*7*64-1:0] body_pending;            // Pending window -> body RF load
    logic [N_BODIES*7*64-1:0] body_committed;          // Committed bank -> AXI read mux

    axi_lite_if #(
        .ADDR_W (12)
    ) u_axi_lite_if (
        .clk            (clk),
        .rst_n          (rst_n),
        .s_axi_awaddr   (s_axi_awaddr),
        .s_axi_awprot   (s_axi_awprot),
        .s_axi_awvalid  (s_axi_awvalid),
        .s_axi_awready  (s_axi_awready),
        .s_axi_wdata    (s_axi_wdata),
        .s_axi_wstrb    (s_axi_wstrb),
        .s_axi_wvalid   (s_axi_wvalid),
        .s_axi_wready   (s_axi_wready),
        .s_axi_bresp    (s_axi_bresp),
        .s_axi_bvalid   (s_axi_bvalid),
        .s_axi_bready   (s_axi_bready),
        .s_axi_araddr   (s_axi_araddr),
        .s_axi_arprot   (s_axi_arprot),
        .s_axi_arvalid  (s_axi_arvalid),
        .s_axi_arready  (s_axi_arready),
        .s_axi_rdata    (s_axi_rdata),
        .s_axi_rresp    (s_axi_rresp),
        .s_axi_rvalid   (s_axi_rvalid),
        .s_axi_rready   (s_axi_rready),
        .req_wr_o       (req_wr),
        .wr_addr_o      (wr_addr),
        .wr_data_o      (wr_data),
        .wr_strb_o      (wr_strb),
        .wr_err_i       (wr_err),
        .wr_resp_hold_i (wr_resp_hold_o),
        .req_rd_o       (req_rd),
        .rd_addr_o      (rd_addr),
        .rd_data_i      (rd_data),
        .rd_err_i       (rd_err)
    );

    grape_regs #(
        .N_BODIES    (N_BODIES),
        .N_PAIRS_MAX (N_PAIRS_MAX),
        .VERSION     (VERSION)
    ) u_grape_regs (
        .clk              (clk),
        .rst_n            (rst_n),
        .req_wr_i         (req_wr),
        .wr_addr_i        (wr_addr),
        .wr_data_i        (wr_data),
        .wr_strb_i        (wr_strb),
        .wr_err_o         (wr_err),
        .wr_resp_hold_o   (wr_resp_hold_o),
        .req_rd_i         (req_rd),
        .rd_addr_i        (rd_addr),
        .rd_data_o        (rd_data),
        .rd_err_o         (rd_err),
        .doorbell_o       (doorbell_o),
        .abort_o          (abort_o),
        .busy_i           (busy_i),
        .done_set_i       (done_set_i),
        .aborted_set_i    (aborted_set_i),
        .fp_flags_set_i   (fp_flags_set_i),
        .steps_done_i     (steps_done_i),
        .cycles_i         (cycles_i),
        .dt_o             (dt_o),
        .nsteps_o         (nsteps_o),
        .npairs_o         (npairs_o),
        .pairs_o          (pairs_o),
        .body_pending_o   (body_pending),
        .body_committed_i (body_committed),
        .irq_o            (irq_o)
    );

    grape_body_rf #(
        .N_BODIES (N_BODIES)
    ) u_grape_body_rf (
        .clk              (clk),
        .rst_n            (rst_n),
        .load_en_i        (doorbell_o),
        .load_flat_i      (body_pending),
        .working_flat_o   (working_flat_o),
        .wr_en_i          (bwr_en_i),
        .wr_body_i        (bwr_body_i),
        .wr_field_i       (bwr_field_i),
        .wr_data_i        (bwr_data_i),
        .commit_en_i      (commit_en_i),
        .committed_flat_o (body_committed)
    );

endmodule

`default_nettype wire
