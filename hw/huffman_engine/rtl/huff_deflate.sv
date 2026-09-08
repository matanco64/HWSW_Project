`default_nettype none

// Module: huff_deflate
// Purpose: DEFLATE post-decode resolve (uArch §2, II=2): classifies the symtab symbol
//          (literal / length 257..285 / EOB 256 / invalid 286-287), sequences the extra-bit
//          consumes and the distance decode (set 1) with its extra bits, and produces the
//          m_sym beat fields (RFC 1951 §3.2.5 base/extra tables as packed localparams).
//          Idle and transparent in bzip2 mode. The engine owns the aligner consume port and
//          the set-override while active.
module huff_deflate (
    input  logic        clk,            // System clock
    input  logic        rst_n,          // Active-low synchronous reset
    input  logic        mode_deflate_i, // Latched MODE (engine active)
    input  logic        decode_en_i,    // huff_ctrl DECODE state
    input  logic        stall_i,        // Downstream stall (skid full)
    // Resolve input: registered C1 result of the last C0 decode
    input  logic        c1_valid_i,     // A symbol resolved this cycle
    input  logic [8:0]  c1_sym_i,       // symtab symbol
    input  logic        c1_sym_valid_i, // symtab valid bit
    // Aligner access for extra bits (granted while busy_o)
    input  logic [19:0] window_i,       // Top-aligned window (reversed 15b in [19:5])
    input  logic        occ_ok_i,       // Window valid
    output logic [4:0]  extra_consume_o, // Extra-bit consume request (0 = none)
    // Distance decode result (C0 view with set 1 forced)
    input  logic [4:0]  dist_len_i,     // Distance code length
    input  logic [8:0]  dist_sym_i,     // Distance symbol index 0..29 (via symtab)
    input  logic        dist_c1_valid_i, // Distance symbol resolved
    // Sequencing
    output logic        busy_o,         // Engine owns C0 (blocks normal issue)
    output logic        force_dist_set_o, // Force cur_set = 1 for the distance decode
    output logic        dist_issue_o,   // Request a C0 decode with set 1
    output logic        err_symbol_o,   // Invalid code (286/287, dist 30/31, symtab invalid)
    // Beat out (TYPE 2 = length/distance pair, TYPE 0 = literal — MAS §2)
    output logic        emit_o,         // Push a beat
    output logic [31:0] emit_data_o     // Beat
);

    // RFC 1951 length codes 257..285: extra bits and base (3..258)
    localparam logic [29*3-1:0]  LEN_EXTRA = {3'd0, 3'd5,3'd5,3'd5,3'd5, 3'd4,3'd4,3'd4,3'd4,
                                              3'd3,3'd3,3'd3,3'd3, 3'd2,3'd2,3'd2,3'd2,
                                              3'd1,3'd1,3'd1,3'd1, 3'd0,3'd0,3'd0,3'd0,
                                              3'd0,3'd0,3'd0,3'd0};
    localparam logic [29*9-1:0]  LEN_BASE = {9'd258, 9'd227,9'd195,9'd163,9'd131,
                                             9'd115,9'd99,9'd83,9'd67, 9'd59,9'd51,9'd43,
                                             9'd35, 9'd31,9'd27,9'd23,9'd19, 9'd17,9'd15,
                                             9'd13,9'd11, 9'd10,9'd9,9'd8,9'd7, 9'd6,9'd5,
                                             9'd4,9'd3};
    // Distance codes 0..29: extra bits and base (1..24577)
    localparam logic [30*4-1:0]  DIST_EXTRA = {4'd13,4'd13, 4'd12,4'd12, 4'd11,4'd11,
                                               4'd10,4'd10, 4'd9,4'd9, 4'd8,4'd8, 4'd7,4'd7,
                                               4'd6,4'd6, 4'd5,4'd5, 4'd4,4'd4, 4'd3,4'd3,
                                               4'd2,4'd2, 4'd1,4'd1, 4'd0,4'd0, 4'd0,4'd0};
    localparam logic [30*15-1:0] DIST_BASE = {15'd24577,15'd16385, 15'd12289,15'd8193,
                                              15'd6145,15'd4097, 15'd3073,15'd2049,
                                              15'd1537,15'd1025, 15'd769,15'd513,
                                              15'd385,15'd257, 15'd193,15'd129, 15'd97,15'd65,
                                              15'd49,15'd33, 15'd25,15'd17, 15'd13,15'd9,
                                              15'd7,15'd5, 15'd4,15'd3, 15'd2,15'd1};

    typedef enum logic [2:0] {
        D_IDLE,                         // bzip2 / waiting for a resolve
        D_LEXTRA,                       // consume length extra bits
        D_DIST,                         // issue the distance decode (set 1)
        D_DWAIT,                        // wait its C1
        D_DEXTRA,                       // consume distance extra bits
        D_EMIT                          // push the TYPE-2 beat
    } dstate_t;

    dstate_t     st, st_n;              // FSM state
    logic [8:0]  len_val, len_val_n;    // Resolved copy length (3..258)
    logic [4:0]  lidx;                  // Length code index (sym-257)
    logic [15:0] dist_val, dist_val_n;  // Resolved distance (1..24577... 15b + carry)
    logic [4:0]  didx;                  // Distance code index
    logic [2:0]  lextra;                // Length extra count
    logic [3:0]  dextra;                // Distance extra count
    logic [12:0] extra_bits;            // Extracted extra-bit value (LSB-first per RFC)

    // extra-bit value (R14): the RAW aligner window has the next stream bit at [5],
    // ascending — DEFLATE extras are LSB-first, so the value is simply the slice starting
    // at bit 5 masked to n bits
    function automatic logic [12:0] rev_extract(input logic [19:0] w, input logic [3:0] n);
        logic [12:0] sl;
        logic        pad_zero;
        pad_zero = |{w[19:18], w[4:0]};  // [19:18] beyond the 13 extras; [4:0] zero pad
        sl = w[17:5];                   // up to 13 extra bits, LSB (next stream bit) at w[5]
        rev_extract = (sl & ((13'd1 << n) - 13'd1)) & {13{!pad_zero | pad_zero}};
    endfunction

    always_comb begin
        st_n         = st;
        len_val_n    = len_val;
        dist_val_n   = dist_val;
        extra_consume_o = 5'd0;
        dist_issue_o = 1'b0;
        emit_o       = 1'b0;
        emit_data_o  = 32'd0;
        err_symbol_o = 1'b0;
        lidx  = 5'(c1_sym_i - 9'd257);
        didx  = dist_sym_i[4:0];
        lextra = LEN_EXTRA[32'(lidx)*3 +: 3];
        dextra = DIST_EXTRA[32'(didx)*4 +: 4];
        extra_bits = rev_extract(window_i, {1'b0, len_val[2:0]});  // placeholder, refined below
        case (st)
            D_IDLE: begin
                if (mode_deflate_i && decode_en_i && c1_valid_i) begin
                    if (!c1_sym_valid_i || c1_sym_i >= 9'd286) begin
                        err_symbol_o = 1'b1;
                    end else if (c1_sym_i >= 9'd257) begin
                        len_val_n = LEN_BASE[32'(lidx)*9 +: 9];
                        st_n = D_LEXTRA;
                    end
                    // literals/EOB are emitted by the main path (TYPE 0 / TYPE 3)
                end
            end
            D_LEXTRA: begin
                if (occ_ok_i && !stall_i) begin
                    extra_bits = rev_extract(window_i, {1'b0, lextra});
                    len_val_n  = len_val + 9'(extra_bits);
                    extra_consume_o = {2'd0, lextra};
                    st_n = D_DIST;
                end
            end
            D_DIST: begin
                if (occ_ok_i && !stall_i) begin
                    dist_issue_o = 1'b1;
                    st_n = D_DWAIT;
                end
            end
            D_DWAIT: begin
                if (dist_c1_valid_i) begin
                    if (dist_sym_i >= 9'd30 || dist_len_i == 5'd0) begin
                        err_symbol_o = 1'b1;
                        st_n = D_IDLE;
                    end else begin
                        dist_val_n = 16'(DIST_BASE[32'(didx)*15 +: 15]);
                        st_n = D_DEXTRA;
                    end
                end
            end
            D_DEXTRA: begin
                if (occ_ok_i && !stall_i) begin
                    extra_bits = rev_extract(window_i, dextra);
                    dist_val_n = dist_val + 16'(extra_bits);
                    extra_consume_o = {1'd0, dextra};
                    st_n = D_EMIT;
                end
            end
            D_EMIT: begin
                if (!stall_i) begin
                    emit_o = 1'b1;
                    // TYPE 2 beat: [8:0] length value, [11:9] TYPE=2, [27:12] distance
                    emit_data_o = {4'd0, dist_val, 3'd2, len_val};
                    st_n = D_IDLE;
                end
            end
            default: st_n = D_IDLE;
        endcase
        if (!rst_n || !mode_deflate_i || !decode_en_i) begin
            st_n = D_IDLE;
        end
    end

    always_ff @(posedge clk) begin
        st       <= st_n;
        len_val  <= len_val_n;
        dist_val <= dist_val_n;
    end

    assign busy_o = (st != D_IDLE);
    assign force_dist_set_o = (st == D_DIST) || (st == D_DWAIT);

endmodule

`default_nettype wire
