`default_nettype none

// Module: axi_lite_if
// Purpose: AXI4-Lite slave handshake cell (grape MAS §4.1, ADR-0005). Converts the five AXI
//          channels into a simple register bus a per-module decoder implements:
//            - one-cycle req_wr_o pulse with wr_addr_o/wr_data_o/wr_strb_o; the decoder answers
//              on the NEXT cycle with wr_err_i (SLVERR) and may hold the write response with
//              wr_resp_hold_i (doorbell rule: BRESP only after STATUS shows accept/reject);
//            - one-cycle req_rd_o pulse with rd_addr_o; the decoder answers on the NEXT cycle
//              with rd_data_i/rd_err_i.
//          One outstanding transaction per direction; write wins arbitration (no simultaneous
//          pulses). Reset drops in-flight transactions (MAS §3).
module axi_lite_if #(
    parameter int ADDR_W = 12                          // Byte address width (4 KB window)
) (
    input  logic              clk,                     // System clock
    input  logic              rst_n,                   // Active-low synchronous reset
    // AXI4-Lite slave
    input  logic [ADDR_W-1:0] s_axi_awaddr,            // Write byte address
    input  logic [2:0]        s_axi_awprot,            // Ignored
    input  logic              s_axi_awvalid,           // Write address valid
    output logic              s_axi_awready,           // Write address ready
    input  logic [31:0]       s_axi_wdata,             // Write data
    input  logic [3:0]        s_axi_wstrb,             // Write byte strobes
    input  logic              s_axi_wvalid,            // Write data valid
    output logic              s_axi_wready,            // Write data ready
    output logic [1:0]        s_axi_bresp,             // Write response (OKAY/SLVERR)
    output logic              s_axi_bvalid,            // Write response valid
    input  logic              s_axi_bready,            // Write response ready
    input  logic [ADDR_W-1:0] s_axi_araddr,            // Read byte address
    input  logic [2:0]        s_axi_arprot,            // Ignored
    input  logic              s_axi_arvalid,           // Read address valid
    output logic              s_axi_arready,           // Read address ready
    output logic [31:0]       s_axi_rdata,             // Read data
    output logic [1:0]        s_axi_rresp,             // Read response
    output logic              s_axi_rvalid,            // Read data valid
    input  logic              s_axi_rready,            // Read data ready
    // Register bus (decoder side)
    output logic              req_wr_o,                // One-cycle write pulse
    output logic [ADDR_W-3:0] wr_addr_o,               // Write word address (byte addr >> 2)
    output logic [31:0]       wr_data_o,               // Write data
    output logic [3:0]        wr_strb_o,               // Write byte strobes
    input  logic              wr_err_i,                // SLVERR for the write (cycle after req_wr_o, held while hold)
    input  logic              wr_resp_hold_i,          // Hold BRESP (doorbell acceptance window)
    output logic              req_rd_o,                // One-cycle read pulse
    output logic [ADDR_W-3:0] rd_addr_o,               // Read word address
    input  logic [31:0]       rd_data_i,               // Read data (cycle after req_rd_o)
    input  logic              rd_err_i                 // SLVERR for the read
);

    localparam logic [1:0] RESP_OKAY   = 2'b00;        // AXI OKAY
    localparam logic [1:0] RESP_SLVERR = 2'b10;        // AXI SLVERR

    // Protection inputs are intentionally unused.
    /* verilator lint_off UNUSEDSIGNAL */
    logic [9:0] unused_bits;                           // Sink for aw/ar prot and byte-offset addr bits
    /* verilator lint_on UNUSEDSIGNAL */
    assign unused_bits = {s_axi_awprot, s_axi_arprot, s_axi_awaddr[1:0], s_axi_araddr[1:0]};

    // ---- write channel -------------------------------------------------------------------------
    typedef enum logic [1:0] {
        W_IDLE,                                        // Waiting for AW and W
        W_PULSE,                                       // req_wr_o this cycle
        W_WAIT,                                        // Decoder answered; waiting for !hold
        W_RESP                                         // bvalid asserted
    } wstate_t;

    wstate_t            wstate;                        // Write FSM state
    wstate_t            wstate_next;                   // Next write FSM state
    logic               aw_seen;                       // AW captured, waiting for W
    logic               aw_seen_next;                  // Next aw_seen
    logic               w_seen;                        // W captured, waiting for AW
    logic               w_seen_next;                   // Next w_seen
    logic [ADDR_W-3:0]  wr_addr_q;                     // Captured write word address
    logic [ADDR_W-3:0]  wr_addr_next;                  // Next captured write address
    logic [31:0]        wr_data_q;                     // Captured write data
    logic [31:0]        wr_data_next;                  // Next captured write data
    logic [3:0]         wr_strb_q;                     // Captured strobes
    logic [3:0]         wr_strb_next;                  // Next captured strobes
    logic               wr_err_q;                      // Latched write error
    logic               wr_err_next;                   // Next latched write error
    logic               aw_hs;                         // AW handshake this cycle
    logic               w_hs;                          // W handshake this cycle
    logic               wr_start;                      // Both halves available

    assign aw_hs    = s_axi_awvalid && s_axi_awready;
    assign w_hs     = s_axi_wvalid && s_axi_wready;
    assign wr_start = (aw_seen || aw_hs) && (w_seen || w_hs);

    always_comb begin
        wstate_next   = wstate;
        aw_seen_next  = aw_seen;
        w_seen_next   = w_seen;
        wr_addr_next  = wr_addr_q;
        wr_data_next  = wr_data_q;
        wr_strb_next  = wr_strb_q;
        wr_err_next   = wr_err_q;
        if (aw_hs) begin
            wr_addr_next = s_axi_awaddr[ADDR_W-1:2];
            aw_seen_next = 1'b1;
        end
        if (w_hs) begin
            wr_data_next = s_axi_wdata;
            wr_strb_next = s_axi_wstrb;
            w_seen_next  = 1'b1;
        end
        case (wstate)
            W_IDLE: begin
                if (wr_start) begin
                    wstate_next = W_PULSE;
                end
            end
            W_PULSE: begin
                wstate_next = W_WAIT;                  // Decoder answers next cycle
            end
            W_WAIT: begin
                wr_err_next = wr_err_i;
                if (!wr_resp_hold_i) begin
                    wstate_next = W_RESP;
                end
            end
            W_RESP: begin
                if (s_axi_bready) begin
                    wstate_next  = W_IDLE;
                    aw_seen_next = 1'b0;
                    w_seen_next  = 1'b0;
                end
            end
            default: begin
                wstate_next = W_IDLE;
            end
        endcase
        if (!rst_n) begin
            wstate_next  = W_IDLE;
            aw_seen_next = 1'b0;
            w_seen_next  = 1'b0;
            wr_err_next  = 1'b0;
        end
    end

    always_ff @(posedge clk) begin
        wstate    <= wstate_next;
        aw_seen   <= aw_seen_next;
        w_seen    <= w_seen_next;
        wr_addr_q <= wr_addr_next;
        wr_data_q <= wr_data_next;
        wr_strb_q <= wr_strb_next;
        wr_err_q  <= wr_err_next;
    end

    assign s_axi_awready = (wstate == W_IDLE) && !aw_seen;
    assign s_axi_wready  = (wstate == W_IDLE) && !w_seen;
    assign s_axi_bvalid  = (wstate == W_RESP);
    assign s_axi_bresp   = wr_err_q ? RESP_SLVERR : RESP_OKAY;
    assign req_wr_o      = (wstate == W_PULSE);
    assign wr_addr_o     = wr_addr_q;
    assign wr_data_o     = wr_data_q;
    assign wr_strb_o     = wr_strb_q;

    // ---- read channel --------------------------------------------------------------------------
    typedef enum logic [1:0] {
        R_IDLE,                                        // Waiting for AR
        R_PULSE,                                       // req_rd_o this cycle
        R_CAPT,                                        // Capture decoder answer
        R_RESP                                         // rvalid asserted
    } rstate_t;

    rstate_t           rstate;                         // Read FSM state
    rstate_t           rstate_next;                    // Next read FSM state
    logic [ADDR_W-3:0] rd_addr_q;                      // Captured read word address
    logic [ADDR_W-3:0] rd_addr_next;                   // Next captured read address
    logic [31:0]       rd_data_q;                      // Captured read data
    logic [31:0]       rd_data_next;                   // Next captured read data
    logic              rd_err_q;                       // Captured read error
    logic              rd_err_next;                    // Next captured read error

    always_comb begin
        rstate_next  = rstate;
        rd_addr_next = rd_addr_q;
        rd_data_next = rd_data_q;
        rd_err_next  = rd_err_q;
        case (rstate)
            R_IDLE: begin
                if (s_axi_arvalid) begin
                    rd_addr_next = s_axi_araddr[ADDR_W-1:2];
                    rstate_next  = R_PULSE;
                end
            end
            R_PULSE: begin
                rstate_next = R_CAPT;
            end
            R_CAPT: begin
                rd_data_next = rd_data_i;
                rd_err_next  = rd_err_i;
                rstate_next  = R_RESP;
            end
            R_RESP: begin
                if (s_axi_rready) begin
                    rstate_next = R_IDLE;
                end
            end
            default: begin
                rstate_next = R_IDLE;
            end
        endcase
        if (!rst_n) begin
            rstate_next = R_IDLE;
            rd_err_next = 1'b0;
        end
    end

    always_ff @(posedge clk) begin
        rstate    <= rstate_next;
        rd_addr_q <= rd_addr_next;
        rd_data_q <= rd_data_next;
        rd_err_q  <= rd_err_next;
    end

    assign s_axi_arready = (rstate == R_IDLE);
    assign s_axi_rvalid  = (rstate == R_RESP);
    assign s_axi_rdata   = rd_data_q;
    assign s_axi_rresp   = rd_err_q ? RESP_SLVERR : RESP_OKAY;
    assign req_rd_o      = (rstate == R_PULSE);
    assign rd_addr_o     = rd_addr_q;

endmodule

`default_nettype wire
