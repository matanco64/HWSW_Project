`default_nettype none

// Module: grape_accum
// Purpose: Ordered velocity accumulate + position integrate (uArch §3.3). The accumulate
//          sequence (6 ops per pair: v_i.c -= f_i.c then v_j.c += f_j.c, pair order) issues
//          UP TO THREE ops per cycle into the ADD slots the static table leaves free: ops are
//          scanned in program order and one may issue when its pair is force_ready, its
//          (body, component) chain has no earlier unissued op and is not in flight (or clears
//          this cycle — retire bypass), and a slot remains. Order within each (body, component)
//          chain is preserved exactly (PRD-F2/F3 bit-exactness); independent chains overlap,
//          which is what uArch §3.3 promises and the §7 schedule model (123/127 cycles)
//          assumes — the earlier single-issue engine measured 162 cycles/step at sign-off. After the last pair, integrates: for each (body, component), mul dt*v
//          (MUL free slots) then add r + (dt*v) (ADD free slots) — two roundings, never fused.
//          Writes results into the body RF working bank. All 90 op retirements are counted for
//          the step-done countdown (step FSM).
module grape_accum #(
    parameter int N_BODIES    = 5,                     // Bodies
    parameter int N_PAIRS_MAX = 10                     // Pair slots
) (
    input  logic                        clk,           // System clock
    input  logic                        rst_n,         // Active-low synchronous reset
    input  logic                        step_start_i,  // Cycle 0 of a step
    input  logic                        run_i,         // Step in progress
    input  logic [7:0]                  npairs_i,      // Latched NPAIRS
    // verilator coverage_off
    // Toggle exclusion (testplan §5): latched pair domain — indices are doorbell-validated < N_BODIES (3 bits); upper field bits unreachable past ERR_PARAM.
    input  logic [N_PAIRS_MAX*16-1:0]   pairs_i,       // Latched pair list
    // verilator coverage_on
    input  logic [63:0]                 dt_i,          // Latched dt
    input  logic [N_BODIES*7*64-1:0]    working_flat_i, // Body working bank (velocities, positions)
    input  logic [N_PAIRS_MAX*6*64-1:0] force_flat_i,  // Force terms from grape_force_pipe
    input  logic [N_PAIRS_MAX-1:0]      force_ready_i, // Per-pair force-ready
    // Free-slot masks from the static table
    input  logic [2:0]                  add_free_i,    // ADD slots free this cycle
    input  logic [2:0]                  mul_free_i,    // MUL slots free this cycle
    // FP unit issue (merged with the force pipe's drives in grape_top; own valids here)
    output logic [2:0]                  add_valid_o,   // ADD issue valids (only on free slots)
    output logic [2:0]                  add_sub_o,     // Subtract selects
    output logic [3*64-1:0]             add_a_o,       // Operand a
    output logic [3*64-1:0]             add_b_o,       // Operand b
    input  logic [2:0]                  add_ovalid_i,  // ADD result valids
    input  logic [3*64-1:0]             add_r_i,       // ADD results
    output logic [2:0]                  mul_valid_o,   // MUL issue valids (only on free slots)
    output logic [3*64-1:0]             mul_a_o,       // Operand a
    output logic [3*64-1:0]             mul_b_o,       // Operand b
    input  logic [2:0]                  mul_ovalid_i,  // MUL result valids
    input  logic [3*64-1:0]             mul_r_i,       // MUL results
    // Body RF write ports (one per ADD unit; retire targets are distinct — SVA below)
    output logic [2:0]                  wr_en_o,       // Working-bank write enables
    output logic [3*3-1:0]              wr_body_o,     // Write body indices
    output logic [3*3-1:0]              wr_field_o,    // Write field indices
    output logic [3*64-1:0]             wr_data_o,     // Write data
    // Step completion
    output logic                        all_done_o     // All accumulate+integrate ops retired
);

    localparam int ADD_LAT = 3;                        // fp64_add latency
    localparam int MUL_LAT = 3;                        // fp64_mul latency

    // ---- micro-op state ------------------------------------------------------------------------
    // Accumulate op e (0 .. 6*NPAIRS-1): pair = e/6; op = e%6; op 0..2 -> v[i].c -= f_i.c,
    // op 3..5 -> v[j].c += f_j.c. Issue is in-order PER (body, component) chain; up to 3 ops
    // issue per cycle across independent chains.
    localparam int N_ACC = N_PAIRS_MAX * 6;            // 60 accumulate op slots
    logic [N_ACC-1:0] acc_issued;                      // Issued bitmap
    logic [N_ACC-1:0] acc_valid_mask;                  // Ops with pair < NPAIRS
    logic [N_ACC-1:0] acc_iss_set;                     // Issuing this cycle
    logic             acc_done;                        // All valid accumulate ops issued
    logic [14:0] integ_mul_issued;                     // Integrate mul issued per lane
    logic        integ_mul_done;                       // All integrate muls issued
    logic [14:0] lane_pend;                            // Lane has an unissued accumulate op
    logic [14:0] integ_mul_v;                          // dt*v result valid per lane
    logic [63:0] integ_mul_r [15];                     // dt*v results
    logic [14:0] integ_add_issued;                     // Integrate add issued per lane
    logic [7:0]  retired;                              // Retired op count (6*NPAIRS + 30)
    logic [14:0] busy_bc;                              // Scoreboard: (body,comp) in flight

    // Shadow pipes for result routing, per ADD unit (parallel arrays — Yosys 0.68)
    logic       add_sh_v  [3][ADD_LAT];                // ADD shadow valids
    logic       add_sh_ia [3][ADD_LAT];                // ADD: op is an integrate add
    logic [2:0] add_sh_b  [3][ADD_LAT];                // ADD target body
    logic [2:0] add_sh_f  [3][ADD_LAT];                // ADD target field
    logic [1:0] add_sh_c  [3][ADD_LAT];                // ADD target component (R3)
    logic       mul_sh_v  [3][MUL_LAT];                // MUL shadow valids (integrate muls)
    logic [3:0] mul_sh_l  [3][MUL_LAT];                // MUL integrate lane

    function automatic logic [63:0] body_field(input logic [N_BODIES*7*64-1:0] flat,
                                               input logic [2:0] body, input logic [2:0] field);
        logic [5:0] idx;
        idx = {3'b000, body} * 6'd7 + {3'b000, field};
        body_field = flat[idx*64 +: 64];
    endfunction

    // ---- retire view (needed before issue: bypass + scoreboard clear) -------------------------
    logic [2:0]  ret_acc_v;                            // Accumulate ADD retiring per unit
    logic [3:0]  ret_lane [3];                         // Its (body*3+comp) lane
    logic [14:0] bc_clr;                               // Lanes clearing this cycle
    always_comb begin
        bc_clr = 15'd0;
        for (int u = 0; u < 3; u++) begin
            ret_acc_v[u] = add_ovalid_i[u] && add_sh_v[u][ADD_LAT-1] && !add_sh_ia[u][ADD_LAT-1];
            ret_lane[u]  = 4'(({1'b0, add_sh_b[u][ADD_LAT-1]} * 4'd3)
                              + {2'd0, add_sh_c[u][ADD_LAT-1]});
            if (ret_acc_v[u]) begin
                bc_clr[ret_lane[u]] = 1'b1;
            end
        end
    end

    // ---- issue logic ---------------------------------------------------------------------------
    // Per-unit issue records driving the FP buses and the shadow capture
    logic [2:0]  iss_v;                                // Issue valid per ADD unit
    logic        iss_sub  [3];                         // Subtract select
    logic [63:0] iss_a    [3];                         // Operand a
    logic [63:0] iss_b    [3];                         // Operand b
    logic        iss_ia   [3];                         // Integrate-add flag
    logic [2:0]  iss_body [3];                         // Target body
    logic [2:0]  iss_fld  [3];                         // Target field
    logic [1:0]  iss_comp [3];                         // Target component
    logic [14:0] bc_set;                               // Lanes issued this cycle
    logic [14:0] lane_hold;                            // Scan: lane has an earlier unissued op
    logic [1:0]  slot_q [3];                           // Free-slot queue (unit ids)
    logic [1:0]  nslots;                               // Free slots this cycle (0..3)
    logic [1:0]  slots_used;                           // Slots consumed by the scan
    logic [1:0]  mslot_q [3];                          // Free MUL slot queue
    logic [1:0]  mslots;                               // Free MUL slots (0..3)
    logic [1:0]  mslots_used;                          // MUL slots consumed
    logic [3:0]  m_iss_l [3];                          // Issued integrate lane per MUL unit
    logic [14:0] integ_mul_set;                        // Integrate muls issuing this cycle
    logic [14:0] integ_add_set;                        // Integrate adds issuing this cycle
    // per-op scan temps
    logic [2:0]  e_body;                               // Op target body
    logic [1:0]  e_comp;                               // Op component
    logic [3:0]  e_lane;                               // Op lane
    logic [63:0] e_opa;                                // Op operand a (working or bypass)
    logic        e_byp;                                // Lane clears this cycle

    logic [2:0] p_body;                                // lane_pend decode temp
    always_comb begin
        lane_pend = 15'd0;
        p_body = 3'd0;
        for (int e = 0; e < N_ACC; e++) begin
            acc_valid_mask[e] = 32'(e / 6) < {24'd0, npairs_i};
            if (acc_valid_mask[e] && !acc_issued[e]) begin
                if ((e % 6) <= 2) begin
                    p_body = pairs_i[(e / 6)*16 +: 3];
                end else begin
                    p_body = pairs_i[(e / 6)*16+8 +: 3];
                end
                lane_pend[4'(({1'b0, p_body} * 4'd3) + {2'd0, 2'((e % 6) % 3)})] = 1'b1;
            end
        end
        acc_done = (acc_issued & acc_valid_mask) == acc_valid_mask;
    end

    always_comb begin
        add_valid_o = 3'b000;
        add_sub_o   = 3'b000;
        add_a_o     = '0;
        add_b_o     = '0;
        mul_valid_o = 3'b000;
        mul_a_o     = '0;
        mul_b_o     = '0;
        iss_v       = 3'b000;
        for (int u = 0; u < 3; u++) begin
            m_iss_l[u] = 4'd0;
        end
        bc_set      = 15'd0;
        lane_hold   = 15'd0;
        acc_iss_set = '0;
        for (int u = 0; u < 3; u++) begin
            iss_sub[u]  = 1'b0;
            iss_a[u]    = 64'd0;
            iss_b[u]    = 64'd0;
            iss_ia[u]   = 1'b0;
            iss_body[u] = 3'd0;
            iss_fld[u]  = 3'd0;
            iss_comp[u] = 2'd0;
            slot_q[u]   = 2'd0;
        end
        // free-slot queue
        nslots = 2'd0;
        for (int u = 0; u < 3; u++) begin
            if (add_free_i[u]) begin
                slot_q[nslots] = u[1:0];
                nslots = nslots + 2'd1;
            end
        end
        slots_used = 2'd0;
        e_body = 3'd0;
        e_comp = 2'd0;
        e_lane = 4'd0;
        e_opa  = 64'd0;
        e_byp  = 1'b0;
        // in-order scan: an op may issue iff no earlier unissued op holds its lane
        for (int e = 0; e < N_ACC; e++) begin
            if (run_i && acc_valid_mask[e] && !acc_issued[e]) begin
                if ((e % 6) <= 2) begin
                    e_body = pairs_i[(e / 6)*16 +: 3];
                end else begin
                    e_body = pairs_i[(e / 6)*16+8 +: 3];
                end
                e_comp = 2'((e % 6) % 3);
                e_lane = 4'(({1'b0, e_body} * 4'd3) + {2'd0, e_comp});
                e_byp  = bc_clr[e_lane];
                if (!lane_hold[e_lane] && force_ready_i[e / 6]
                    && (!busy_bc[e_lane] || e_byp) && slots_used < nslots) begin
                    // bypass operand: the retiring unit's result for this lane (R5)
                    e_opa = body_field(working_flat_i, e_body, 3'({1'b0, e_comp} + 3'd3));
                    if (busy_bc[e_lane] && e_byp) begin
                        for (int u = 0; u < 3; u++) begin
                            if (ret_acc_v[u] && ret_lane[u] == e_lane) begin
                                e_opa = add_r_i[u*64 +: 64];
                            end
                        end
                    end
                    iss_v[slot_q[slots_used]]      = 1'b1;
                    iss_sub[slot_q[slots_used]]    = ((e % 6) <= 2);
                    iss_a[slot_q[slots_used]]      = e_opa;
                    iss_b[slot_q[slots_used]]      = force_flat_i[e*64 +: 64];
                    iss_ia[slot_q[slots_used]]     = 1'b0;
                    iss_body[slot_q[slots_used]]   = e_body;
                    iss_fld[slot_q[slots_used]]    = 3'({1'b0, e_comp} + 3'd3);
                    iss_comp[slot_q[slots_used]]   = e_comp;
                    bc_set[e_lane]  = 1'b1;
                    acc_iss_set[e]  = 1'b1;
                    slots_used = slots_used + 2'd1;
                end
                lane_hold[e_lane] = 1'b1;          // later same-lane ops wait (chain order)
            end
        end
        // integrate adds: ready lanes take the remaining slots (accumulate has priority)
        integ_add_set = 15'd0;
        for (int l = 0; l < 15; l++) begin
            if (run_i && integ_mul_v[l[3:0]] && !integ_add_issued[l[3:0]]
                && slots_used < nslots) begin
                iss_v[slot_q[slots_used]]    = 1'b1;
                iss_sub[slot_q[slots_used]]  = 1'b0;
                iss_a[slot_q[slots_used]]    = body_field(working_flat_i, 3'(l / 3), 3'(l % 3));
                iss_b[slot_q[slots_used]]    = integ_mul_r[l];
                iss_ia[slot_q[slots_used]]   = 1'b1;
                iss_body[slot_q[slots_used]] = 3'(l / 3);
                iss_fld[slot_q[slots_used]]  = 3'(l % 3);
                iss_comp[slot_q[slots_used]] = 2'(l % 3);
                integ_add_set[l[3:0]] = 1'b1;
                slots_used = slots_used + 2'd1;
            end
        end
        // drive the FP ADD buses from the records
        for (int u = 0; u < 3; u++) begin
            add_valid_o[u] = iss_v[u];
            add_sub_o[u]   = iss_sub[u];
            add_a_o[u*64 +: 64] = iss_a[u];
            add_b_o[u*64 +: 64] = iss_b[u];
        end
        // integrate muls: per-lane readiness (uArch §3.1 — a lane's dt*v issues as soon as
        // its own accumulate chain is issued AND retired, other lanes still in flight), up to
        // all free MUL slots per cycle
        mslot_q[0] = 2'd0; mslot_q[1] = 2'd0; mslot_q[2] = 2'd0;
        mslots = 2'd0;
        for (int u = 0; u < 3; u++) begin
            if (mul_free_i[u]) begin
                mslot_q[mslots] = u[1:0];
                mslots = mslots + 2'd1;
            end
        end
        mslots_used = 2'd0;
        integ_mul_set = 15'd0;
        for (int l = 0; l < 15; l++) begin
            if (run_i && !lane_pend[l[3:0]] && !busy_bc[l[3:0]] && !integ_mul_issued[l[3:0]]
                && mslots_used < mslots) begin
                mul_valid_o[mslot_q[mslots_used]] = 1'b1;
                mul_a_o[mslot_q[mslots_used]*64 +: 64] = dt_i;
                mul_b_o[mslot_q[mslots_used]*64 +: 64] =
                    body_field(working_flat_i, 3'(l / 3), 3'(l % 3 + 3));
                m_iss_l[mslot_q[mslots_used]] = l[3:0];
                integ_mul_set[l[3:0]] = 1'b1;
                mslots_used = mslots_used + 2'd1;
            end
        end
    end

    logic [7:0]  acc_total;                            // 6 * NPAIRS (NPAIRS <= 10 — R10)
    assign acc_total = 8'({4'd0, npairs_i[3:0]} * 8'd6);
    logic [2:0]  retire_cnt;                           // Ops retiring this cycle (0..3 ADD + 0..1 MUL)

    always_comb begin
        retire_cnt = 3'd0;
        for (int u = 0; u < 3; u++) begin
            if (add_ovalid_i[u] && add_sh_v[u][ADD_LAT-1]) begin
                retire_cnt = retire_cnt + 3'd1;
            end
            if (mul_ovalid_i[u] && mul_sh_v[u][MUL_LAT-1]) begin
                retire_cnt = retire_cnt + 3'd1;
            end
        end
    end

    // ---- sequential state ----------------------------------------------------------------------
    always_ff @(posedge clk) begin
        // shadow pipes: capture the per-unit issue records
        for (int u = 0; u < 3; u++) begin
            add_sh_v[u][0]  <= iss_v[u];
            add_sh_ia[u][0] <= iss_ia[u];
            add_sh_b[u][0]  <= iss_body[u];
            add_sh_f[u][0]  <= iss_fld[u];
            add_sh_c[u][0]  <= iss_comp[u];
            for (int d = 1; d < ADD_LAT; d++) begin
                add_sh_v[u][d]  <= add_sh_v[u][d-1];
                add_sh_ia[u][d] <= add_sh_ia[u][d-1];
                add_sh_b[u][d]  <= add_sh_b[u][d-1];
                add_sh_f[u][d]  <= add_sh_f[u][d-1];
                add_sh_c[u][d]  <= add_sh_c[u][d-1];
            end
            mul_sh_v[u][0] <= mul_valid_o[u];
            mul_sh_l[u][0] <= m_iss_l[u];
            for (int d = 1; d < MUL_LAT; d++) begin
                mul_sh_v[u][d] <= mul_sh_v[u][d-1];
                mul_sh_l[u][d] <= mul_sh_l[u][d-1];
            end
        end
        // issue + scoreboard bookkeeping (issue wins over the retire clear on the same lane)
        acc_issued <= acc_issued | acc_iss_set;
        busy_bc    <= (busy_bc & ~bc_clr) | bc_set;
        integ_mul_issued <= integ_mul_issued | integ_mul_set;
        if ((integ_mul_issued | integ_mul_set) == 15'h7FFF) begin
            integ_mul_done <= 1'b1;
        end
        // retires (single accumulation — S1)
        retired <= retired + {5'd0, retire_cnt};
        for (int u = 0; u < 3; u++) begin
            if (mul_ovalid_i[u] && mul_sh_v[u][MUL_LAT-1]) begin
                integ_mul_v[mul_sh_l[u][MUL_LAT-1]] <= 1'b1;
                integ_mul_r[mul_sh_l[u][MUL_LAT-1]] <= mul_r_i[u*64 +: 64];
            end
        end
        integ_add_issued <= integ_add_issued | integ_add_set;
        // step reset
        if (step_start_i || !rst_n) begin
            acc_issued       <= '0;
            integ_mul_issued <= 15'd0;
            integ_mul_done   <= 1'b0;
            integ_mul_v      <= 15'd0;
            integ_add_issued <= 15'd0;
            retired          <= 8'd0;
            busy_bc          <= 15'd0;
            for (int u = 0; u < 3; u++) begin
                for (int d = 0; d < ADD_LAT; d++) begin
                    add_sh_v[u][d] <= 1'b0;
                end
                for (int d = 0; d < MUL_LAT; d++) begin
                    mul_sh_v[u][d] <= 1'b0;
                end
            end
        end
    end

    // ---- body RF write-back: one port per ADD unit (targets distinct by construction) ----------
    always_comb begin
        for (int u = 0; u < 3; u++) begin
            wr_en_o[u] = add_ovalid_i[u] && add_sh_v[u][ADD_LAT-1];
            wr_body_o[u*3 +: 3]   = add_sh_b[u][ADD_LAT-1];
            wr_field_o[u*3 +: 3]  = add_sh_ia[u][ADD_LAT-1]
                                    ? {1'b0, add_sh_f[u][ADD_LAT-1][1:0]}
                                    : add_sh_f[u][ADD_LAT-1];
            wr_data_o[u*64 +: 64] = add_r_i[u*64 +: 64];
        end
    end

`ifdef SIMULATION
    // Retiring ADD targets must be pairwise distinct (one op per (body,field) in flight —
    // the lane_hold scan admits at most one op per lane per cycle).
    always_comb begin
        for (int u = 0; u < 3; u++) begin
            for (int w = 0; w < 3; w++) begin
                if (u != w && wr_en_o[u] && wr_en_o[w]) begin
                    assert (wr_body_o[u*3 +: 3] != wr_body_o[w*3 +: 3]
                            || wr_field_o[u*3 +: 3] != wr_field_o[w*3 +: 3])
                        else $error("grape_accum: two retires to one (body,field)");
                end
            end
        end
    end
`endif

    assign all_done_o = acc_done && integ_mul_done
                        && (integ_add_issued == 15'h7FFF)
                        && (retired == acc_total + 8'd30);   // 6*NPAIRS acc + 15 muls + 15 adds

endmodule

`default_nettype wire
