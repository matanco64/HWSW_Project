`default_nettype none

// File: mtf_list_inv.sv
// Purpose: SymbiYosys formal harness for mtf_list (testplan §3 lines 148-150, F-05 / K8). Proves the
//          THREE move-to-front list invariants. Read with the Yosys *slang* SystemVerilog frontend
//          (read_slang) so hierarchical references into the DUT (dut.lst[i], dut.rem_q) resolve to
//          the real internal signals -- the built-in Verilog frontend supports neither hierarchical
//          reads nor `bind`, so slang is required here (see synth/formal.sby).
//
//   (i)   permutation -- multiset(live entries lst[0..n_used-1]) == multiset(consumed used bytes) at
//         all times (no loss, no duplicate). Encoded per value v as a "present exactly once" count:
//         exactly one live entry carries value v iff v is a used byte already filled
//         (used_latched[v] && !dut.rem_q[v]); zero otherwise. count<=1 is distinctness, count==0 for
//         a non-consumed value is membership, and pinning the whole live multiset to (used & ~rem)
//         makes the property 1-inductive -- so `mode prove` (k-induction) closes on N_LIST=16. Once
//         INIT completes (rem==0) this is exactly multiset(live)==multiset(used).
//   (ii)  lookup-returns-pre-shift -- the rank-r byte read the cycle before a move (rd_byte_o) is the
//         value promoted to the front: byte0_o == $past(rd_byte_o).
//   (iii) post-shift positions -- after a move-to-front of rank r: list[0]==moved byte;
//         list[k]==$past(list[k-1]) for 1<=k<=r; list[k]==$past(list[k]) for k>r.
//
// N_LIST is a task parameter (read_slang -G): `prove`=16 (unbounded induction, so smtbmc closes),
// `bmc`=256 (PRD-K8, bounded depth >= 20). Env: rd_rank==mv_rank is assumed (the module's real use --
// read a rank then move THAT rank to the front) so the moved value is the port rd_byte_o and
// (ii)/(iii) need no dynamic memory index. Inputs otherwise free; reset assumed at t=0 (slang-safe
// past_valid idiom -- slang rejects reading a net inside an `initial` block).
module mtf_list_inv #(
    parameter int N_LIST   = 16,
    parameter bit MOVE_CHK  = 1'b1, // check the (ii)/(iii) move-semantics asserts (see g_shift note)
    parameter bit PERM_FULL   = 1'b1, // 1: universal present-mask permutation (inductive, N_LIST=16
                                      // `prove`); 0: two-probe permutation for the bounded N_LIST=256
                                      // `bmc` (the O(N^2) present-mask is intractable bit-blasted at 256)
    parameter bit PROBE_CHK   = 1'b1  // 1: include the two-probe lst-content asserts (PERM_FULL=0 mode)
) (
    input  logic                      clk,
    input  logic                      rst_n,
    input  logic                      init_start,
    input  logic [N_LIST-1:0]         used_map,
    input  logic [$clog2(N_LIST)-1:0] rd_rank,
    input  logic                      mv_en,
    input  logic [$clog2(N_LIST)-1:0] mv_rank,
    input  logic [7:0]                dbg_sel
);
    localparam int RW = $clog2(N_LIST);          // rank/index width
    localparam int CW = RW + 1;                  // count width (holds N_LIST)

    logic                init_busy_o;            // == dut.fill_active (a fill cycle in progress)
    logic [RW:0]         n_used_o;               // live-entry count (== dut.fill_idx_q)
    logic [7:0]          rd_byte_o, byte0_o, dbg_data_o;

    mtf_list #(.N_LIST(N_LIST)) dut (
        .clk(clk), .rst_n(rst_n),
        .init_start(init_start), .used_map(used_map),
        .init_busy_o(init_busy_o), .n_used_o(n_used_o),
        .rd_rank(rd_rank), .rd_byte_o(rd_byte_o), .byte0_o(byte0_o),
        .mv_en(mv_en), .mv_rank(mv_rank),
        .dbg_sel(dbg_sel), .dbg_data_o(dbg_data_o)
    );

    logic unused;
    assign unused = ^{dbg_data_o, 1'b0};

    // Reset assumed at t=0 (one cycle), free afterwards. Real use: read a rank, then move THAT rank.
    logic past_valid = 1'b0;
    always_ff @(posedge clk) past_valid <= 1'b1;
    always_comb if (!past_valid) assume (!rst_n);
    always_comb assume (mv_rank == rd_rank);

    // Environment contract (MAS §5 / F-10): the controller only ever moves a LIVE rank. An
    // out-of-range rank is rejected as ERR_RANK before any move reaches mtf_list, so a move with
    // mv_rank >= n_used never occurs. Without this the RTL faithfully shifts a dead entry to the
    // front (garbage-in) and corrupts the live prefix -- expected, not an RTL bug, so it is excluded.
    always_comb if (mv_en) assume ({1'b0, mv_rank} < n_used_o);

    // Latch the used map exactly when the DUT does (same posedge, same source) so the permutation
    // reference tracks the DUT's own rem_q consumption. Reset to 0 mirrors rem_q's reset.
    logic [N_LIST-1:0] used_latched = {N_LIST{1'b0}};
    always_ff @(posedge clk) begin
        if (!rst_n)          used_latched <= {N_LIST{1'b0}};
        else if (init_start) used_latched <= used_map;
    end

    // ---- (i) permutation ------------------------------------------------------------------------
    // Auxiliary invariant (true of the DUT: rem_q starts as used_map and only loses bits): every
    // not-yet-filled bit is a used byte. This is the inductive strengthening -- without it k-induction
    // starts from an unreachable state where rem_q holds a non-used bit, which the fill would then
    // place as a phantom live entry. (Cheap: one N-bit AND. Checked in both modes.)
    always_comb if (rst_n) assert ((dut.rem_q & ~used_latched) == {N_LIST{1'b0}});

    // Completeness/count: exactly as many live entries as consumed used bytes. (One popcount; cheap.
    // Implied by the present-mask below, but asserted directly so the two-probe mode still pins n_used.)
    function automatic logic [CW-1:0] popcnt(input logic [N_LIST-1:0] v);
        popcnt = {CW{1'b0}};
        for (int b = 0; b < N_LIST; b++) popcnt += CW'(v[b]);
    endfunction
    always_comb if (rst_n) assert (n_used_o == popcnt(used_latched & ~dut.rem_q));

    generate
    if (PERM_FULL) begin : g_perm_full
        // Every live entry is in the list's domain [0, N_LIST) (the RTL only stores an RW-bit index),
        // which guarantees each sets exactly one present bit below (pins the count for k-induction).
        integer jj;
        always_comb begin
            if (rst_n) begin
                for (jj = 0; jj < N_LIST; jj++) begin
                    if (CW'(jj) < n_used_o) assert (dut.lst[jj] < 9'(N_LIST));
                end
            end
        end
        // Scan the live prefix building the SET of values present, flagging any value seen twice.
        // (a) no duplicate == distinctness; (b) the set of live values == the consumed used bytes
        // (membership + no loss). Distinctness + set-equality + domain == permutation. Universal over
        // all entries every cycle, so it is a sound k-induction invariant (N_LIST=16 `prove`).
        logic [N_LIST-1:0] present;            // values held by some live entry
        logic              dup;                // some value held by two live entries
        integer ii;
        always_comb begin
            present = {N_LIST{1'b0}};
            dup     = 1'b0;
            for (ii = 0; ii < N_LIST; ii++) begin
                if (CW'(ii) < n_used_o) begin
                    if (present[dut.lst[ii][RW-1:0]]) dup = 1'b1;
                    present[dut.lst[ii][RW-1:0]] = 1'b1;
                end
            end
        end
        always_comb begin
            if (rst_n) begin
                assert (!dup);                                    // distinctness: no duplicate
                assert (present == (used_latched & ~dut.rem_q));  // membership + no loss
            end
        end
    end else begin : g_perm_probe
        // Bounded (N_LIST=256 `bmc`) permutation via two free probe ranks: the DUT exposes two live
        // reads -- rd_byte_o = lst[rd_rank] and dbg_data_o = lst[dbg_sel] (valid when dbg_sel<n_used).
        // Membership: a probed entry is a consumed used byte. Distinctness: two distinct live ranks
        // hold distinct values. With the count assert above (n_used == popcount(used & ~rem)) these
        // are exactly permutation. The probe indices are free, so within the bounded horizon smtbmc
        // checks every entry and every pair, avoiding the O(N^2) present-mask. (Sound only for BMC, not
        // k-induction; the unbounded proof is at N_LIST=16. See synth/formal.sby for the 256 depth note:
        // the fill's 256-deep priority encoder caps the reachable BMC depth well below PRD-K8's 20.)
        logic [8:0] nu9;   assign nu9   = n_used_o;             // n_used widened for the compares
        logic [7:0] rdsel; assign rdsel = rd_rank;              // rd_rank widened to 8b (RW<=8)
        always_comb begin
            if (rst_n && PROBE_CHK) begin
                if ({1'b0, dbg_sel} < nu9) begin
                    assert (used_latched[dbg_data_o] && !dut.rem_q[dbg_data_o]);   // membership
                end
                if (({1'b0, dbg_sel} < nu9) && ({1'b0, rdsel} < nu9) && (dbg_sel != rdsel)) begin
                    assert (dbg_data_o != rd_byte_o);                             // distinctness
                end
            end
        end
    end
    endgenerate

    // ---- (ii) lookup-returns-pre-shift & (iii) post-shift positions -----------------------------
    // A move happened last cycle iff it was not a fill cycle (init_busy low) and mv_en was set.
    // The move logic is structurally width-independent, so these are proven UNBOUNDED by the N_LIST=16
    // `prove` (k-induction) task; MOVE_CHK is cleared only for the N_LIST=256 bounded task, where the
    // per-rank $past shift asserts would be O(N_LIST^2) and add no coverage the induction lacks.
    generate
        if (MOVE_CHK) begin : g_move
            always_ff @(posedge clk) begin
                if (past_valid && $past(rst_n) && rst_n && !$past(init_busy_o) && $past(mv_en)) begin
                    assert (byte0_o == $past(rd_byte_o));               // (ii)
                    assert (dut.lst[0] == $past(rd_byte_o));            // (iii) rank 0 = moved byte
                end
            end
            genvar gk;
            for (gk = 1; gk < N_LIST; gk++) begin : g_shift
                always_ff @(posedge clk) begin
                    if (past_valid && $past(rst_n) && rst_n && !$past(init_busy_o) && $past(mv_en)) begin
                        if (RW'(gk) <= $past(mv_rank)) begin
                            // 1 <= k <= r: shift down
                            assert (dut.lst[gk] == $past(dut.lst[gk-1]));
                        end else begin
                            // k > r: unchanged
                            assert (dut.lst[gk] == $past(dut.lst[gk]));
                        end
                    end
                end
            end
        end
    endgenerate

    // ---- cover traces (cg_fml): filled list, lookups r=0/1/max, back-to-back moves --------------
    always_ff @(posedge clk) begin
        if (rst_n) begin
            cover (!init_busy_o && n_used_o > CW'(1));                                    // filled list
            cover (!init_busy_o && mv_en && mv_rank == RW'(0));                           // lookup r = 0
            cover (!init_busy_o && mv_en && mv_rank == RW'(1));                           // lookup r = 1
            cover (!init_busy_o && mv_en && n_used_o > CW'(1)
                                 && ({1'b0, mv_rank} == n_used_o - CW'(1)));              // lookup r=max
            cover (!init_busy_o && mv_en && $past(mv_en) && !$past(init_busy_o));         // back-to-back
        end
    end

endmodule

`default_nettype wire
