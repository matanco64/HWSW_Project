`default_nettype none

// Module: huff_builder
// Purpose: Canonical-Huffman table build FSM (uArch section 3.2, rtl_contracts.md builder).
//          Per table t < n_tables_i:
//            PREFIX (MAXLEN = 20 cycles, l = 1..20):
//              first_code[l] = (first_code[l-1] + count[t][l-1]) << 1     (UQ20.0 stored)
//              base[l]       = base[l-1] + count[t][l-1]                  (UQ11.0)
//              limit_la[l]   = (first_code[l] + count[t][l]) << (20 - l)  (UQ21.0)
//              Kraft check: first_code[l] + count[t][l] > 2^l -> err_table_o pulse, build abort
//            FILL (ALPHABET cycles, s = 0..alphabet-1): symbol s with len l != 0 is written to
//              symtab[table_base[t] + base[l] + next[l]++] = {valid = 1, s}; the EOB symbol's
//              (l, code) is latched (s == alphabet-1 in bzip2; s == 256, table 0 only, DEFLATE).
//          All six EOB latches are cleared at build start (PREP-entry clear, review N2).
//          table_base[t] = t * 288 (fixed per-set stride into the shared 1,728-entry symtab —
//          simplest bounded layout; index math is bounded by the per-table sums, uArch section 4).
//          Lengths arrive through huff_regs' read port ({t, sym} -> 5 b, 1-cycle registered);
//          counts through the folded (t, l) -> 9 b combinational bins. DEFLATE reuses the
//          20-aligned datapath: bins 16..20 are zero (checked at the doorbell by huff_regs).
//          build_cycles_o = max per-table PREFIX+FILL cycles = alphabet + 20 (K2 evidence).
//          Yosys 0.68 subset: no struct arrays, no fn-call bit-selects, declare-before-use.
module huff_builder (
    input  logic        clk,              // System clock
    input  logic        rst_n,            // Active-low synchronous reset
    // Control (from huff_ctrl / TB)
    input  logic        start_i,          // 1-cycle pulse: build n_tables_i tables
    input  logic        stop_i,           // Abort/flush: return to IDLE (R6)
    input  logic        mode_deflate_i,   // 1 = DEFLATE (EOB = symbol 256, table 0 only)
    input  logic [8:0]  alphabet_i,       // Symbols per table, UQ9.0 (1..288)
    input  logic [2:0]  n_tables_i,       // Tables to build, UQ3.0 (1..6)
    // Lengths read port (huff_regs): addr {t[2:0], sym[8:0]} -> 5 b, 1-cycle registered
    output logic [11:0] lengths_addr_o,   // Lengths window read address
    input  logic [4:0]  lengths_data_i,   // Length of the symbol addressed LAST cycle, UQ5.0
    // Counts read port (huff_regs): {t[2:0], l[4:0]} -> 9 b combinational
    output logic [7:0]  counts_addr_o,    // Count-bin read address
    input  logic [8:0]  counts_data_i,    // count[t][l], UQ9.0 (combinational)
    // Set write port (huff_tables)
    output logic        wr_set_en_o,      // Write {first_code, base, limit_la} entry l of set t
    output logic [2:0]  wr_set_o,         // Destination set index (= t)
    output logic [4:0]  wr_l_o,           // Destination length 1..20
    output logic [19:0] wr_first_code_o,  // first_code[l], UQ20.0 (truncated from UQ21.0)
    output logic [20:0] wr_limit_la_o,    // limit_la[l], UQ21.0
    output logic [10:0] wr_base_o,        // base[l], UQ11.0
    output logic        tbase_wr_en_o,    // Write table_base of set t
    output logic [10:0] tbase_o,          // table_base[t] = t * 288, UQ11.0
    output logic        eob_wr_en_o,      // Latch (eob_len, eob_code) into set t
    output logic [4:0]  eob_len_o,        // EOB code length, UQ5.0
    output logic [19:0] eob_code_o,       // EOB canonical code, UQ20.0
    output logic        eob_clr_o,        // Clear ALL six eob_len latches (build start)
    // Symtab write port (huff_tables)
    output logic        symtab_wr_en_o,   // Symtab write strobe
    output logic [10:0] symtab_wr_addr_o, // table_base + base[l] + next[l], UQ11.0
    output logic [9:0]  symtab_wr_data_o, // {valid, sym[8:0]}
    // Status
    output logic        busy_o,           // Build in progress
    output logic        fill_active_o,    // FILL pass active (gates the tables DBG read)
    output logic        build_done_o,     // LEVEL: all tables built (cleared by start/stop — R2)
    output logic        err_table_o,      // 1-cycle pulse: Kraft overflow, build aborted
    output logic [15:0] build_cycles_o    // Max per-table build cycles, UQ16.0
);

    localparam logic [4:0] MAXLEN = 5'd20;  // bzip2 MAXLEN (DEFLATE zero-bins 16..20)

    typedef enum logic [1:0] {
        ST_IDLE,    // Waiting for start_i
        ST_PREFIX,  // Prefix recurrence, l = 1..MAXLEN
        ST_FILL     // Symtab fill, s = 0..alphabet-1
    } state_t;

    // ---- state registers ----------------------------------------------------------------------
    state_t             state;        // Current FSM state
    state_t             state_next;   // Next FSM state
    logic [2:0]         t_r;          // Current table index
    logic [2:0]         t_next;       // Next table index
    logic [4:0]         l_r;          // Current PREFIX length (1..20)
    logic [4:0]         l_next;       // Next PREFIX length
    logic [8:0]         s_r;          // FILL symbol whose length data arrives THIS cycle
    logic [8:0]         s_next;       // Next FILL symbol
    logic [20:0]        code_r;       // Untruncated first_code[l_r], UQ21.0
    logic [20:0]        code_next;    // Next running code
    logic [10:0]        base_r;       // base[l_r] (symbols of length < l_r), UQ11.0
    logic [10:0]        base_next;    // Next running base
    logic [15:0]        cyc_r;        // Per-table cycle counter, UQ16.0
    logic [15:0]        cyc_next;     // Next per-table cycle counter
    logic [15:0]        maxcyc_r;     // Max per-table cycles so far, UQ16.0
    logic [15:0]        maxcyc_next;  // Next max
    logic               done_r;       // Registered build_done pulse
    logic               done_next;    // Next done pulse
    logic               err_r;        // Registered err_table pulse
    logic               err_next;     // Next err pulse

    // Per-length FILL pointers (initialized during PREFIX, bumped per placed symbol):
    // fill_ptr[l-1] = table_base + base[l] + next[l] (absolute symtab address, UQ11.0)
    // code_ptr[l-1] = first_code[l] + next[l]        (running canonical code, UQ20.0)
    logic [10:0]        fill_ptr [0:19];  // Absolute symtab write pointer per length
    logic [19:0]        code_ptr [0:19];  // Running canonical code per length
    logic               fp_we;            // Pointer-pair write enable
    logic [4:0]         fp_idx;           // Pointer-pair index (l-1 in PREFIX, len-1 in FILL)
    logic [10:0]        fp_wdata;         // fill_ptr write data
    logic [19:0]        cp_wdata;         // code_ptr write data
    logic [10:0]        fill_cur;         // fill_ptr[fp_idx] (current read)
    logic [19:0]        code_cur;         // code_ptr[fp_idx] (current read)

    // ---- combinational datapath ---------------------------------------------------------------
    logic [8:0]         count_c;      // count[t_r][l_r] from the bins, UQ9.0
    logic [20:0]        sum_c;        // first_code[l] + count[l], UQ21.0
    logic [20:0]        pow2_c;       // 2^l, UQ21.0
    logic               kraft_viol_c; // sum_c > 2^l: over-subscribed code
    logic [4:0]         shift_c;      // MAXLEN - l
    logic [20:0]        limit_c;      // limit_la[l] = sum_c << (MAXLEN - l), UQ21.0
    logic [10:0]        tbase_c;      // table_base[t_r] = t_r * 288, UQ11.0
    logic [4:0]         len_c;        // Length of FILL symbol s_r, UQ5.0
    logic               len_nz_c;     // Symbol is coded (0 < len <= MAXLEN)
    logic               last_sym_c;   // s_r is the table's last symbol
    logic               last_tbl_c;   // t_r is the last table
    logic               eob_hit_c;    // This FILL symbol is the EOB symbol
    logic [8:0]         s_addr_c;     // Symbol index driven on the lengths read port

    always_comb begin
        count_c      = counts_data_i;
        sum_c        = code_r + {12'b0, count_c};
        pow2_c       = 21'd1 << l_r;
        kraft_viol_c = (state == ST_PREFIX) && (sum_c > pow2_c);
        shift_c      = MAXLEN - l_r;
        limit_c      = sum_c << shift_c;
        tbase_c      = {t_r, 8'b0} + {3'b0, t_r, 5'b0};  // t*256 + t*32 = t*288
        len_c        = lengths_data_i;
        len_nz_c     = (len_c != 5'd0) && (len_c <= MAXLEN);
        last_sym_c   = (s_r == alphabet_i - 9'd1);
        last_tbl_c   = (t_r == n_tables_i - 3'd1);
        eob_hit_c    = (state == ST_FILL) && len_nz_c &&
                       (mode_deflate_i ? ((s_r == 9'd256) && (t_r == 3'd0)) : last_sym_c);
        s_addr_c     = (state == ST_FILL) ? (s_r + 9'd1) : 9'd0;
    end

    // ---- next-state logic ---------------------------------------------------------------------
    always_comb begin
        state_next  = state;
        t_next      = t_r;
        l_next      = l_r;
        s_next      = s_r;
        code_next   = code_r;
        base_next   = base_r;
        cyc_next    = cyc_r;
        maxcyc_next = maxcyc_r;
        done_next   = done_r;
        err_next    = 1'b0;
        fp_we       = 1'b0;
        fp_idx      = l_r - 5'd1;
        fp_wdata    = tbase_c + base_r;
        cp_wdata    = code_r[19:0];

        case (state)
            ST_IDLE: begin
                done_next = done_r && !start_i;
                if (start_i) begin
                    state_next  = ST_PREFIX;
                    t_next      = 3'd0;
                    l_next      = 5'd1;
                    code_next   = 21'd0;
                    base_next   = 11'd0;
                    cyc_next    = 16'd0;
                    maxcyc_next = 16'd0;
                end
            end
            ST_PREFIX: begin
                cyc_next = cyc_r + 16'd1;
                if (kraft_viol_c) begin
                    err_next   = 1'b1;      // ERR_TABLE pulse next cycle, abort the build
                    state_next = ST_IDLE;
                end else begin
                    fp_we     = 1'b1;       // fill_ptr[l-1] <- table_base + base[l]
                    code_next = {sum_c[19:0], 1'b0};
                    base_next = base_r + {2'b0, count_c};
                    if (l_r == MAXLEN) begin
                        state_next = ST_FILL;
                        s_next     = 9'd0;
                    end else begin
                        l_next = l_r + 5'd1;
                    end
                end
            end
            ST_FILL: begin
                cyc_next = cyc_r + 16'd1;
                fp_idx   = len_c - 5'd1;
                if (len_nz_c) begin
                    fp_we    = 1'b1;        // bump both pointers past the placed symbol
                    fp_wdata = fill_cur + 11'd1;
                    cp_wdata = code_cur + 20'd1;
                end
                if (last_sym_c) begin
                    if (cyc_r + 16'd1 > maxcyc_r) begin
                        maxcyc_next = cyc_r + 16'd1;   // this table's PREFIX+FILL total
                    end
                    if (last_tbl_c) begin
                        done_next  = 1'b1;
                        state_next = ST_IDLE;
                    end else begin
                        state_next = ST_PREFIX;
                        t_next     = t_r + 3'd1;
                        l_next     = 5'd1;
                        code_next  = 21'd0;
                        base_next  = 11'd0;
                        cyc_next   = 16'd0;
                    end
                end else begin
                    s_next = s_r + 9'd1;
                end
            end
            default: begin
                state_next = ST_IDLE;
            end
        endcase

        if (stop_i) begin
            state_next = ST_IDLE;
            done_next  = 1'b0;
            err_next   = 1'b0;
        end
        if (!rst_n) begin
            state_next  = ST_IDLE;
            t_next      = 3'd0;
            l_next      = 5'd1;
            s_next      = 9'd0;
            code_next   = 21'd0;
            base_next   = 11'd0;
            cyc_next    = 16'd0;
            maxcyc_next = 16'd0;
            done_next   = 1'b0;
            err_next    = 1'b0;
            fp_we       = 1'b0;
        end
    end

    // ---- registers ----------------------------------------------------------------------------
    always_ff @(posedge clk) begin
        state    <= state_next;
        t_r      <= t_next;
        l_r      <= l_next;
        s_r      <= s_next;
        code_r   <= code_next;
        base_r   <= base_next;
        cyc_r    <= cyc_next;
        maxcyc_r <= maxcyc_next;
        done_r   <= done_next;
        err_r    <= err_next;
    end

    // Pointer pair: small RMW memories (memory-inference exception to simple-assign rule)
    always_ff @(posedge clk) begin
        if (fp_we) begin
            fill_ptr[fp_idx] <= fp_wdata;
            code_ptr[fp_idx] <= cp_wdata;
        end
    end

    always_comb begin
        fill_cur = fill_ptr[fp_idx];
        code_cur = code_ptr[fp_idx];
    end

    // ---- outputs ------------------------------------------------------------------------------
    always_comb begin
        lengths_addr_o   = {t_r, s_addr_c};
        counts_addr_o    = {t_r, l_r};
        wr_set_en_o      = (state == ST_PREFIX) && !kraft_viol_c;
        wr_set_o         = t_r;
        wr_l_o           = l_r;
        wr_first_code_o  = code_r[19:0];
        wr_limit_la_o    = limit_c;
        wr_base_o        = base_r;
        tbase_wr_en_o    = (state == ST_PREFIX) && (l_r == 5'd1) && !kraft_viol_c;
        tbase_o          = tbase_c;
        eob_wr_en_o      = eob_hit_c;
        eob_len_o        = len_c;
        eob_code_o       = code_cur;
        eob_clr_o        = (state == ST_IDLE) && start_i && rst_n;
        symtab_wr_en_o   = (state == ST_FILL) && len_nz_c;
        symtab_wr_addr_o = fill_cur;
        symtab_wr_data_o = {1'b1, s_r};
        busy_o           = (state != ST_IDLE);
        fill_active_o    = (state == ST_FILL);
        build_done_o     = done_r;
        err_table_o      = err_r;
        build_cycles_o   = maxcyc_r;
    end

endmodule

`default_nettype wire
