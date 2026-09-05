`default_nettype none

// Module: grape_force_pipe
// Purpose: Front-end issue engine of the step (uArch §2/§7): drives the shared FP64 units from
//          the GENERATED static reservation table (rtl/grape_sched_rom.svh, from
//          docs/gen_reservation.py). Per issue event: select operands from the per-pair scratch
//          registers / body working bank / DT, issue to the bound unit, and capture the result
//          back into scratch via a (pair, tag) shadow delay line per unit. Pairs with slot >=
//          NPAIRS are suppressed (bubbles; PRD-F6). Outputs the six force terms per pair with a
//          ready pulse, consumed in order by grape_accum. ADD units 0..2 and MUL units 0..2 are
//          shared with grape_accum: the static table owns a slot iff an event names it this
//          cycle; grape_accum may claim any other slot (issue_add/mul_free_o masks).
module grape_force_pipe #(
    parameter int N_BODIES    = 5,                     // Bodies
    parameter int N_PAIRS_MAX = 10                     // Pair slots in the table
) (
    input  logic                       clk,            // System clock
    input  logic                       rst_n,          // Active-low synchronous reset
    // Step control
    input  logic                       step_start_i,   // Pulse: cycle 0 of a step (FSM RUN entry)
    input  logic                       run_i,          // Step in progress (counter enable)
    input  logic [7:0]                 npairs_i,       // Latched NPAIRS
    input  logic [N_PAIRS_MAX*16-1:0]  pairs_i,        // Latched pair list ([7:0] i, [15:8] j)
    input  logic [63:0]                dt_i,           // Latched dt (binary64)
    input  logic [N_BODIES*7*64-1:0]   working_flat_i, // Body working bank (positions, masses)
    // FP unit issue interfaces (3 ADD, 3 MUL, 1 SQRT, 1 RCP)
    output logic [2:0]                 add_valid_o,    // ADD unit issue valids
    output logic [2:0]                 add_sub_o,      // ADD unit subtract selects
    output logic [3*64-1:0]            add_a_o,        // ADD unit operand a
    output logic [3*64-1:0]            add_b_o,        // ADD unit operand b
    input  logic [2:0]                 add_ovalid_i,   // ADD unit result valids
    input  logic [3*64-1:0]            add_r_i,        // ADD unit results
    output logic [2:0]                 mul_valid_o,    // MUL unit issue valids
    output logic [3*64-1:0]            mul_a_o,        // MUL unit operand a
    output logic [3*64-1:0]            mul_b_o,        // MUL unit operand b
    input  logic [2:0]                 mul_ovalid_i,   // MUL unit result valids
    input  logic [3*64-1:0]            mul_r_i,        // MUL unit results
    output logic                       sqrt_valid_o,   // SQRT issue valid
    output logic [63:0]                sqrt_a_o,       // SQRT operand
    input  logic                       sqrt_ovalid_i,  // SQRT result valid
    input  logic [63:0]                sqrt_r_i,       // SQRT result
    output logic                       rcp_valid_o,    // RCP issue valid
    output logic [63:0]                rcp_a_o,        // RCP operand
    input  logic                       rcp_ovalid_i,   // RCP result valid
    input  logic [63:0]                rcp_r_i,        // RCP result
    // Slots left free for grape_accum this cycle (per ADD/MUL unit)
    output logic [2:0]                 add_free_o,     // ADD unit not used by the table this cycle
    output logic [2:0]                 mul_free_o,     // MUL unit not used by the table this cycle
    // Force-term output (scratch view) for grape_accum
    output logic [N_PAIRS_MAX*6*64-1:0] force_flat_o,  // f_i x,y,z then f_j x,y,z per pair
    output logic [N_PAIRS_MAX-1:0]     force_ready_o   // All six force terms of pair k captured
);

    // verilator lint_off UNUSEDPARAM
    `include "grape_sched_rom.svh"
    // verilator lint_on UNUSEDPARAM

    localparam int N_TAGS  = 20;                       // Scratch tags (TAG_*)
    localparam int ADD_LAT = 3;                        // fp64_add latency
    localparam int MUL_LAT = 3;                        // fp64_mul latency
    localparam int SQRT_LAT = 30;                      // fp64_sqrt_srt latency
    localparam int RCP_LAT = 22;                       // fp64_rcp_nr latency

    // ---- step cycle counter --------------------------------------------------------------------
    logic [7:0] cyc;                                   // Cycle within the step (0..SCHED_STEP_CYCLES)
    logic [7:0] cyc_next;                              // Next cycle value
    always_comb begin
        cyc_next = cyc;
        if (step_start_i) begin
            cyc_next = 8'd0;
        end else if (run_i && cyc != 8'hFF) begin
            cyc_next = cyc + 8'd1;
        end
        if (!rst_n) begin
            cyc_next = 8'hFF;                          // Parked
        end
    end
    always_ff @(posedge clk) begin
        cyc <= cyc_next;
    end

    // ---- scratch: per pair, per tag ------------------------------------------------------------
    logic [63:0] scratch [N_PAIRS_MAX][N_TAGS];        // Captured results
    logic        scr_v   [N_PAIRS_MAX][N_TAGS];        // Capture valids (cleared at step start)

    // ---- per-unit shadow delay lines (pair, tag, valid) ----------------------------------------
    // Depth covers the longest unit latency; entry written at issue, read at out_valid time.
    // Shadow pipes as parallel arrays (Yosys 0.68 cannot parse struct members on unpacked
    // array elements): _v valid, _p pair slot, _t result tag.
    logic       add_sh_v [3][ADD_LAT];                 // ADD shadow valids
    logic [3:0] add_sh_p [3][ADD_LAT];                 // ADD shadow pair slots
    logic [4:0] add_sh_t [3][ADD_LAT];                 // ADD shadow tags
    logic       mul_sh_v [3][MUL_LAT];                 // MUL shadow valids
    logic [3:0] mul_sh_p [3][MUL_LAT];                 // MUL shadow pair slots
    logic [4:0] mul_sh_t [3][MUL_LAT];                 // MUL shadow tags
    logic       sqrt_sh_v [SQRT_LAT];                  // SQRT shadow valids
    logic [3:0] sqrt_sh_p [SQRT_LAT];                  // SQRT shadow pair slots
    logic [4:0] sqrt_sh_t [SQRT_LAT];                  // SQRT shadow tags
    logic       rcp_sh_v [RCP_LAT];                    // RCP shadow valids
    logic [3:0] rcp_sh_p [RCP_LAT];                    // RCP shadow pair slots
    logic [4:0] rcp_sh_t [RCP_LAT];                    // RCP shadow tags

    // ---- operand selection ---------------------------------------------------------------------
    function automatic logic [63:0] body_field(input logic [N_BODIES*7*64-1:0] flat,
                                               input logic [2:0] body, input logic [2:0] field);
        logic [5:0] idx;
        idx = {3'b000, body} * 6'd7 + {3'b000, field};
        body_field = flat[idx*64 +: 64];
    endfunction

    // Per event this cycle: compute operands. Tags: SUB_c a=pos_i[c] b=pos_j[c] (sub);
    // SQ_c a=b=SUB_c; A1 a=SQ_X b=SQ_Y; DSQ a=A1 b=SQ_Z; SQRT a=DSQ; D3 a=DSQ b=SQRT;
    // RCP a=D3; MAG a=DT b=RCP; B1M a=m_i b=MAG; B2M a=m_j b=MAG; F_I_c a=SUB_c b=B2M;
    // F_J_c a=SUB_c b=B1M.
    logic [3:0]  ev_pair;                              // Helper: current event pair
    logic [4:0]  ev_tag;                               // Helper: current event tag
    logic [2:0]  ev_unit;                              // Helper: current event unit binding
    // Per-unit issue capture (review R1: up to 6 events issue per cycle; ev_* holds only the
    // last one after the loop, so each unit records its own pair/tag here).
    logic [3:0]  add_iss_p [3];                        // ADD issue pair per unit
    logic [4:0]  add_iss_t [3];                        // ADD issue tag per unit
    logic [3:0]  mul_iss_p [3];                        // MUL issue pair per unit
    logic [4:0]  mul_iss_t [3];                        // MUL issue tag per unit
    logic [3:0]  sqrt_iss_p;                           // SQRT issue pair
    logic [4:0]  sqrt_iss_t;                           // SQRT issue tag
    logic [3:0]  rcp_iss_p;                            // RCP issue pair
    logic [4:0]  rcp_iss_t;                            // RCP issue tag
    // Result-forwarded scratch view (review R2: the table schedules consumers at
    // parent_issue + LAT, the exact cycle the result retires — scratch is written at the end of
    // that cycle, so reads go through this same-cycle forward). scr_fwd reads in the event loop
    // must index via the SCHED_*_V constant part-selects, never via the ev_* variables: with a
    // constant e the select folds at elaboration, keeping every read a constant index — through
    // ev_* Yosys mem2reg expands each read into a 200-way mux and synthesis does not terminate.
    logic [63:0] scr_fwd [N_PAIRS_MAX][N_TAGS];        // Scratch with retiring results forwarded
    logic [2:0]  bi;                                   // Body i of the pair
    logic [2:0]  bj;                                   // Body j of the pair
    logic [63:0] op_a;                                 // Selected operand a
    logic [63:0] op_b;                                 // Selected operand b
    logic        op_sub;                               // Subtract select for ADD ops

    // Built in its own always_comb: inside the 200-guard issue process every scr_fwd bit
    // would be muxed through the whole decision tree (PROC_MUX blow-up).
    always_comb begin
        for (int k = 0; k < N_PAIRS_MAX; k++) begin
            for (int g = 0; g < N_TAGS; g++) begin
                scr_fwd[k][g] = scratch[k][g];
            end
        end
        for (int u = 0; u < 3; u++) begin
            if (add_ovalid_i[u] && add_sh_v[u][ADD_LAT-1]) begin
                scr_fwd[add_sh_p[u][ADD_LAT-1]][add_sh_t[u][ADD_LAT-1]] = add_r_i[u*64 +: 64];
            end
            if (mul_ovalid_i[u] && mul_sh_v[u][MUL_LAT-1]) begin
                scr_fwd[mul_sh_p[u][MUL_LAT-1]][mul_sh_t[u][MUL_LAT-1]] = mul_r_i[u*64 +: 64];
            end
        end
        if (sqrt_ovalid_i && sqrt_sh_v[SQRT_LAT-1]) begin
            scr_fwd[sqrt_sh_p[SQRT_LAT-1]][sqrt_sh_t[SQRT_LAT-1]] = sqrt_r_i;
        end
        if (rcp_ovalid_i && rcp_sh_v[RCP_LAT-1]) begin
            scr_fwd[rcp_sh_p[RCP_LAT-1]][rcp_sh_t[RCP_LAT-1]] = rcp_r_i;
        end
    end

    always_comb begin
        add_valid_o = 3'b000;
        add_sub_o   = 3'b000;
        add_a_o     = '0;
        add_b_o     = '0;
        mul_valid_o = 3'b000;
        mul_a_o     = '0;
        mul_b_o     = '0;
        sqrt_valid_o = 1'b0;
        sqrt_a_o     = '0;
        rcp_valid_o  = 1'b0;
        rcp_a_o      = '0;
        add_free_o  = 3'b111;
        mul_free_o  = 3'b111;
        ev_pair = 4'd0;
        ev_tag  = 5'd0;
        ev_unit = 3'd0;
        for (int u = 0; u < 3; u++) begin
            add_iss_p[u] = 4'd0;
            add_iss_t[u] = 5'd0;
            mul_iss_p[u] = 4'd0;
            mul_iss_t[u] = 5'd0;
        end
        sqrt_iss_p = 4'd0;
        sqrt_iss_t = 5'd0;
        rcp_iss_p  = 4'd0;
        rcp_iss_t  = 5'd0;
        bi      = 3'd0;
        bj      = 3'd0;
        op_a    = 64'd0;
        op_b    = 64'd0;
        op_sub  = 1'b0;
        for (int e = 0; e < SCHED_EVENTS; e++) begin
            if (run_i && SCHED_CYCLE_V[e*8 +: 8] == cyc) begin
                ev_pair = SCHED_PAIR_V[e*4 +: 4];
                ev_tag  = SCHED_TAG_V[e*5 +: 5];
                ev_unit = SCHED_UNIT_V[e*3 +: 3];
                bi = pairs_i[ev_pair*16 +: 3];
                bj = pairs_i[ev_pair*16+8 +: 3];
                op_sub = 1'b0;
                op_a = 64'd0;
                op_b = 64'd0;
                if (SCHED_TAG_V[e*5 +: 5] <= TAG_SUB_Z[4:0]) begin
                    op_a   = body_field(working_flat_i, bi, ev_tag[2:0]);
                    op_b   = body_field(working_flat_i, bj, ev_tag[2:0]);
                    op_sub = 1'b1;
                end else if (SCHED_TAG_V[e*5 +: 5] <= TAG_SQ_Z[4:0]) begin
                    op_a = scr_fwd[SCHED_PAIR_V[e*4 +: 4]][SCHED_TAG_V[e*5 +: 5] - 5'd3];               // SQ_c -> SUB_c
                    op_b = op_a;
                end else if (SCHED_TAG_V[e*5 +: 5] == TAG_A1[4:0]) begin
                    op_a = scr_fwd[SCHED_PAIR_V[e*4 +: 4]][TAG_SQ_X];
                    op_b = scr_fwd[SCHED_PAIR_V[e*4 +: 4]][TAG_SQ_Y];
                end else if (SCHED_TAG_V[e*5 +: 5] == TAG_DSQ[4:0]) begin
                    op_a = scr_fwd[SCHED_PAIR_V[e*4 +: 4]][TAG_A1];
                    op_b = scr_fwd[SCHED_PAIR_V[e*4 +: 4]][TAG_SQ_Z];
                end else if (SCHED_TAG_V[e*5 +: 5] == TAG_SQRT[4:0]) begin
                    op_a = scr_fwd[SCHED_PAIR_V[e*4 +: 4]][TAG_DSQ];
                end else if (SCHED_TAG_V[e*5 +: 5] == TAG_D3[4:0]) begin
                    op_a = scr_fwd[SCHED_PAIR_V[e*4 +: 4]][TAG_DSQ];
                    op_b = scr_fwd[SCHED_PAIR_V[e*4 +: 4]][TAG_SQRT];
                end else if (SCHED_TAG_V[e*5 +: 5] == TAG_RCP[4:0]) begin
                    op_a = scr_fwd[SCHED_PAIR_V[e*4 +: 4]][TAG_D3];
                end else if (SCHED_TAG_V[e*5 +: 5] == TAG_MAG[4:0]) begin
                    op_a = dt_i;
                    op_b = scr_fwd[SCHED_PAIR_V[e*4 +: 4]][TAG_RCP];
                end else if (SCHED_TAG_V[e*5 +: 5] == TAG_B1M[4:0]) begin
                    op_a = body_field(working_flat_i, bi, 3'd6);
                    op_b = scr_fwd[SCHED_PAIR_V[e*4 +: 4]][TAG_MAG];
                end else if (SCHED_TAG_V[e*5 +: 5] == TAG_B2M[4:0]) begin
                    op_a = body_field(working_flat_i, bj, 3'd6);
                    op_b = scr_fwd[SCHED_PAIR_V[e*4 +: 4]][TAG_MAG];
                end else if (SCHED_TAG_V[e*5 +: 5] <= TAG_F_I_Z[4:0]) begin
                    op_a = scr_fwd[SCHED_PAIR_V[e*4 +: 4]][SCHED_TAG_V[e*5 +: 5] - 5'd14];              // F_I_c -> SUB_c (tag 14..16 -> 0..2)
                    op_b = scr_fwd[SCHED_PAIR_V[e*4 +: 4]][TAG_B2M];
                end else begin
                    op_a = scr_fwd[SCHED_PAIR_V[e*4 +: 4]][SCHED_TAG_V[e*5 +: 5] - 5'd17];              // F_J_c -> SUB_c (tag 17..19 -> 0..2)
                    op_b = scr_fwd[SCHED_PAIR_V[e*4 +: 4]][TAG_B1M];
                end
                if ({28'd0, ev_pair} < {24'd0, npairs_i}) begin
                    if (ev_unit <= 3'd2) begin
                        add_valid_o[ev_unit[1:0]] = 1'b1;
                        add_sub_o[ev_unit[1:0]]   = op_sub;
                        add_a_o[ev_unit[1:0]*64 +: 64] = op_a;
                        add_b_o[ev_unit[1:0]*64 +: 64] = op_b;
                        add_iss_p[ev_unit[1:0]] = ev_pair;
                        add_iss_t[ev_unit[1:0]] = ev_tag;
                    end else if (ev_unit <= 3'd5) begin
                        mul_valid_o[ev_unit[1:0]] = 1'b1;
                        mul_a_o[ev_unit[1:0]*64 +: 64] = op_a;
                        mul_b_o[ev_unit[1:0]*64 +: 64] = op_b;
                        mul_iss_p[ev_unit[1:0]] = ev_pair;
                        mul_iss_t[ev_unit[1:0]] = ev_tag;
                    end else if (ev_unit == 3'd6) begin
                        sqrt_valid_o = 1'b1;
                        sqrt_a_o     = op_a;
                        sqrt_iss_p   = ev_pair;
                        sqrt_iss_t   = ev_tag;
                    end else begin
                        rcp_valid_o = 1'b1;
                        rcp_a_o     = op_a;
                        rcp_iss_p   = ev_pair;
                        rcp_iss_t   = ev_tag;
                    end
                end
                // Table ownership blocks accum use of the slot even when suppressed (keeps
                // accum arbitration independent of NPAIRS).
                if (ev_unit <= 3'd2) begin
                    add_free_o[ev_unit[1:0]] = 1'b0;
                end else if (ev_unit <= 3'd5) begin
                    mul_free_o[ev_unit[1:0]] = 1'b0;
                end
            end
        end
    end

    // ---- shadow pipes and result capture -------------------------------------------------------
    always_ff @(posedge clk) begin
        for (int u = 0; u < 3; u++) begin
            add_sh_v[u][0] <= add_valid_o[u];
            add_sh_p[u][0] <= add_iss_p[u];
            add_sh_t[u][0] <= add_iss_t[u];
            for (int d = 1; d < ADD_LAT; d++) begin
                add_sh_v[u][d] <= add_sh_v[u][d-1];
                add_sh_p[u][d] <= add_sh_p[u][d-1];
                add_sh_t[u][d] <= add_sh_t[u][d-1];
            end
            mul_sh_v[u][0] <= mul_valid_o[u];
            mul_sh_p[u][0] <= mul_iss_p[u];
            mul_sh_t[u][0] <= mul_iss_t[u];
            for (int d = 1; d < MUL_LAT; d++) begin
                mul_sh_v[u][d] <= mul_sh_v[u][d-1];
                mul_sh_p[u][d] <= mul_sh_p[u][d-1];
                mul_sh_t[u][d] <= mul_sh_t[u][d-1];
            end
        end
        sqrt_sh_v[0] <= sqrt_valid_o;
        sqrt_sh_p[0] <= sqrt_iss_p;
        sqrt_sh_t[0] <= sqrt_iss_t;
        for (int d = 1; d < SQRT_LAT; d++) begin
            sqrt_sh_v[d] <= sqrt_sh_v[d-1];
            sqrt_sh_p[d] <= sqrt_sh_p[d-1];
            sqrt_sh_t[d] <= sqrt_sh_t[d-1];
        end
        rcp_sh_v[0] <= rcp_valid_o;
        rcp_sh_p[0] <= rcp_iss_p;
        rcp_sh_t[0] <= rcp_iss_t;
        for (int d = 1; d < RCP_LAT; d++) begin
            rcp_sh_v[d] <= rcp_sh_v[d-1];
            rcp_sh_p[d] <= rcp_sh_p[d-1];
            rcp_sh_t[d] <= rcp_sh_t[d-1];
        end
        // Capture results into scratch
        for (int u = 0; u < 3; u++) begin
            if (add_ovalid_i[u] && add_sh_v[u][ADD_LAT-1]) begin
                scratch[add_sh_p[u][ADD_LAT-1]][add_sh_t[u][ADD_LAT-1]] <= add_r_i[u*64 +: 64];
                scr_v[add_sh_p[u][ADD_LAT-1]][add_sh_t[u][ADD_LAT-1]]   <= 1'b1;
            end
            if (mul_ovalid_i[u] && mul_sh_v[u][MUL_LAT-1]) begin
                scratch[mul_sh_p[u][MUL_LAT-1]][mul_sh_t[u][MUL_LAT-1]] <= mul_r_i[u*64 +: 64];
                scr_v[mul_sh_p[u][MUL_LAT-1]][mul_sh_t[u][MUL_LAT-1]]   <= 1'b1;
            end
        end
        if (sqrt_ovalid_i && sqrt_sh_v[SQRT_LAT-1]) begin
            scratch[sqrt_sh_p[SQRT_LAT-1]][sqrt_sh_t[SQRT_LAT-1]] <= sqrt_r_i;
            scr_v[sqrt_sh_p[SQRT_LAT-1]][sqrt_sh_t[SQRT_LAT-1]]   <= 1'b1;
        end
        if (rcp_ovalid_i && rcp_sh_v[RCP_LAT-1]) begin
            scratch[rcp_sh_p[RCP_LAT-1]][rcp_sh_t[RCP_LAT-1]] <= rcp_r_i;
            scr_v[rcp_sh_p[RCP_LAT-1]][rcp_sh_t[RCP_LAT-1]]   <= 1'b1;
        end
        // Clear valids at step start
        if (step_start_i || !rst_n) begin
            for (int k = 0; k < N_PAIRS_MAX; k++) begin
                for (int g = 0; g < N_TAGS; g++) begin
                    scr_v[k][g] <= 1'b0;
                end
            end
            for (int u = 0; u < 3; u++) begin
                for (int d = 0; d < ADD_LAT; d++) begin
                    add_sh_v[u][d] <= 1'b0;
                end
                for (int d = 0; d < MUL_LAT; d++) begin
                    mul_sh_v[u][d] <= 1'b0;
                end
            end
            for (int d = 0; d < SQRT_LAT; d++) begin
                sqrt_sh_v[d] <= 1'b0;
            end
            for (int d = 0; d < RCP_LAT; d++) begin
                rcp_sh_v[d] <= 1'b0;
            end
        end
    end

    // ---- force outputs -------------------------------------------------------------------------
    always_comb begin
        for (int k = 0; k < N_PAIRS_MAX; k++) begin
            for (int c = 0; c < 3; c++) begin
                force_flat_o[(k*6+c)*64 +: 64]     = scratch[k][TAG_F_I_X + c];
                force_flat_o[(k*6+3+c)*64 +: 64]   = scratch[k][TAG_F_J_X + c];
            end
            force_ready_o[k] = scr_v[k][TAG_F_I_X] && scr_v[k][TAG_F_I_Y] && scr_v[k][TAG_F_I_Z]
                               && scr_v[k][TAG_F_J_X] && scr_v[k][TAG_F_J_Y] && scr_v[k][TAG_F_J_Z];
        end
    end

endmodule

`default_nettype wire
