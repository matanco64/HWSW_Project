`default_nettype none

// Module: skid_buffer
// Purpose: Single-stage ready/valid pipeline register with a one-entry skid
//          slot. Both in_ready and the output side are driven from flops, so
//          the buffer breaks the combinational ready path in both directions
//          while sustaining one transfer per cycle (full throughput).
module skid_buffer #(
    parameter int WIDTH = 32                 // Payload width in bits
) (
    input  logic             clk,            // System clock
    input  logic             rst_n,          // Active-low synchronous reset
    input  logic             in_valid,       // Upstream has data
    output logic             in_ready,       // Buffer can accept data (registered)
    input  logic [WIDTH-1:0] in_data,        // Upstream payload
    output logic             out_valid,      // Registered output valid
    input  logic             out_ready,      // Downstream accepts data
    output logic [WIDTH-1:0] out_data        // Registered output payload
);

    logic             skid_valid;            // Skid slot holds a word
    logic [WIDTH-1:0] skid_data;             // Skid slot payload
    logic             skid_valid_next;       // Next skid_valid
    logic [WIDTH-1:0] skid_data_next;        // Next skid_data
    logic             out_valid_next;        // Next out_valid
    logic [WIDTH-1:0] out_data_next;         // Next out_data
    logic             in_fire;               // Upstream handshake
    logic             out_fire;              // Downstream handshake

    // in_ready is a pure function of a flop: accept whenever the skid slot is free.
    assign in_ready = ~skid_valid;

    always_comb begin
        in_fire         = in_valid & in_ready;
        out_fire        = out_valid & out_ready;
        skid_valid_next = skid_valid;
        skid_data_next  = skid_data;
        out_valid_next  = out_valid;
        out_data_next   = out_data;

        if (skid_valid) begin
            // Slot occupied: upstream is stalled; drain the slot into the output register.
            if (out_fire) begin
                out_valid_next  = 1'b1;
                out_data_next   = skid_data;
                skid_valid_next = 1'b0;
            end
        end else begin
            if (out_fire || !out_valid) begin
                // Output register free this cycle: pass the incoming word straight through.
                out_valid_next = in_fire;
                out_data_next  = in_fire ? in_data : out_data;
            end else if (in_fire) begin
                // Output stalled but upstream fired: park the word in the skid slot.
                skid_valid_next = 1'b1;
                skid_data_next  = in_data;
            end
        end
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            skid_valid <= 1'b0;
            out_valid  <= 1'b0;
        end else begin
            skid_valid <= skid_valid_next;
            out_valid  <= out_valid_next;
        end
    end

    always_ff @(posedge clk) begin
        skid_data <= skid_data_next;
        out_data  <= out_data_next;
    end

endmodule

`default_nettype wire
