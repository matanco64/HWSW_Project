`default_nettype none

// Module: pyflate_accel
// Purpose: Thin chain wrapper (huffman_engine MAS §1 / mtf_cam MAS §1): both modules on ONE
//          clock and reset, no CDC, huffman_engine.m_sym wired directly to mtf_cam.s_sym
//          (ADR-0006 beats). Each module keeps its own AXI4-Lite slave (h_* / m_*); the
//          compressed-bit and selector streams enter huffman_engine, the L-vector leaves
//          mtf_cam on m_l. No logic of its own.
module pyflate_accel #(
    parameter int          W       = 8,              // mtf_cam output lanes (bytes/beat)
    parameter logic [31:0] VERSION = 32'd0           // git short SHA (both modules)
) (
    input  logic            clk,                     // Shared system clock
    input  logic            rst_n,                   // Shared active-low synchronous reset
    // huffman_engine AXI4-Lite slave
    input  logic [11:0]     h_axi_awaddr,
    input  logic [2:0]      h_axi_awprot,
    input  logic            h_axi_awvalid,
    output logic            h_axi_awready,
    input  logic [31:0]     h_axi_wdata,
    input  logic [3:0]      h_axi_wstrb,
    input  logic            h_axi_wvalid,
    output logic            h_axi_wready,
    output logic [1:0]      h_axi_bresp,
    output logic            h_axi_bvalid,
    input  logic            h_axi_bready,
    input  logic [11:0]     h_axi_araddr,
    input  logic [2:0]      h_axi_arprot,
    input  logic            h_axi_arvalid,
    output logic            h_axi_arready,
    output logic [31:0]     h_axi_rdata,
    output logic [1:0]      h_axi_rresp,
    output logic            h_axi_rvalid,
    input  logic            h_axi_rready,
    // mtf_cam AXI4-Lite slave
    input  logic [11:0]     m_axi_awaddr,
    input  logic [2:0]      m_axi_awprot,
    input  logic            m_axi_awvalid,
    output logic            m_axi_awready,
    input  logic [31:0]     m_axi_wdata,
    input  logic [3:0]      m_axi_wstrb,
    input  logic            m_axi_wvalid,
    output logic            m_axi_wready,
    output logic [1:0]      m_axi_bresp,
    output logic            m_axi_bvalid,
    input  logic            m_axi_bready,
    input  logic [11:0]     m_axi_araddr,
    input  logic [2:0]      m_axi_arprot,
    input  logic            m_axi_arvalid,
    output logic            m_axi_arready,
    output logic [31:0]     m_axi_rdata,
    output logic [1:0]      m_axi_rresp,
    output logic            m_axi_rvalid,
    input  logic            m_axi_rready,
    // Compressed bit stream in (huffman_engine s_bits)
    input  logic [31:0]     s_axis_bits_tdata,
    input  logic [3:0]      s_axis_bits_tkeep,
    input  logic            s_axis_bits_tlast,
    input  logic            s_axis_bits_tvalid,
    output logic            s_axis_bits_tready,
    // Selector stream in (huffman_engine s_sel)
    input  logic [7:0]      s_axis_sel_tdata,
    input  logic            s_axis_sel_tlast,
    input  logic            s_axis_sel_tvalid,
    output logic            s_axis_sel_tready,
    // L-vector bytes out (mtf_cam m_l)
    output logic [8*W-1:0]  m_axis_l_tdata,
    output logic [W-1:0]    m_axis_l_tkeep,
    output logic            m_axis_l_tvalid,
    input  logic            m_axis_l_tready,
    output logic            m_axis_l_tlast,
    // Interrupts
    output logic            h_irq,                   // huffman_engine level IRQ
    output logic            m_irq                    // mtf_cam level IRQ
);

    // ---- the chain link: huffman_engine.m_sym -> mtf_cam.s_sym --------------------------------
    logic [31:0] sym_tdata;                          // ADR-0006 symbol beat
    logic        sym_tlast;                          // EOB beat
    logic        sym_tvalid;                         // Beat valid
    logic        sym_tready;                         // Beat ready

    huffman_engine #(
        .VERSION(VERSION)
    ) u_huff (
        .clk(clk), .rst_n(rst_n),
        .s_axi_awaddr(h_axi_awaddr), .s_axi_awprot(h_axi_awprot),
        .s_axi_awvalid(h_axi_awvalid), .s_axi_awready(h_axi_awready),
        .s_axi_wdata(h_axi_wdata), .s_axi_wstrb(h_axi_wstrb),
        .s_axi_wvalid(h_axi_wvalid), .s_axi_wready(h_axi_wready),
        .s_axi_bresp(h_axi_bresp), .s_axi_bvalid(h_axi_bvalid), .s_axi_bready(h_axi_bready),
        .s_axi_araddr(h_axi_araddr), .s_axi_arprot(h_axi_arprot),
        .s_axi_arvalid(h_axi_arvalid), .s_axi_arready(h_axi_arready),
        .s_axi_rdata(h_axi_rdata), .s_axi_rresp(h_axi_rresp),
        .s_axi_rvalid(h_axi_rvalid), .s_axi_rready(h_axi_rready),
        .s_axis_bits_tdata(s_axis_bits_tdata), .s_axis_bits_tkeep(s_axis_bits_tkeep),
        .s_axis_bits_tlast(s_axis_bits_tlast), .s_axis_bits_tvalid(s_axis_bits_tvalid),
        .s_axis_bits_tready(s_axis_bits_tready),
        .s_axis_sel_tdata(s_axis_sel_tdata), .s_axis_sel_tlast(s_axis_sel_tlast),
        .s_axis_sel_tvalid(s_axis_sel_tvalid), .s_axis_sel_tready(s_axis_sel_tready),
        .m_axis_sym_tdata(sym_tdata), .m_axis_sym_tlast(sym_tlast),
        .m_axis_sym_tvalid(sym_tvalid), .m_axis_sym_tready(sym_tready),
        .irq(h_irq)
    );

    mtf_cam #(
        .W(W), .VERSION(VERSION)
    ) u_mtf (
        .clk(clk), .rst_n(rst_n),
        .s_axi_awaddr(m_axi_awaddr), .s_axi_awprot(m_axi_awprot),
        .s_axi_awvalid(m_axi_awvalid), .s_axi_awready(m_axi_awready),
        .s_axi_wdata(m_axi_wdata), .s_axi_wstrb(m_axi_wstrb),
        .s_axi_wvalid(m_axi_wvalid), .s_axi_wready(m_axi_wready),
        .s_axi_bresp(m_axi_bresp), .s_axi_bvalid(m_axi_bvalid), .s_axi_bready(m_axi_bready),
        .s_axi_araddr(m_axi_araddr), .s_axi_arprot(m_axi_arprot),
        .s_axi_arvalid(m_axi_arvalid), .s_axi_arready(m_axi_arready),
        .s_axi_rdata(m_axi_rdata), .s_axi_rresp(m_axi_rresp),
        .s_axi_rvalid(m_axi_rvalid), .s_axi_rready(m_axi_rready),
        .s_axis_sym_tdata(sym_tdata), .s_axis_sym_tvalid(sym_tvalid),
        .s_axis_sym_tready(sym_tready), .s_axis_sym_tlast(sym_tlast),
        .m_axis_l_tdata(m_axis_l_tdata), .m_axis_l_tkeep(m_axis_l_tkeep),
        .m_axis_l_tvalid(m_axis_l_tvalid), .m_axis_l_tready(m_axis_l_tready),
        .m_axis_l_tlast(m_axis_l_tlast),
        .irq(m_irq)
    );

endmodule

`default_nettype wire
