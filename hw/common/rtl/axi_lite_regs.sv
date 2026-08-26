`default_nettype none

// Module: axi_lite_regs
// Purpose: Minimal AXI4-Lite slave exposing NUM_REGS 32-bit registers at
//          consecutive word offsets. Register values are output flattened
//          (regs_o), software writes raise wr_strobe_o for one cycle and reads
//          raise rd_strobe_o. Hardware may overwrite a register through
//          hw_wr_en_i/hw_wr_data_i (hardware wins over a simultaneous bus write).
//          Out-of-range accesses complete with SLVERR. Signal names follow the
//          cocotbext-axi `s_axi_*` prefix convention.
module axi_lite_regs #(
    parameter int NUM_REGS = 4,                        // Number of 32-bit registers
    parameter int ADDR_W   = 8                         // Byte address width
) (
    input  logic                   clk,                // System clock
    input  logic                   rst_n,              // Active-low synchronous reset
    // Write address channel
    input  logic [ADDR_W-1:0]      s_axi_awaddr,       // Write byte address
    input  logic [2:0]             s_axi_awprot,       // Write protection (ignored)
    input  logic                   s_axi_awvalid,      // Write address valid
    output logic                   s_axi_awready,      // Write address ready
    // Write data channel
    input  logic [31:0]            s_axi_wdata,        // Write data
    input  logic [3:0]             s_axi_wstrb,        // Write byte strobes
    input  logic                   s_axi_wvalid,       // Write data valid
    output logic                   s_axi_wready,       // Write data ready
    // Write response channel
    output logic [1:0]             s_axi_bresp,        // Write response (OKAY/SLVERR)
    output logic                   s_axi_bvalid,       // Write response valid
    input  logic                   s_axi_bready,       // Write response ready
    // Read address channel
    input  logic [ADDR_W-1:0]      s_axi_araddr,       // Read byte address
    input  logic [2:0]             s_axi_arprot,       // Read protection (ignored)
    input  logic                   s_axi_arvalid,      // Read address valid
    output logic                   s_axi_arready,      // Read address ready
    // Read data channel
    output logic [31:0]            s_axi_rdata,        // Read data
    output logic [1:0]             s_axi_rresp,        // Read response (OKAY/SLVERR)
    output logic                   s_axi_rvalid,       // Read data valid
    input  logic                   s_axi_rready,       // Read data ready
    // Register side
    output logic [NUM_REGS*32-1:0] regs_o,             // Current register values, reg i at [32*i +: 32]
    output logic [NUM_REGS-1:0]    wr_strobe_o,        // One-cycle pulse per software write
    output logic [NUM_REGS-1:0]    rd_strobe_o,        // One-cycle pulse per software read
    input  logic [NUM_REGS-1:0]    hw_wr_en_i,         // Hardware write enable per register
    input  logic [NUM_REGS*32-1:0] hw_wr_data_i        // Hardware write data, flattened
);

    localparam logic [1:0] RESP_OKAY   = 2'b00;         // AXI OKAY response
    localparam logic [1:0] RESP_SLVERR = 2'b10;         // AXI SLVERR response
    localparam int         IDX_W       = (NUM_REGS > 1) ? $clog2(NUM_REGS) : 1;  // Register index width

    // Protection bits and byte-offset address bits are intentionally unused.
    /* verilator lint_off UNUSEDSIGNAL */
    logic [4:0] unused_bits;                            // Sink for awprot/arprot/addr[1:0]
    /* verilator lint_on UNUSEDSIGNAL */
    assign unused_bits = {s_axi_awprot | s_axi_arprot, s_axi_awaddr[1:0] | s_axi_araddr[1:0]};

    logic [31:0]           regs [NUM_REGS];             // Register storage
    logic [31:0]           regs_next [NUM_REGS];        // Next register values

    logic                  aw_captured;                 // Write address latched
    logic [ADDR_W-1:0]     aw_addr;                     // Latched write address
    logic                  w_captured;                  // Write data latched
    logic [31:0]           w_data;                      // Latched write data
    logic [3:0]            w_strb;                      // Latched write strobes
    logic                  aw_captured_next;            // Next aw_captured
    logic [ADDR_W-1:0]     aw_addr_next;                // Next aw_addr
    logic                  w_captured_next;             // Next w_captured
    logic [31:0]           w_data_next;                 // Next w_data
    logic [3:0]            w_strb_next;                 // Next w_strb
    logic                  bvalid_next;                 // Next s_axi_bvalid
    logic [1:0]            bresp_next;                  // Next s_axi_bresp
    logic                  rvalid_next;                 // Next s_axi_rvalid
    logic [31:0]           rdata_next;                  // Next s_axi_rdata
    logic [1:0]            rresp_next;                  // Next s_axi_rresp
    logic [NUM_REGS-1:0]   wr_strobe_next;              // Next wr_strobe_o
    logic [NUM_REGS-1:0]   rd_strobe_next;              // Next rd_strobe_o

    logic                  do_write;                    // Both write halves present, response slot free
    logic                  wr_in_range;                 // Write address decodes to a register
    logic                  rd_in_range;                 // Read address decodes to a register
    logic [ADDR_W-1:0]     wr_word;                     // Write address >> 2
    logic [ADDR_W-1:0]     rd_word;                     // Read address >> 2
    logic [IDX_W-1:0]      wr_idx;                      // Write register index
    logic [IDX_W-1:0]      rd_idx;                      // Read register index
    logic                  ar_fire;                     // Read address handshake

    always_comb begin
        // Address decode
        wr_word     = {2'b00, aw_addr[ADDR_W-1:2]};
        rd_word     = {2'b00, s_axi_araddr[ADDR_W-1:2]};
        wr_in_range = (wr_word < ADDR_W'(NUM_REGS));
        rd_in_range = (rd_word < ADDR_W'(NUM_REGS));
        wr_idx      = wr_word[IDX_W-1:0];
        rd_idx      = rd_word[IDX_W-1:0];

        // Write channel: accept AW and W independently, respond once both are held.
        s_axi_awready    = ~aw_captured;
        s_axi_wready     = ~w_captured;
        do_write         = aw_captured & w_captured & (~s_axi_bvalid | s_axi_bready);
        aw_captured_next = aw_captured;
        aw_addr_next     = aw_addr;
        w_captured_next  = w_captured;
        w_data_next      = w_data;
        w_strb_next      = w_strb;
        bvalid_next      = s_axi_bvalid & ~s_axi_bready;
        bresp_next       = s_axi_bresp;
        wr_strobe_next   = '0;

        if (s_axi_awvalid & s_axi_awready) begin
            aw_captured_next = 1'b1;
            aw_addr_next     = s_axi_awaddr;
        end
        if (s_axi_wvalid & s_axi_wready) begin
            w_captured_next = 1'b1;
            w_data_next     = s_axi_wdata;
            w_strb_next     = s_axi_wstrb;
        end
        if (do_write) begin
            aw_captured_next = 1'b0;
            w_captured_next  = 1'b0;
            bvalid_next      = 1'b1;
            bresp_next       = wr_in_range ? RESP_OKAY : RESP_SLVERR;
            if (wr_in_range) begin
                wr_strobe_next[wr_idx] = 1'b1;
            end
        end

        // Read channel: single outstanding read, data registered.
        s_axi_arready  = ~s_axi_rvalid | s_axi_rready;
        ar_fire        = s_axi_arvalid & s_axi_arready;
        rvalid_next    = s_axi_rvalid & ~s_axi_rready;
        rdata_next     = s_axi_rdata;
        rresp_next     = s_axi_rresp;
        rd_strobe_next = '0;
        if (ar_fire) begin
            rvalid_next = 1'b1;
            rresp_next  = rd_in_range ? RESP_OKAY : RESP_SLVERR;
            rdata_next  = rd_in_range ? regs[rd_idx] : 32'h0000_0000;
            if (rd_in_range) begin
                rd_strobe_next[rd_idx] = 1'b1;
            end
        end

        // Register next-state: software write with byte strobes, hardware write overrides.
        for (int i = 0; i < NUM_REGS; i++) begin
            regs_next[i] = regs[i];
            if (do_write && wr_in_range && (wr_idx == IDX_W'(i))) begin
                for (int b = 0; b < 4; b++) begin
                    if (w_strb[b]) begin
                        regs_next[i][8*b +: 8] = w_data[8*b +: 8];
                    end
                end
            end
            if (hw_wr_en_i[i]) begin
                regs_next[i] = hw_wr_data_i[32*i +: 32];
            end
            regs_o[32*i +: 32] = regs[i];
        end
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            aw_captured  <= 1'b0;
            w_captured   <= 1'b0;
            s_axi_bvalid <= 1'b0;
            s_axi_bresp  <= RESP_OKAY;
            s_axi_rvalid <= 1'b0;
            s_axi_rresp  <= RESP_OKAY;
            s_axi_rdata  <= 32'h0000_0000;
            wr_strobe_o  <= '0;
            rd_strobe_o  <= '0;
        end else begin
            aw_captured  <= aw_captured_next;
            w_captured   <= w_captured_next;
            s_axi_bvalid <= bvalid_next;
            s_axi_bresp  <= bresp_next;
            s_axi_rvalid <= rvalid_next;
            s_axi_rresp  <= rresp_next;
            s_axi_rdata  <= rdata_next;
            wr_strobe_o  <= wr_strobe_next;
            rd_strobe_o  <= rd_strobe_next;
        end
    end

    always_ff @(posedge clk) begin
        aw_addr <= aw_addr_next;
        w_data  <= w_data_next;
        w_strb  <= w_strb_next;
    end

    // Register array reset is unrolled so Yosys infers plain flops (no memory).
    always_ff @(posedge clk) begin
        for (int i = 0; i < NUM_REGS; i++) begin
            if (!rst_n) begin
                regs[i] <= 32'h0000_0000;
            end else begin
                regs[i] <= regs_next[i];
            end
        end
    end

endmodule

`default_nettype wire
