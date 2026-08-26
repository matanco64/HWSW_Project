`default_nettype none

// Module: ready_valid_fifo
// Purpose: Synchronous FIFO with ready/valid handshakes on both sides.
//          DEPTH must be a power of two; pointers carry one extra wrap bit so
//          full and empty are distinguished without a separate count register.
module ready_valid_fifo #(
    parameter int WIDTH = 32,                // Payload width in bits
    parameter int DEPTH = 16                 // Number of entries (power of two)
) (
    input  logic             clk,            // System clock
    input  logic             rst_n,          // Active-low synchronous reset
    input  logic             in_valid,       // Upstream has data
    output logic             in_ready,       // FIFO not full
    input  logic [WIDTH-1:0] in_data,        // Upstream payload
    output logic             out_valid,      // FIFO not empty
    input  logic             out_ready,      // Downstream accepts data
    output logic [WIDTH-1:0] out_data        // Head-of-queue payload
);

    localparam int AW = (DEPTH > 1) ? $clog2(DEPTH) : 1;  // Address width

    logic [WIDTH-1:0] mem [DEPTH];           // Storage array
    logic [AW:0]      wr_ptr;                // Write pointer with wrap bit
    logic [AW:0]      rd_ptr;                // Read pointer with wrap bit
    logic [AW:0]      wr_ptr_next;           // Next write pointer
    logic [AW:0]      rd_ptr_next;           // Next read pointer
    logic             empty;                 // No entries stored
    logic             full;                  // DEPTH entries stored
    logic             wr_en;                 // Write handshake
    logic             rd_en;                 // Read handshake

    always_comb begin
        empty       = (wr_ptr == rd_ptr);
        full        = (wr_ptr[AW] != rd_ptr[AW]) && (wr_ptr[AW-1:0] == rd_ptr[AW-1:0]);
        in_ready    = ~full;
        out_valid   = ~empty;
        wr_en       = in_valid & in_ready;
        rd_en       = out_valid & out_ready;
        wr_ptr_next = wr_en ? wr_ptr + {{AW{1'b0}}, 1'b1} : wr_ptr;
        rd_ptr_next = rd_en ? rd_ptr + {{AW{1'b0}}, 1'b1} : rd_ptr;
        out_data    = mem[rd_ptr[AW-1:0]];
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            wr_ptr <= '0;
            rd_ptr <= '0;
        end else begin
            wr_ptr <= wr_ptr_next;
            rd_ptr <= rd_ptr_next;
        end
    end

    // Memory inference: conditional write is the one permitted always_ff exception.
    always_ff @(posedge clk) begin
        if (wr_en) begin
            mem[wr_ptr[AW-1:0]] <= in_data;
        end
    end

endmodule

`default_nettype wire
