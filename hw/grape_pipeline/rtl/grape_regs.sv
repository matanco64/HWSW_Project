`default_nettype none

// Module: grape_regs
// Purpose: Register decoder for grape_pipeline behind axi_lite_if (MAS §4). Implements the
//          ADR-0005 header (ID/VERSION/CTRL/STATUS/IRQ), counters, configuration with
//          pending/latched semantics, the body-state window (pending here; committed bank read
//          from grape_body_rf while BUSY), the pair-list window, reserved RAZ/WI ranges and
//          SLVERR for unmapped words. Doorbell-time ERR_PARAM check and BRESP hold (ADR-0005).
module grape_regs #(
    parameter int          N_BODIES    = 5,            // Bodies (PRD-F6)
    parameter int          N_PAIRS_MAX = 10,           // Pair-list capacity
    parameter logic [31:0] VERSION     = 32'd0         // git short SHA (synthesis parameter)
) (
    input  logic                     clk,              // System clock
    input  logic                     rst_n,            // Active-low synchronous reset
    // Register bus (axi_lite_if)
    input  logic                     req_wr_i,         // Write pulse
    input  logic [9:0]               wr_addr_i,        // Write word address
    input  logic [31:0]              wr_data_i,        // Write data
    input  logic [3:0]               wr_strb_i,        // Byte strobes
    output logic                     wr_err_o,         // SLVERR (cycle after req_wr_i)
    output logic                     wr_resp_hold_o,   // Hold BRESP during doorbell decision
    input  logic                     req_rd_i,         // Read pulse
    input  logic [9:0]               rd_addr_i,        // Read word address
    output logic [31:0]              rd_data_o,        // Read data (cycle after req_rd_i)
    output logic                     rd_err_o,         // SLVERR
    // Control / status exchange with the step FSM
    output logic                     doorbell_o,       // Accepted-doorbell pulse (config latched now)
    output logic                     abort_o,          // Abort request pulse
    input  logic                     busy_i,           // Step FSM busy
    input  logic                     done_set_i,       // DONE pulse (last step committed)
    input  logic                     aborted_set_i,    // ABORTED pulse
    input  logic [3:0]               fp_flags_set_i,   // {invalid, divzero, overflow, underflow} pulses
    input  logic [31:0]              steps_done_i,     // Live steps counter (step FSM)
    input  logic [63:0]              cycles_i,         // Live busy-cycle counter (step FSM)
    // Latched configuration (valid from doorbell_o until the next one)
    output logic [63:0]              dt_o,             // dt, binary64
    output logic [31:0]              nsteps_o,         // Steps per invocation
    output logic [7:0]               npairs_o,         // Pairs per step
    output logic [N_PAIRS_MAX*16-1:0] pairs_o,         // Pair list: [7:0] i, [15:8] j per entry
    output logic [N_BODIES*7*64-1:0] body_pending_o,   // Pending body window (load into body RF)
    input  logic [N_BODIES*7*64-1:0] body_committed_i, // Committed bank (read while BUSY)
    // Interrupt
    output logic                     irq_o             // Level IRQ (registered)
);

    localparam logic [31:0] ID_VALUE = 32'h4752_5031;  // ASCII "GRP1"
    localparam int          NW       = N_BODIES * 7;   // Body window words (64-bit values)

    // ---- storage -------------------------------------------------------------------------------
    logic [63:0] dt_pend;                              // Pending DT
    logic [31:0] nsteps_pend;                          // Pending NSTEPS
    logic [7:0]  npairs_pend;                          // Pending NPAIRS
    logic [15:0] pairs_pend [N_PAIRS_MAX];             // Pending pair list
    logic [63:0] body_pend  [NW];                      // Pending body window
    logic [63:0] dt_l;                                 // Latched DT
    logic [31:0] nsteps_l;                             // Latched NSTEPS
    logic [7:0]  npairs_l;                             // Latched NPAIRS
    logic [15:0] pairs_l [N_PAIRS_MAX];                // Latched pair list
    logic [15:0] sticky;                               // STATUS sticky bits [15:1] (bit 0 unused)
    logic [16:1] irq_en;                               // IRQ_EN mask
    logic        irq_q;                                // Registered IRQ
    logic        db_pending;                           // Doorbell decision window (this cycle)
    logic        db_hold;                              // BRESP hold flag

    // STATUS sticky bit positions (MAS §4)
    localparam int B_DONE = 1;                         // DONE
    localparam int B_ABRT = 2;                         // ABORTED
    localparam int B_EBSY = 8;                         // ERR_BUSY
    localparam int B_EPRM = 9;                         // ERR_PARAM
    localparam int B_FINV = 12;                        // FP_INVALID
    localparam int B_FDIV = 13;                        // FP_DIVZERO
    localparam int B_FOVF = 14;                        // FP_OVERFLOW
    localparam int B_FUNF = 15;                        // FP_UNDERFLOW

    // ---- ERR_PARAM (combinational over pending config) -----------------------------------------
    logic        err_param;                            // Doorbell rejection condition
    always_comb begin
        err_param = 1'b0;
        if ({24'd0, npairs_pend} > N_PAIRS_MAX[31:0]) begin
            err_param = 1'b1;
        end
        for (int k = 0; k < N_PAIRS_MAX; k++) begin
            if (k < {24'd0, npairs_pend}) begin
                if ({29'd0, pairs_pend[k][2:0]} >= N_BODIES[31:0] || pairs_pend[k][7:3] != 5'd0) begin
                    err_param = 1'b1;
                end
                if ({29'd0, pairs_pend[k][10:8]} >= N_BODIES[31:0] || pairs_pend[k][15:11] != 5'd0) begin
                    err_param = 1'b1;
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
        if (a >= 10'h010 && a <= 10'h012) begin
            m = 1'b1;                                  // 0x040-0x048 counters
        end
        if (a >= 10'h013 && a <= 10'h03F) begin
            m = 1'b1;                                  // 0x04C-0x0FC reserved
        end
        if (a >= 10'h040 && a <= 10'h043) begin
            m = 1'b1;                                  // 0x100-0x10C config
        end
        if (a >= 10'h044 && a <= 10'h07F) begin
            m = 1'b1;                                  // 0x110-0x1FC reserved
        end
        if (a >= 10'h080 && a <= 10'h0FF) begin
            m = 1'b1;                                  // 0x200-0x3FC body window + reserved
        end
        if (a >= 10'h100 && a < 10'h100 + N_PAIRS_MAX[9:0]) begin
            m = 1'b1;                                  // 0x400.. pair list
        end
        addr_mapped = m;
    endfunction

    logic        wr_body_hit;                          // Write targets a used body word
    // verilator lint_off UNUSEDSIGNAL
    logic [9:0]  wr_body_word;                         // Word offset inside the body region (bit 9 unused: range-checked)
    // verilator lint_on UNUSEDSIGNAL
    logic [5:0]  wr_body_val;                          // 64-bit value index (0..NW-1)
    logic        wr_body_hi;                           // High word of the value
    always_comb begin
        wr_body_word = wr_addr_i - 10'h080;            // Words since 0x200
        wr_body_val  = {1'b0, wr_body_word[8:4]} * 6'd7 + {3'b000, wr_body_word[3:1]};
        wr_body_hi   = wr_body_word[0];
        wr_body_hit  = (wr_addr_i >= 10'h080) && (wr_addr_i <= 10'h0FF)
                       && (wr_body_word[3:1] < 3'd7) && ({1'b0, wr_body_word[8:4]} < N_BODIES[5:0]);
    end

    logic        cfg_write;                            // Write to a latched-class config register
    always_comb begin
        cfg_write = wr_body_hit
                    || (wr_addr_i >= 10'h040 && wr_addr_i <= 10'h043)
                    || (wr_addr_i >= 10'h100 && wr_addr_i < 10'h100 + N_PAIRS_MAX[9:0]);
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
    logic [63:0] dt_pend_n;
    logic [31:0] nsteps_pend_n;
    logic [7:0]  npairs_pend_n;
    logic [15:0] pairs_pend_n [N_PAIRS_MAX];
    logic [63:0] body_pend_n  [NW];
    logic [63:0] dt_l_n;
    logic [31:0] nsteps_l_n;
    logic [7:0]  npairs_l_n;
    logic [15:0] pairs_l_n [N_PAIRS_MAX];
    logic [15:0] sticky_n;
    logic [16:1] irq_en_n;
    logic        irq_n;
    logic        db_pending_n;
    logic        db_hold_n;
    logic        doorbell_n;
    logic        abort_n;
    logic        wr_err_n;
    logic [31:0] rd_data_n;
    logic        rd_err_n;
    // verilator lint_off UNUSEDSIGNAL
    logic [31:0] npairs_tmp;                           // apply_strb temp (Yosys: no fn-call slicing; upper bits unused)
    logic [31:0] pair_tmp;                             // apply_strb temp
    logic [31:0] w1c_tmp;                              // apply_strb temp
    logic [31:0] irqen_tmp;                            // apply_strb temp
    // verilator lint_on UNUSEDSIGNAL

    always_comb begin
        npairs_tmp = 32'd0;
        pair_tmp   = 32'd0;
        w1c_tmp    = 32'd0;
        irqen_tmp  = 32'd0;
        dt_pend_n     = dt_pend;
        nsteps_pend_n = nsteps_pend;
        npairs_pend_n = npairs_pend;
        for (int k = 0; k < N_PAIRS_MAX; k++) begin
            pairs_pend_n[k] = pairs_pend[k];
        end
        for (int u = 0; u < NW; u++) begin
            body_pend_n[u] = body_pend[u];
        end
        dt_l_n     = dt_l;
        nsteps_l_n = nsteps_l;
        npairs_l_n = npairs_l;
        for (int k = 0; k < N_PAIRS_MAX; k++) begin
            pairs_l_n[k] = pairs_l[k];
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

        // sticky set inputs from the FSM/datapath
        if (done_set_i) begin
            sticky_n[B_DONE] = 1'b1;
        end
        if (aborted_set_i) begin
            sticky_n[B_ABRT] = 1'b1;
        end
        if (fp_flags_set_i[3]) begin
            sticky_n[B_FINV] = 1'b1;
        end
        if (fp_flags_set_i[2]) begin
            sticky_n[B_FDIV] = 1'b1;
        end
        if (fp_flags_set_i[1]) begin
            sticky_n[B_FOVF] = 1'b1;
        end
        if (fp_flags_set_i[0]) begin
            sticky_n[B_FUNF] = 1'b1;
        end

        // committed -> pending copy at DONE/ABORTED (MAS §4)
        if (done_set_i || aborted_set_i) begin
            for (int u = 0; u < NW; u++) begin
                body_pend_n[u] = body_committed_i[u*64 +: 64];
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
                    if (wr_addr_i == 10'h040) begin
                        dt_pend_n[31:0] = apply_strb(dt_pend[31:0], wr_data_i, wr_strb_i);
                    end
                    if (wr_addr_i == 10'h041) begin
                        dt_pend_n[63:32] = apply_strb(dt_pend[63:32], wr_data_i, wr_strb_i);
                    end
                    if (wr_addr_i == 10'h042) begin
                        nsteps_pend_n = apply_strb(nsteps_pend, wr_data_i, wr_strb_i);
                    end
                    if (wr_addr_i == 10'h043) begin
                        npairs_tmp = apply_strb({24'd0, npairs_pend}, wr_data_i, wr_strb_i);
                        npairs_pend_n = npairs_tmp[7:0];
                    end
                    if (wr_body_hit) begin
                        if (wr_body_hi) begin
                            body_pend_n[wr_body_val][63:32] =
                                apply_strb(body_pend[wr_body_val][63:32], wr_data_i, wr_strb_i);
                        end else begin
                            body_pend_n[wr_body_val][31:0] =
                                apply_strb(body_pend[wr_body_val][31:0], wr_data_i, wr_strb_i);
                        end
                    end
                    for (int k = 0; k < N_PAIRS_MAX; k++) begin
                        if (wr_addr_i == 10'h100 + k[9:0]) begin
                            pair_tmp = apply_strb({16'd0, pairs_pend[k]}, wr_data_i, wr_strb_i);
                            pairs_pend_n[k] = pair_tmp[15:0];
                        end
                    end
                end
            end else begin
                // header/writable-while-BUSY registers
                if (wr_addr_i == 10'h002) begin        // CTRL (WP)
                    if (wr_data_i[1]) begin
                        abort_n = 1'b1;                // ABORT wins over DOORBELL (MAS §4)
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
                if (wr_addr_i == 10'h004) begin        // IRQ_EN
                    irqen_tmp = apply_strb({15'd0, irq_en, 1'b0}, wr_data_i, wr_strb_i);
                    irq_en_n = irqen_tmp[16:1];
                end
                // ID, VERSION, counters, IRQ_STATUS, reserved: write ignored, OKAY
            end
        end

        // ---- doorbell decision (cycle after the CTRL write; BRESP held meanwhile) ----
        if (db_pending) begin
            db_hold_n = 1'b0;
            if (err_param) begin
                sticky_n[B_EPRM] = 1'b1;
            end else begin
                doorbell_n = 1'b1;
                dt_l_n     = dt_pend;
                nsteps_l_n = nsteps_pend;
                npairs_l_n = npairs_pend;
                for (int k = 0; k < N_PAIRS_MAX; k++) begin
                    pairs_l_n[k] = pairs_pend[k];
                end
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
                    10'h004: rd_data_n = {15'd0, irq_en, 1'b0};
                    10'h005: rd_data_n = {16'd0, sticky[15:1] & irq_en[15:1], 1'b0};
                    10'h010: rd_data_n = cycles_i[31:0];
                    10'h011: rd_data_n = cycles_i[63:32];
                    10'h012: rd_data_n = steps_done_i;
                    10'h040: rd_data_n = busy_i ? dt_l[31:0] : dt_pend[31:0];
                    10'h041: rd_data_n = busy_i ? dt_l[63:32] : dt_pend[63:32];
                    10'h042: rd_data_n = busy_i ? nsteps_l : nsteps_pend;
                    10'h043: rd_data_n = {24'd0, busy_i ? npairs_l : npairs_pend};
                    default: begin
                        rd_data_n = 32'd0;             // reserved reads 0
                        if (rd_addr_i >= 10'h080 && rd_addr_i <= 10'h0FF) begin
                            rd_data_n = body_read(rd_addr_i);
                        end
                        for (int k = 0; k < N_PAIRS_MAX; k++) begin
                            if (rd_addr_i == 10'h100 + k[9:0]) begin
                                rd_data_n = {16'd0, busy_i ? pairs_l[k] : pairs_pend[k]};
                            end
                        end
                    end
                endcase
            end
        end

        // ---- IRQ ----
        irq_n = |(sticky_n[15:1] & irq_en_n[15:1]);

        // ---- reset ----
        if (!rst_n) begin
            dt_pend_n     = 64'd0;
            nsteps_pend_n = 32'd0;
            npairs_pend_n = 8'd0;
            for (int k = 0; k < N_PAIRS_MAX; k++) begin
                pairs_pend_n[k] = 16'd0;
                pairs_l_n[k]    = 16'd0;
            end
            for (int u = 0; u < NW; u++) begin
                body_pend_n[u] = 64'd0;
            end
            dt_l_n       = 64'd0;
            nsteps_l_n   = 32'd0;
            npairs_l_n   = 8'd0;
            sticky_n     = 16'd0;
            irq_en_n     = 16'd0;
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

    // Body window read helper: working copy = pending while idle, committed while BUSY (PRD-F10).
    function automatic logic [31:0] body_read(input logic [9:0] a);
        // verilator lint_off UNUSEDSIGNAL
        logic [9:0] w;                                 // bit 9 unused: callers range-check
        // verilator lint_on UNUSEDSIGNAL
        logic [5:0] v;
        logic       hi;
        logic [63:0] val;
        w  = a - 10'h080;
        v  = {1'b0, w[8:4]} * 6'd7 + {3'b000, w[3:1]};
        hi = w[0];
        val = 64'd0;
        if ((w[3:1] < 3'd7) && ({1'b0, w[8:4]} < N_BODIES[5:0])) begin
            val = busy_i ? body_committed_i[v*64 +: 64] : body_pend[v];
        end
        body_read = hi ? val[63:32] : val[31:0];
    endfunction

    always_ff @(posedge clk) begin
        dt_pend     <= dt_pend_n;
        nsteps_pend <= nsteps_pend_n;
        npairs_pend <= npairs_pend_n;
        dt_l        <= dt_l_n;
        nsteps_l    <= nsteps_l_n;
        npairs_l    <= npairs_l_n;
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
        for (int k = 0; k < N_PAIRS_MAX; k++) begin
            pairs_pend[k] <= pairs_pend_n[k];
            pairs_l[k]    <= pairs_l_n[k];
        end
        for (int u = 0; u < NW; u++) begin
            body_pend[u] <= body_pend_n[u];
        end
    end

    assign wr_resp_hold_o = db_hold;
    assign irq_o          = irq_q;
    assign dt_o           = dt_l;
    assign nsteps_o       = nsteps_l;
    assign npairs_o       = npairs_l;
    always_comb begin
        for (int k = 0; k < N_PAIRS_MAX; k++) begin
            pairs_o[k*16 +: 16] = pairs_l[k];
        end
        for (int u = 0; u < NW; u++) begin
            body_pending_o[u*64 +: 64] = body_pend[u];
        end
    end

endmodule

`default_nettype wire
