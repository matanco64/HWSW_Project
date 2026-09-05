`default_nettype none

// Module: grape_accum
// Purpose: Ordered velocity accumulate + position integrate (uArch §3.3). Consumes pairs
//          strictly in order: for pair k (k < NPAIRS, force_ready), issues six plain add/sub
//          ops — v_i.c -= f_i.c (components x,y,z), then v_j.c += f_j.c — into ADD-unit slots
//          the static table leaves free, gated by a per-(body, component) busy scoreboard with
//          same-cycle clear bypass (preserves the emulation model's write order per chain;
//          PRD-F2/F3). After the last pair, integrates: for each (body, component), mul dt*v
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
    input  logic [N_PAIRS_MAX*16-1:0]   pairs_i,       // Latched pair list
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
    // Body RF write port
    output logic                        wr_en_o,       // Working-bank write enable
    output logic [2:0]                  wr_body_o,     // Write body index
    output logic [2:0]                  wr_field_o,    // Write field index
    output logic [63:0]                 wr_data_o,     // Write data
    // Step completion
    output logic                        all_done_o     // All accumulate+integrate ops retired
);

    localparam int ADD_LAT = 3;                        // fp64_add latency
    localparam int MUL_LAT = 3;                        // fp64_mul latency

    // ---- micro-op state ------------------------------------------------------------------------
    // Accumulate: 6 ops per pair, strictly in order across the (pair, op) sequence per chain
    // target; op n of pair k: n 0..2 -> v[i].c -= f_i.c ; n 3..5 -> v[j].c += f_j.c.
    logic [3:0] acc_pair;                              // Next pair to issue from
    logic [2:0] acc_op;                                // Next op within the pair (0..5)
    logic       acc_done;                              // All accumulate ops issued
    logic [4:0] integ_idx;                             // Next integrate lane (0..14: body*3+comp)
    logic       integ_mul_done;                        // All integrate muls issued
    logic [14:0] integ_mul_v;                          // dt*v result valid per lane
    logic [63:0] integ_mul_r [15];                     // dt*v results
    logic [14:0] integ_add_issued;                     // Integrate add issued per lane
    logic [7:0]  retired;                              // Retired op count (accumulate 6*NPAIRS + integrate 30)
    logic [14:0] busy_bc;                              // Scoreboard: (body,comp) in flight (accumulate)

    // Shadow pipes for result routing: (kind, body, field/lane)
    // Shadow pipes as parallel arrays (Yosys 0.68 struct-array limitation): valid, integrate-add
    // flag, target body, target field, integrate lane.
    logic       add_sh_v  [3][ADD_LAT];                // ADD shadow valids
    logic       add_sh_ia [3][ADD_LAT];                // ADD: op is an integrate add
    logic [2:0] add_sh_b  [3][ADD_LAT];                // ADD target body
    logic [2:0] add_sh_f  [3][ADD_LAT];                // ADD target field
    logic [1:0] add_sh_c  [3][ADD_LAT];                // ADD target component (review R3: field is comp+3 for v)
    logic       mul_sh_v  [3][MUL_LAT];                // MUL shadow valids (integrate muls)
    logic [3:0] mul_sh_l  [3][MUL_LAT];                // MUL integrate lane

    function automatic logic [63:0] body_field(input logic [N_BODIES*7*64-1:0] flat,
                                               input logic [2:0] body, input logic [2:0] field);
        logic [5:0] idx;
        idx = {3'b000, body} * 6'd7 + {3'b000, field};
        body_field = flat[idx*64 +: 64];
    endfunction

    // ---- issue logic ---------------------------------------------------------------------------
    logic [2:0] acc_body;                              // Current accumulate target body
    logic [1:0] acc_comp;                              // Current accumulate component
    logic [63:0] acc_force;                            // Current force term
    logic        acc_can_issue;                        // Ready + not hazarded
    logic [3:0]  bc_idx;                               // Scoreboard index body*3+comp
    logic        add_slot_found;                       // An ADD slot is free this cycle
    logic [1:0]  add_slot;                             // Chosen ADD slot
    logic        mul_slot_found;                       // A MUL slot is free
    logic [1:0]  mul_slot;                             // Chosen MUL slot
    logic        clr_bypass;                           // Target clears this cycle (retire bypass)
    logic [63:0] byp_data;                             // Retiring value forwarded on the bypass (R5)

    always_comb begin
        // defaults
        add_valid_o = 3'b000;
        add_sub_o   = 3'b000;
        add_a_o     = '0;
        add_b_o     = '0;
        mul_valid_o = 3'b000;
        mul_a_o     = '0;
        mul_b_o     = '0;
        // accumulate target decode
        if (acc_op <= 3'd2) begin
            acc_body = pairs_i[acc_pair*16 +: 3];
            acc_comp = acc_op[1:0];
        end else begin
            acc_body = pairs_i[acc_pair*16+8 +: 3];
            acc_comp = 2'(acc_op - 3'd3);
        end
        bc_idx    = 4'(({1'b0, acc_body} * 4'd3) + {2'd0, acc_comp});
        acc_force = force_flat_i[({28'd0, acc_pair}*32'd6 + {29'd0, acc_op})*64 +: 64];
        // retire bypass: an ADD retiring this cycle to the same (body,comp)
        clr_bypass = 1'b0;
        byp_data   = 64'd0;
        for (int u = 0; u < 3; u++) begin
            if (add_ovalid_i[u] && add_sh_v[u][ADD_LAT-1] && !add_sh_ia[u][ADD_LAT-1]) begin
                if (4'(({1'b0, add_sh_b[u][ADD_LAT-1]} * 4'd3)
                    + {2'd0, add_sh_c[u][ADD_LAT-1]}) == bc_idx) begin
                    clr_bypass = 1'b1;
                    byp_data   = add_r_i[u*64 +: 64];  // review R5: data bypass paired with the clear bypass
                end
            end
        end
        // slot pickers
        add_slot_found = 1'b0;
        add_slot       = 2'd0;
        for (int u = 2; u >= 0; u--) begin
            if (add_free_i[u]) begin
                add_slot_found = 1'b1;
                add_slot       = u[1:0];
            end
        end
        mul_slot_found = 1'b0;
        mul_slot       = 2'd0;
        for (int u = 2; u >= 0; u--) begin
            if (mul_free_i[u]) begin
                mul_slot_found = 1'b1;
                mul_slot       = u[1:0];
            end
        end
        // accumulate issue
        acc_can_issue = run_i && !acc_done
                        && ({28'd0, acc_pair} < {24'd0, npairs_i})
                        && force_ready_i[acc_pair]
                        && (!busy_bc[bc_idx] || clr_bypass)
                        && add_slot_found;
        if (run_i && !acc_done && {28'd0, acc_pair} >= {24'd0, npairs_i}) begin
            acc_can_issue = 1'b0;                      // handled in seq: skip pairs >= NPAIRS
        end
        if (acc_can_issue) begin
            add_valid_o[add_slot] = 1'b1;
            add_sub_o[add_slot]   = (acc_op <= 3'd2);  // v_i -= ; v_j +=
            add_a_o[add_slot*64 +: 64] = clr_bypass
                                         ? byp_data
                                         : body_field(working_flat_i, acc_body, 3'({1'b0, acc_comp} + 3'd3));
            add_b_o[add_slot*64 +: 64] = acc_force;
        end
        // integrate muls (after all accumulate issued AND retired for the lane's body? —
        // dependency: dt*v needs the FINAL v: all accumulate ops retired (busy_bc clear and
        // acc_done). Conservative per uArch §3.1: issue integrate muls once acc_done and no
        // accumulate op in flight for that (body,comp).
        // Review R6: per-lane gating (uArch §3.1 rejects phase gating): the lane's chain is final
        // once all accumulates are ISSUED (acc_done) and none is in flight for this (body,comp).
        if (run_i && acc_done && !integ_mul_done && mul_slot_found) begin
            if (!busy_bc[integ_idx[3:0]] && !integ_mul_v[integ_idx[3:0]]) begin
                mul_valid_o[mul_slot] = 1'b1;
                mul_a_o[mul_slot*64 +: 64] = dt_i;
                mul_b_o[mul_slot*64 +: 64] =
                    body_field(working_flat_i, integ_body, 3'({1'b0, integ_comp} + 3'd3));
            end
        end
        // integrate adds: r.c + dtv when the mul result arrived
        // (issued from the seq block via integ_add_pick)
        if (run_i && integ_add_pick_v && add_slot_found && !acc_can_issue) begin
            add_valid_o[add_slot] = 1'b1;
            add_sub_o[add_slot]   = 1'b0;
            add_a_o[add_slot*64 +: 64] = body_field(working_flat_i, integ_add_body, integ_add_comp);
            add_b_o[add_slot*64 +: 64] = integ_mul_r[integ_add_lane];
        end
    end

    // helper decodes for integrate
    logic [2:0] integ_body;                            // integ_idx / 3
    logic [1:0] integ_comp;                            // integ_idx % 3
    always_comb begin
        integ_body = 3'(integ_idx / 5'd3);
        integ_comp = 2'(integ_idx % 5'd3);
    end
    logic [7:0]  acc_total;                            // 6 * NPAIRS (NPAIRS <= N_PAIRS_MAX = 10
                                                       // enforced by ERR_PARAM, so 4 bits suffice — R10)
    assign acc_total = 8'({4'd0, npairs_i[3:0]} * 8'd6);
    logic [7:0]  acc_retired;                          // Retired accumulate ops

    // integrate add pick: lowest lane with mul result ready and add not yet issued
    logic        integ_add_pick_v;                     // A lane is ready for its add
    logic [3:0]  integ_add_lane;                       // Chosen lane
    logic [2:0]  integ_add_body;                       // Its body
    logic [2:0]  integ_add_comp;                       // Its component (position field)
    always_comb begin
        integ_add_pick_v = 1'b0;
        integ_add_lane   = 4'd0;
        for (int l = 14; l >= 0; l--) begin
            if (integ_mul_v[l] && !integ_add_issued[l]) begin
                integ_add_pick_v = 1'b1;
                integ_add_lane   = l[3:0];
            end
        end
        integ_add_body = 3'({28'd0, integ_add_lane} / 32'd3);
        integ_add_comp = 3'({28'd0, integ_add_lane} % 32'd3);
    end

    // ---- sequential state ----------------------------------------------------------------------
    always_ff @(posedge clk) begin
        // shadow pipes
        for (int u = 0; u < 3; u++) begin
            add_sh_v[u][0]  <= add_valid_o[u];
            if (integ_add_pick_v && !acc_can_issue) begin
                add_sh_ia[u][0] <= 1'b1;
                add_sh_b[u][0]  <= integ_add_body;
                add_sh_f[u][0]  <= integ_add_comp;
                add_sh_c[u][0]  <= integ_add_comp[1:0];
            end else begin
                add_sh_ia[u][0] <= 1'b0;
                add_sh_b[u][0]  <= acc_body;
                add_sh_f[u][0]  <= 3'({1'b0, acc_comp} + 3'd3);
                add_sh_c[u][0]  <= acc_comp;
            end
            for (int d = 1; d < ADD_LAT; d++) begin
                add_sh_v[u][d]  <= add_sh_v[u][d-1];
                add_sh_ia[u][d] <= add_sh_ia[u][d-1];
                add_sh_b[u][d]  <= add_sh_b[u][d-1];
                add_sh_f[u][d]  <= add_sh_f[u][d-1];
                add_sh_c[u][d]  <= add_sh_c[u][d-1];
            end
            mul_sh_v[u][0] <= mul_valid_o[u];
            mul_sh_l[u][0] <= integ_idx[3:0];
            for (int d = 1; d < MUL_LAT; d++) begin
                mul_sh_v[u][d] <= mul_sh_v[u][d-1];
                mul_sh_l[u][d] <= mul_sh_l[u][d-1];
            end
        end
        // issue bookkeeping
        if (acc_can_issue) begin
            busy_bc[bc_idx] <= 1'b1;
            if (acc_op == 3'd5) begin
                acc_op   <= 3'd0;
                acc_pair <= acc_pair + 4'd1;
                if ({28'd0, acc_pair} + 32'd1 >= {24'd0, npairs_i}) begin
                    acc_done <= 1'b1;
                end
            end else begin
                acc_op <= acc_op + 3'd1;
            end
        end
        if (run_i && !acc_done && {28'd0, acc_pair} >= {24'd0, npairs_i}) begin
            acc_done <= 1'b1;                          // NPAIRS == 0 or exhausted
        end
        if (run_i && acc_done && !integ_mul_done && mul_valid_o != 3'b000) begin
            if (integ_idx == 5'd14) begin
                integ_mul_done <= 1'b1;
            end
            integ_idx <= integ_idx + 5'd1;
        end
        // retires
        for (int u = 0; u < 3; u++) begin
            if (add_ovalid_i[u] && add_sh_v[u][ADD_LAT-1]) begin
                retired <= retired + 8'd1;
                if (!add_sh_ia[u][ADD_LAT-1]) begin
                    acc_retired <= acc_retired + 8'd1;
                    busy_bc[4'(({1'b0, add_sh_b[u][ADD_LAT-1]} * 4'd3)
                            + {2'd0, add_sh_c[u][ADD_LAT-1]})] <= 1'b0;
                end
            end
            if (mul_ovalid_i[u] && mul_sh_v[u][MUL_LAT-1]) begin
                integ_mul_v[mul_sh_l[u][MUL_LAT-1]] <= 1'b1;
                integ_mul_r[mul_sh_l[u][MUL_LAT-1]] <= mul_r_i[u*64 +: 64];
                retired <= retired + 8'd1;             // review R4: integrate muls count too
            end
        end
        if (integ_add_pick_v && add_valid_o != 3'b000 && !acc_can_issue) begin
            integ_add_issued[integ_add_lane] <= 1'b1;
        end
        // step reset
        if (step_start_i || !rst_n) begin
            acc_pair         <= 4'd0;
            acc_op           <= 3'd0;
            acc_done         <= 1'b0;
            integ_idx        <= 5'd0;
            integ_mul_done   <= 1'b0;
            integ_mul_v      <= 15'd0;
            integ_add_issued <= 15'd0;
            retired          <= 8'd0;
            acc_retired      <= 8'd0;
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

    // ---- body RF write-back --------------------------------------------------------------------
    // One retirement per cycle max on the write port? Up to 3 ADD retires/cycle are possible in
    // theory; the schedule model shows accumulate/integrate adds retire at most one per cycle on
    // distinct targets because issue is single-op-per-cycle in this engine. An SVA guards it.
    logic [1:0] wr_sel;                                // Retiring unit select
    always_comb begin
        wr_en_o    = 1'b0;
        wr_body_o  = 3'd0;
        wr_field_o = 3'd0;
        wr_data_o  = 64'd0;
        wr_sel     = 2'd0;
        for (int u = 2; u >= 0; u--) begin
            if (add_ovalid_i[u] && add_sh_v[u][ADD_LAT-1]) begin
                wr_en_o    = 1'b1;
                wr_sel     = u[1:0];
                wr_body_o  = add_sh_b[u][ADD_LAT-1];
                wr_field_o = add_sh_ia[u][ADD_LAT-1]
                             ? {1'b0, add_sh_f[u][ADD_LAT-1][1:0]}
                             : add_sh_f[u][ADD_LAT-1];
            end
        end
        wr_data_o = add_r_i[wr_sel*64 +: 64];
    end

`ifdef SIMULATION
    // At most one accumulate/integrate ADD may retire per cycle (single-issue engine).
    always_comb begin
        assert ($countones({add_ovalid_i[2] && add_sh_v[2][ADD_LAT-1],
                            add_ovalid_i[1] && add_sh_v[1][ADD_LAT-1],
                            add_ovalid_i[0] && add_sh_v[0][ADD_LAT-1]}) <= 1)
            else $error("grape_accum: multiple ADD retires in one cycle");
    end
`endif

    assign all_done_o = acc_done && integ_mul_done
                        && (integ_add_issued == 15'h7FFF)
                        && (retired == acc_total + 8'd30);   // 6·NPAIRS acc + 15 muls + 15 adds (R4)

endmodule

`default_nettype wire
