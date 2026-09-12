`default_nettype none

// Module: mtf_regs
// Purpose: AXI-Lite register decoder behind axi_lite_if (MAS §4, ADR-0005). Implements the ID/
//          VERSION/CTRL/STATUS/IRQ header, the read-only counters, the used map (8 words) and
//          SYMBOL_LIMIT/BYTES_LIMIT/CAPS/DBG_SEL/DBG_DATA, reserved RAZ/WI ranges and SLVERR for
//          unmapped words. Configuration is a single stored copy: writes while BUSY are ignored
//          with ERR_BUSY, so the value is frozen (== latched) for the whole invocation. The
//          doorbell-time ERR_PARAM check (F9) runs the cycle after the CTRL write with BRESP held
//          (<= 8 cycles). STATUS sticky bits are W1C; a doorbell clears none.
module mtf_regs #(
    parameter int          W       = 8,              // Output lanes (CAPS[7:0])
    parameter int          D       = 8,              // Item-FIFO depth (CAPS[15:8])
    parameter int          N_LIST  = 256,            // List capacity (CAPS[24:16])
    parameter logic [31:0] VERSION = 32'd0           // git short SHA (synthesis parameter)
) (
    input  logic         clk,                        // System clock
    input  logic         rst_n,                      // Active-low synchronous reset
    // Register bus (axi_lite_if)
    input  logic         req_wr_i,                   // Write pulse
    input  logic [9:0]   wr_addr_i,                  // Write word address
    input  logic [31:0]  wr_data_i,                  // Write data
    input  logic [3:0]   wr_strb_i,                  // Byte strobes
    output logic         wr_err_o,                   // SLVERR (cycle after req_wr_i)
    output logic         wr_resp_hold_o,             // Hold BRESP during the doorbell decision
    input  logic         req_rd_i,                   // Read pulse
    input  logic [9:0]   rd_addr_i,                  // Read word address
    output logic [31:0]  rd_data_o,                  // Read data (cycle after req_rd_i)
    output logic         rd_err_o,                   // SLVERR
    // Control exchange with the invocation FSM
    output logic         doorbell_o,                 // Accepted-doorbell pulse
    output logic         abort_o,                    // Abort request pulse
    input  logic         busy_i,                     // FSM busy
    input  logic         done_set_i,                 // DONE pulse
    input  logic         aborted_set_i,              // ABORTED pulse
    input  logic         err_rank_i,                 // ERR_RANK pulse
    input  logic         err_run_i,                  // ERR_RUN pulse
    input  logic         err_limit_i,                // ERR_LIMIT pulse
    input  logic         err_underrun_i,             // ERR_UNDERRUN pulse
    // Live counters (owned by the top)
    input  logic [63:0]  cycles_i,                   // CYCLES
    input  logic [31:0]  symbols_in_i,               // SYMBOLS_IN
    input  logic [31:0]  bytes_out_i,                // BYTES_OUT
    input  logic [8:0]   init_cycles_i,              // INIT_CYCLES
    input  logic [20:0]  max_run_i,                  // MAX_RUN
    // Configuration (single stored copy, frozen while BUSY)
    output logic [N_LIST-1:0] used_map_o,            // Used map (byte b present iff bit b)
    output logic [31:0]  symbol_limit_o,             // SYMBOL_LIMIT
    output logic [31:0]  bytes_limit_o,              // BYTES_LIMIT
    output logic [7:0]   dbg_sel_o,                  // DBG_SEL (rank)
    input  logic [7:0]   dbg_data_i,                 // DBG_DATA (live list byte)
    // Interrupt
    output logic         irq_o                        // Level IRQ (registered)
);

    localparam logic [31:0] ID_VALUE   = 32'h4D54_4631;  // ASCII "MTF1"
    localparam logic [13:0] IRQEN_MASK = 14'h3F06;       // Writable IRQ_EN bits {13:8, 2:1}
    localparam logic [31:0] SYM_MAX    = 32'h0800_0000;  // 2^27
    localparam logic [31:0] BYT_MAX    = 32'h4000_0000;  // 2^30

    // STATUS sticky bit positions (MAS §4)
    localparam int B_DONE  = 1;                          // DONE
    localparam int B_ABRT  = 2;                          // ABORTED
    localparam int B_EBSY  = 8;                          // ERR_BUSY
    localparam int B_EPRM  = 9;                          // ERR_PARAM
    localparam int B_ERNK  = 10;                         // ERR_RANK
    localparam int B_ERUN  = 11;                         // ERR_RUN
    localparam int B_ELIM  = 12;                         // ERR_LIMIT
    localparam int B_EUNR  = 13;                         // ERR_UNDERRUN

    // ---- storage -------------------------------------------------------------------------------
    logic [N_LIST-1:0] used_q;                           // Used map
    logic [31:0]       sym_lim_q;                        // SYMBOL_LIMIT
    logic [31:0]       byt_lim_q;                        // BYTES_LIMIT
    logic [7:0]        dbg_sel_q;                        // DBG_SEL
    logic [13:0]       sticky_q;                         // STATUS sticky (bits per B_* above)
    logic [13:0]       irq_en_q;                         // IRQ_EN mask
    logic              irq_q;                            // Registered IRQ
    logic              db_pending_q;                     // Doorbell decision window (this cycle)
    logic              db_hold_q;                        // BRESP hold flag

    logic [N_LIST-1:0] used_n;                           // Next used map
    logic [31:0]       sym_lim_n;                        // Next SYMBOL_LIMIT
    logic [31:0]       byt_lim_n;                        // Next BYTES_LIMIT
    logic [7:0]        dbg_sel_n;                        // Next DBG_SEL
    logic [13:0]       sticky_n;                         // Next sticky
    logic [13:0]       irq_en_n;                         // Next IRQ_EN
    logic              irq_n;                            // Next IRQ
    logic              db_pending_n;                     // Next decision window
    logic              db_hold_n;                        // Next hold
    logic              doorbell_n;                       // Next doorbell pulse
    logic              abort_n;                          // Next abort pulse
    logic              wr_err_n;                         // Next write SLVERR
    logic [31:0]       rd_data_n;                        // Next read data
    logic              rd_err_n;                         // Next read SLVERR

    // verilator lint_off UNUSEDSIGNAL
    logic [31:0] cfg_tmp;                                // apply_strb temp (upper/other bits unused)
    logic [31:0] w1c_tmp;                                // apply_strb temp
    logic [31:0] irqen_tmp;                              // apply_strb temp
    // verilator lint_on UNUSEDSIGNAL

    // ---- doorbell-time ERR_PARAM (combinational over the stored config) -------------------------
    logic err_param;                                     // Doorbell rejection condition (F9)
    always_comb begin
        err_param = 1'b0;
        if (used_q == {N_LIST{1'b0}}) begin              // N_USED == 0
            err_param = 1'b1;
        end
        if (sym_lim_q == 32'd0 || sym_lim_q > SYM_MAX) begin
            err_param = 1'b1;
        end
        if (byt_lim_q == 32'd0 || byt_lim_q > BYT_MAX) begin
            err_param = 1'b1;
        end
    end

    // ---- strobe merge --------------------------------------------------------------------------
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

    // ---- address classes -----------------------------------------------------------------------
    logic addr_mapped;                                   // In-window and mapped (else SLVERR)
    logic wr_used_hit;                                   // Write targets a USED word
    // verilator lint_off UNUSEDSIGNAL
    logic [9:0] used_word;                               // USED word index (bit 9 unused: range-checked)
    // verilator lint_on UNUSEDSIGNAL
    logic [2:0] used_wsel;                               // USED[0..7] selector
    always_comb begin
        addr_mapped = (wr_addr_i <= 10'h087);            // 0x000..0x21C mapped; >= 0x220 -> SLVERR
        used_word   = wr_addr_i - 10'h080;
        used_wsel   = used_word[2:0];
        wr_used_hit = (wr_addr_i >= 10'h080) && (wr_addr_i <= 10'h087);
    end

    logic rd_mapped;                                     // Read address mapped
    // verilator lint_off UNUSEDSIGNAL
    logic [9:0] rd_used_word;                            // USED word index for reads
    // verilator lint_on UNUSEDSIGNAL
    logic [2:0] rd_used_wsel;                            // USED read selector
    always_comb begin
        rd_mapped    = (rd_addr_i <= 10'h087);
        rd_used_word = rd_addr_i - 10'h080;
        rd_used_wsel = rd_used_word[2:0];
    end

    // ---- write / decision / read path ----------------------------------------------------------
    always_comb begin
        cfg_tmp   = 32'd0;
        w1c_tmp   = 32'd0;
        irqen_tmp = 32'd0;
        used_n    = used_q;
        sym_lim_n = sym_lim_q;
        byt_lim_n = byt_lim_q;
        dbg_sel_n = dbg_sel_q;
        sticky_n  = sticky_q;
        irq_en_n  = irq_en_q;
        db_pending_n = 1'b0;
        db_hold_n    = db_hold_q;
        doorbell_n   = 1'b0;
        abort_n      = 1'b0;
        wr_err_n     = 1'b0;
        rd_data_n    = 32'd0;
        rd_err_n     = 1'b0;

        // sticky set inputs from the datapath
        if (done_set_i)     sticky_n[B_DONE] = 1'b1;
        if (aborted_set_i)  sticky_n[B_ABRT] = 1'b1;
        if (err_rank_i)     sticky_n[B_ERNK] = 1'b1;
        if (err_run_i)      sticky_n[B_ERUN] = 1'b1;
        if (err_limit_i)    sticky_n[B_ELIM] = 1'b1;
        if (err_underrun_i) sticky_n[B_EUNR] = 1'b1;

        // ---- write decode ----
        if (req_wr_i) begin
            if (!addr_mapped) begin
                wr_err_n = 1'b1;                          // unmapped -> SLVERR
            end else if (wr_addr_i == 10'h002 && wr_strb_i[0]) begin
                // CTRL (WP): byte 0 must be strobed
                if (wr_data_i[1]) begin
                    abort_n = 1'b1;                       // ABORT wins over DOORBELL
                    if (wr_data_i[0] && busy_i) begin
                        sticky_n[B_EBSY] = 1'b1;          // the doorbell half was ignored
                    end
                end else if (wr_data_i[0]) begin
                    if (busy_i) begin
                        sticky_n[B_EBSY] = 1'b1;          // doorbell while BUSY -> ERR_BUSY
                    end else begin
                        db_pending_n = 1'b1;              // decide next cycle (BRESP held)
                        db_hold_n    = 1'b1;
                    end
                end
            end else if (wr_addr_i == 10'h003) begin      // STATUS W1C
                w1c_tmp  = apply_strb(32'd0, wr_data_i, wr_strb_i);
                sticky_n = sticky_n & ~w1c_tmp[13:0];
            end else if (wr_addr_i == 10'h004) begin      // IRQ_EN (writable while BUSY)
                irqen_tmp = apply_strb({18'd0, irq_en_q}, wr_data_i, wr_strb_i);
                irq_en_n  = irqen_tmp[13:0] & IRQEN_MASK;
            end else if (wr_addr_i == 10'h043) begin      // DBG_SEL (writable while BUSY)
                cfg_tmp   = apply_strb({24'd0, dbg_sel_q}, wr_data_i, wr_strb_i);
                dbg_sel_n = cfg_tmp[7:0];
            end else if (wr_addr_i == 10'h040) begin      // SYMBOL_LIMIT (config)
                if (busy_i) begin
                    sticky_n[B_EBSY] = 1'b1;
                end else begin
                    sym_lim_n = apply_strb(sym_lim_q, wr_data_i, wr_strb_i);
                end
            end else if (wr_addr_i == 10'h041) begin      // BYTES_LIMIT (config)
                if (busy_i) begin
                    sticky_n[B_EBSY] = 1'b1;
                end else begin
                    byt_lim_n = apply_strb(byt_lim_q, wr_data_i, wr_strb_i);
                end
            end else if (wr_used_hit) begin               // USED[w] (config)
                if (busy_i) begin
                    sticky_n[B_EBSY] = 1'b1;
                end else begin
                    used_n[used_wsel*32 +: 32] = apply_strb(used_q[used_wsel*32 +: 32],
                                                            wr_data_i, wr_strb_i);
                end
            end
            // ID/VERSION/CAPS/DBG_DATA/counters/reserved: write ignored, OKAY
        end

        // ---- doorbell decision (cycle after the CTRL write; BRESP held meanwhile) ----
        if (db_pending_q) begin
            db_hold_n = 1'b0;
            if (err_param) begin
                sticky_n[B_EPRM] = 1'b1;
            end else begin
                doorbell_n = 1'b1;
            end
        end

        // ---- read decode ----
        if (req_rd_i) begin
            if (!rd_mapped) begin
                rd_err_n = 1'b1;
            end else begin
                case (rd_addr_i)
                    10'h000: rd_data_n = ID_VALUE;
                    10'h001: rd_data_n = VERSION;
                    10'h002: rd_data_n = 32'd0;                              // CTRL reads 0
                    10'h003: rd_data_n = {18'd0, sticky_q[13:1], busy_i};    // STATUS
                    10'h004: rd_data_n = {18'd0, irq_en_q[13:1], 1'b0};      // IRQ_EN
                    10'h005: rd_data_n = {18'd0, sticky_q[13:1] & irq_en_q[13:1], 1'b0};  // IRQ_STATUS
                    10'h010: rd_data_n = cycles_i[31:0];
                    10'h011: rd_data_n = cycles_i[63:32];
                    10'h012: rd_data_n = symbols_in_i;
                    10'h013: rd_data_n = bytes_out_i;
                    10'h014: rd_data_n = {23'd0, init_cycles_i};
                    10'h015: rd_data_n = {11'd0, max_run_i};
                    10'h040: rd_data_n = sym_lim_q;
                    10'h041: rd_data_n = byt_lim_q;
                    10'h042: rd_data_n = {7'd0, N_LIST[8:0], D[7:0], W[7:0]};  // CAPS
                    10'h043: rd_data_n = {24'd0, dbg_sel_q};
                    10'h044: rd_data_n = {24'd0, dbg_data_i};
                    default: begin
                        rd_data_n = 32'd0;                                    // reserved reads 0
                        if (rd_addr_i >= 10'h080 && rd_addr_i <= 10'h087) begin
                            rd_data_n = used_q[rd_used_wsel*32 +: 32];        // USED[w]
                        end
                    end
                endcase
            end
        end

        // ---- IRQ ----
        irq_n = |(sticky_n & irq_en_n);

        // ---- reset ----
        if (!rst_n) begin
            used_n       = {N_LIST{1'b0}};
            sym_lim_n    = 32'd0;
            byt_lim_n    = 32'd0;
            dbg_sel_n    = 8'd0;
            sticky_n     = 14'd0;
            irq_en_n     = 14'd0;
            irq_n        = 1'b0;
            db_pending_n = 1'b0;
            db_hold_n    = 1'b0;
            doorbell_n   = 1'b0;
            abort_n      = 1'b0;
            wr_err_n     = 1'b0;
            rd_data_n    = 32'd0;
            rd_err_n     = 1'b0;
        end
    end

    always_ff @(posedge clk) begin
        used_q       <= used_n;
        sym_lim_q    <= sym_lim_n;
        byt_lim_q    <= byt_lim_n;
        dbg_sel_q    <= dbg_sel_n;
        sticky_q     <= sticky_n;
        irq_en_q     <= irq_en_n;
        irq_q        <= irq_n;
        db_pending_q <= db_pending_n;
        db_hold_q    <= db_hold_n;
        doorbell_o   <= doorbell_n;
        abort_o      <= abort_n;
        wr_err_o     <= wr_err_n;
        rd_data_o    <= rd_data_n;
        rd_err_o     <= rd_err_n;
    end

    assign wr_resp_hold_o = db_hold_q;
    assign irq_o          = irq_q;
    assign used_map_o     = used_q;
    assign symbol_limit_o = sym_lim_q;
    assign bytes_limit_o  = byt_lim_q;
    assign dbg_sel_o      = dbg_sel_q;

endmodule

`default_nettype wire
