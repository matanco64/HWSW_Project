`default_nettype none

// Module: grape_body_rf
// Purpose: Body state storage (uArch §5): working bank (read by the datapath, written by
//          accumulate/integrate) and committed bank (read by the AXI window while BUSY,
//          PRD-F10). All values IEEE-754 binary64. Field index f: 0..2 = position x,y,z,
//          3..5 = velocity x,y,z, 6 = mass. Flat flop arrays, flat read export + 3 write
//          ports on the working bank (grape_accum retires up to 3 ADDs per cycle to distinct
//          (body, field) targets — an SVA there guards distinctness); commit copies working -> committed in one cycle; load copies the
//          pending AXI window (driven by grape_regs) into BOTH banks at the accepted doorbell.
module grape_body_rf #(
    parameter int N_BODIES = 5                          // Bodies (PRD-F6)
) (
    input  logic                          clk,          // System clock
    input  logic                          rst_n,        // Active-low synchronous reset
    // Doorbell load: pending window -> both banks
    input  logic                          load_en_i,    // Load pulse (accepted doorbell)
    input  logic [N_BODIES*7*64-1:0]      load_flat_i,  // Pending body window, body-major, field-minor
    // Datapath read: full working bank exported flat (flop RF — reads are external muxes; the
    // force pipe needs up to 6 position reads in one cycle, uArch §7 schedule)
    output logic [N_BODIES*7*64-1:0]      working_flat_o,  // Working bank, flattened
    // Datapath write ports (working bank; velocity and position updates; targets distinct)
    input  logic [2:0]                    wr_en_i,      // Write enables (one per ADD unit)
    input  logic [3*3-1:0]                wr_body_i,    // Write body indices
    input  logic [3*3-1:0]                wr_field_i,   // Write field indices
    input  logic [3*64-1:0]               wr_data_i,    // Write data
    // Commit: working -> committed (step boundary / DONE / ABORTED)
    input  logic                          commit_en_i,  // Commit pulse
    output logic [N_BODIES*7*64-1:0]      committed_flat_o  // Committed bank, flattened (AXI read mux)
);

    logic [63:0] working   [N_BODIES*7];               // Working bank, index = body*7 + field
    logic [63:0] committed [N_BODIES*7];               // Committed bank
    logic [63:0] working_next   [N_BODIES*7];          // Next working values
    logic [63:0] committed_next [N_BODIES*7];          // Next committed values

    logic [5:0] wr_idx [3];                            // Write flat indices (body*7+field, <35)
    always_comb begin
        for (int p = 0; p < 3; p++) begin
            wr_idx[p] = {3'b000, wr_body_i[p*3 +: 3]} * 6'd7 + {3'b000, wr_field_i[p*3 +: 3]};
        end
    end

    always_comb begin
        for (int u = 0; u < N_BODIES * 7; u++) begin
            working_next[u]   = working[u];
            committed_next[u] = committed[u];
            if (load_en_i) begin
                working_next[u]   = load_flat_i[u*64 +: 64];
                committed_next[u] = load_flat_i[u*64 +: 64];
            end
            if (commit_en_i) begin
                committed_next[u] = working[u];
            end
            if (!rst_n) begin
                working_next[u]   = 64'd0;
                committed_next[u] = 64'd0;
            end
        end
        for (int p = 0; p < 3; p++) begin
            if (wr_en_i[p] && !load_en_i && rst_n) begin
                working_next[wr_idx[p]] = wr_data_i[p*64 +: 64];
            end
        end
    end

    always_ff @(posedge clk) begin
        for (int u = 0; u < N_BODIES * 7; u++) begin
            working[u]   <= working_next[u];
            committed[u] <= committed_next[u];
        end
    end

    always_comb begin
        for (int u = 0; u < N_BODIES * 7; u++) begin
            committed_flat_o[u*64 +: 64] = committed[u];
            working_flat_o[u*64 +: 64]   = working[u];
        end
    end

endmodule

`default_nettype wire
