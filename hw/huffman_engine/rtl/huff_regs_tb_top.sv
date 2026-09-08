`default_nettype none

// Module: huff_regs_tb_top
// Purpose: TB-ONLY wrapper for unit.test_regs — NOT part of the synthesized design (excluded
//          from synthesis; the _tb_top suffix marks it). Instantiates the AXI4-Lite handshake
//          cell (axi_lite_if) and the register decoder (huff_regs) wired exactly as in the MAS
//          (§4): register bus between the handshake cell and the decoder. The core-FSM side
//          (busy/done/aborted/err pulses, live counters, DBG data) and the builder read ports
//          (lengths_rd, counts_rd) are exposed as top-level pins so the cocotb test can play
//          the core and verify the folded count bins directly. Wiring only — no logic.
module huff_regs_tb_top #(
    parameter logic [31:0] VERSION = 32'd0             // VERSION register value
) (
    input  logic        clk,                           // System clock
    input  logic        rst_n,                         // Active-low synchronous reset
    // AXI4-Lite slave (driven by cocotbext-axi AxiLiteMaster)
    input  logic [11:0] s_axi_awaddr,                  // Write byte address
    input  logic [2:0]  s_axi_awprot,                  // Ignored
    input  logic        s_axi_awvalid,                 // Write address valid
    output logic        s_axi_awready,                 // Write address ready
    input  logic [31:0] s_axi_wdata,                   // Write data
    input  logic [3:0]  s_axi_wstrb,                   // Write byte strobes
    input  logic        s_axi_wvalid,                  // Write data valid
    output logic        s_axi_wready,                  // Write data ready
    output logic [1:0]  s_axi_bresp,                   // Write response
    output logic        s_axi_bvalid,                  // Write response valid
    input  logic        s_axi_bready,                  // Write response ready
    input  logic [11:0] s_axi_araddr,                  // Read byte address
    input  logic [2:0]  s_axi_arprot,                  // Ignored
    input  logic        s_axi_arvalid,                 // Read address valid
    output logic        s_axi_arready,                 // Read address ready
    output logic [31:0] s_axi_rdata,                   // Read data
    output logic [1:0]  s_axi_rresp,                   // Read response
    output logic        s_axi_rvalid,                  // Read data valid
    input  logic        s_axi_rready,                  // Read data ready
    // Core-FSM side (driven by the test)
    input  logic        busy_i,                        // Core FSM busy
    input  logic        done_set_i,                    // DONE pulse
    input  logic        aborted_set_i,                 // ABORTED pulse
    input  logic [6:0]  err_set_i,                     // Error pulses -> STATUS bits 15:9
    input  logic [63:0] cycles_i,                      // Live busy-cycle counter
    input  logic [31:0] symbols_i,                     // Live m_sym beat counter
    input  logic [31:0] bits_i,                        // Live bits-consumed counter
    input  logic [15:0] build_cycles_i,                // Live longest-build counter
    input  logic [7:0]  overfetch_i,                   // Live overfetch counter
    input  logic [31:0] dbg_data_i,                    // DBG_DATA source (huff_tables in the design)
    // Builder read ports (driven/checked by the test)
    input  logic [11:0] lengths_rd_addr_i,             // {table[2:0], sym[8:0]}
    output logic [4:0]  lengths_rd_data_o,             // Length of (t, sym), 1-cycle
    input  logic [2:0]  counts_rd_table_i,             // Count-bin table select
    input  logic [4:0]  counts_rd_len_i,               // Count-bin length select (1..20)
    output logic [8:0]  counts_rd_data_o,              // count[t][l], combinational
    // Decoder outputs (observable by the test)
    output logic        doorbell_o,                    // Accepted-doorbell pulse
    output logic        abort_o,                       // Abort request pulse
    output logic        irq_o,                         // Level IRQ
    output logic        wr_resp_hold_o,                // BRESP hold (doorbell decision window)
    output logic [2:0]  dbg_table_o,                   // DBG_SEL table field
    output logic [1:0]  dbg_kind_o,                    // DBG_SEL kind field
    output logic [8:0]  dbg_index_o,                   // DBG_SEL index field
    output logic        cfg_mode_o,                    // Latched MODE
    output logic [31:0] cfg_start_bit_o,               // Latched START_BIT
    output logic [8:0]  cfg_alphabet_o,                // Latched ALPHABET
    output logic [2:0]  cfg_n_tables_o,                // Latched N_TABLES
    output logic [31:0] cfg_symbol_limit_o             // Latched SYMBOL_LIMIT
);

    // Register bus between the handshake cell and the decoder (grape MAS §4.1 pattern)
    logic        req_wr;                               // One-cycle write pulse
    logic [9:0]  wr_addr;                              // Write word address
    logic [31:0] wr_data;                              // Write data
    logic [3:0]  wr_strb;                              // Write byte strobes
    logic        wr_err;                               // Write SLVERR
    logic        req_rd;                               // One-cycle read pulse
    logic [9:0]  rd_addr;                              // Read word address
    logic [31:0] rd_data;                              // Read data
    logic        rd_err;                               // Read SLVERR

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

    huff_regs #(
        .VERSION (VERSION)
    ) u_huff_regs (
        .clk                (clk),
        .rst_n              (rst_n),
        .req_wr_i           (req_wr),
        .wr_addr_i          (wr_addr),
        .wr_data_i          (wr_data),
        .wr_strb_i          (wr_strb),
        .wr_err_o           (wr_err),
        .wr_resp_hold_o     (wr_resp_hold_o),
        .req_rd_i           (req_rd),
        .rd_addr_i          (rd_addr),
        .rd_data_o          (rd_data),
        .rd_err_o           (rd_err),
        .doorbell_o         (doorbell_o),
        .abort_o            (abort_o),
        .busy_i             (busy_i),
        .done_set_i         (done_set_i),
        .aborted_set_i      (aborted_set_i),
        .err_set_i          (err_set_i),
        .cycles_i           (cycles_i),
        .symbols_i          (symbols_i),
        .bits_i             (bits_i),
        .build_cycles_i     (build_cycles_i),
        .overfetch_i        (overfetch_i),
        .dbg_data_i         (dbg_data_i),
        .dbg_table_o        (dbg_table_o),
        .dbg_kind_o         (dbg_kind_o),
        .dbg_index_o        (dbg_index_o),
        .cfg_mode_o         (cfg_mode_o),
        .cfg_start_bit_o    (cfg_start_bit_o),
        .cfg_alphabet_o     (cfg_alphabet_o),
        .cfg_n_tables_o     (cfg_n_tables_o),
        .cfg_symbol_limit_o (cfg_symbol_limit_o),
        .lengths_rd_addr_i  (lengths_rd_addr_i),
        .lengths_rd_data_o  (lengths_rd_data_o),
        .counts_rd_table_i  (counts_rd_table_i),
        .counts_rd_len_i    (counts_rd_len_i),
        .counts_rd_data_o   (counts_rd_data_o),
        .irq_o              (irq_o)
    );

endmodule

`default_nettype wire
