`default_nettype none

// Module: huff_decoder
// Purpose: The C0 decode combinationals (uArch §2, ADR-0008 #1): 20 parallel one-sided
//          compares of the top-aligned window against the active set's left-aligned limits
//          (review U1 form), priority-encode the SMALLEST matching length, extract the code,
//          form the symtab index, and detect the C0-visible events (EOB latch match,
//          ERR_NOCODE). Purely combinational; the issue gate and counters live in huff_ctrl /
//          the top. Formats per uArch §4 (all UQn.0).
module huff_decoder #(
    parameter int MAXLEN = 20                          // Window/compare width (bzip2)
) (
    input  logic [MAXLEN-1:0]     window_i,            // Top-aligned peek (UQ20.0)
    // Active table set (flattened views from huff_tables)
    input  logic [MAXLEN*21-1:0]  limit_la_i,          // limit_la[l], l = 1..MAXLEN (UQ21.0 each)
    input  logic [MAXLEN*20-1:0]  first_code_i,        // first_code[l] (UQ20.0)
    input  logic [MAXLEN*11-1:0]  base_i,              // base[l] (UQ11.0)
    input  logic [10:0]           table_base_i,        // Set's symtab base (UQ11.0)
    input  logic [4:0]            eob_len_i,           // EOB length (0 = no EOB in this set)
    input  logic [MAXLEN-1:0]     eob_code_i,          // EOB code, right-aligned (UQ20.0)
    // Decoded outputs (valid the same cycle)
    output logic [4:0]            len_o,               // Decoded length l (1..MAXLEN; 0 = none)
    output logic [MAXLEN-1:0]     code_o,              // code_l = window >> (MAXLEN - l)
    output logic [10:0]           index_o,             // table_base + base[l] + (code - first_code[l])
    output logic                  match_o,             // A length matched
    output logic                  eob_o,               // Decoded symbol is the set's EOB
    output logic                  nocode_o             // No length matched (ERR_NOCODE)
);

    logic [MAXLEN-1:0] match_mask;                     // match(l) per length (bit l-1)
    logic [4:0]        len_n;                          // Priority-encoded smallest l
    logic [MAXLEN-1:0] code_n;                         // Extracted code bits
    logic [20:0]       lim;                            // Selected limit (loop temp)

    always_comb begin
        // one-sided compares: {1'b0, window} < limit_la[l]  (review U1 — ranges tile)
        for (int l = 1; l <= MAXLEN; l++) begin
            lim = limit_la_i[(l-1)*21 +: 21];
            match_mask[l-1] = {1'b0, window_i} < lim;
        end
        // smallest matching length wins
        len_n = 5'd0;
        for (int l = MAXLEN; l >= 1; l--) begin
            if (match_mask[l-1]) begin
                len_n = 5'(l);
            end
        end
        // code extraction: top l bits of the window, right-aligned
        code_n = 20'd0;
        if (len_n != 5'd0) begin
            code_n = window_i >> (5'(MAXLEN) - len_n);
        end
        len_o    = len_n;
        code_o   = code_n;
        match_o  = (len_n != 5'd0);
        nocode_o = (len_n == 5'd0);
        eob_o    = (len_n != 5'd0) && (eob_len_i != 5'd0)
                   && (len_n == eob_len_i) && (code_n == eob_code_i);
        // symtab index (uArch §4: sums bounded, no overflow past UQ11.0)
        index_o = 11'd0;
        if (len_n != 5'd0) begin
            index_o = table_base_i
                      + base_i[(32'(len_n)-1)*11 +: 11]
                      + 11'(code_n - first_code_i[(32'(len_n)-1)*20 +: 20]);
        end
    end

endmodule

`default_nettype wire
