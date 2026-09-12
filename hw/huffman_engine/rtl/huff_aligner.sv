`default_nettype none

// Module: huff_aligner
// Purpose: Bit aligner for the Huffman decode loop (docs/rtl_contracts.md, uArch section
//          2/3.1/5/8).  Accepts the 32-bit s_axis_bits stream, holds a 64-bit top-aligned
//          bit buffer plus a 2-beat prefetch FIFO (accepted-but-unconsumed <= 128 bits,
//          the MAS OVERFETCH cap: tready drops when the FIFO is full), and presents a
//          MAXLEN = 20-bit top-aligned peek window with 0..20-bit consumes and a
//          concurrent 32-bit refill.  Bit order is MSB-first: byte lane 0 bit 7 is the
//          stream's first bit (bzip2), so a beat is byte-swapped into the buffer.
//
//          START_BIT skip (uArch section 3.1 PREP): on start_i, cfg_start_bit_i bits are
//          discarded through the same buffer/consume datapath at up to 32 bits (one whole
//          word) per cycle, then the sub-word remainder; skip_done_o rises when the last
//          skipped bit is gone.  Contract note: the "whole-word discard then remainder"
//          behavior is realised as a 0..32-bit internal consume with concurrent refill --
//          same one-word-per-cycle rate, and the discarded words are consumed, keeping
//          them outside the 128-bit cap (MAS section 8 amendment).
//
//          Stream end (uArch section 8): TLAST + the lowest contiguous tkeep run give the
//          last valid bit; the window zero-pads past it (occ_ok_o then holds even with
//          occupancy < MAXLEN once the tail is fully in the buffer).  Consuming past the
//          last valid bit -- by a decode consume or a START_BIT beyond the buffer -- sets
//          the sticky underrun_o (cleared by start_i / reset).  Before TLAST, occupancy
//          < MAXLEN just drops occ_ok_o (a stall, never an error).  DEFLATE mode: the
//          bit-reversed 15-bit peek sits in window_o[19:5], window_o[4:0] = 0.
//
//          Protocol assumptions (documented, not checked): the decoder only consumes when
//          occ_ok_o = 1, so a consume can exceed the buffer occupancy only in the
//          zero-padded tail (the underrun case; consumption clamps at the last valid
//          bit).  External consumes before skip_done_o are ignored.  tkeep is all-ones
//          except on the TLAST beat (MAS section 2); non-TLAST tkeep is not read.
module huff_aligner (
    input  logic        clk,                // clock
    input  logic        rst_n,              // synchronous active-low reset

    // s_axis_bits: compressed byte stream, byte 0 of the stream in tdata[7:0]
    input  logic [31:0] s_axis_bits_tdata,  // little-endian byte lanes
    input  logic [3:0]  s_axis_bits_tkeep,  // contiguous-from-lane-0 on the TLAST beat
    input  logic        s_axis_bits_tlast,  // last word of the buffer
    input  logic        s_axis_bits_tvalid, // beat valid
    output logic        s_axis_bits_tready, // FIFO not full & enabled & stream not ended

    // control (from huff_ctrl / huff_regs)
    input  logic        start_i,            // 1-cycle pulse: begin the START_BIT skip
    input  logic [31:0] cfg_start_bit_i,    // first code bit within the buffer, UQ32.0
    input  logic        mode_deflate_i,     // 1 = DEFLATE window form (reversed 15b peek)
    input  logic        enable_i,           // stream accept enable (PREP/DECODE)
    input  logic [4:0]  consume_i,          // decode consume length 0..20, UQ5.0
    input  logic        consume_en_i,       // consume_i is valid this cycle

    // decode-facing view
    output logic [19:0] window_o,           // top-aligned MAXLEN peek (zero-padded tail)
    output logic        occ_ok_o,           // occupancy >= MAXLEN, or tail after TLAST
    output logic        skip_done_o,        // START_BIT skip finished (level)
    output logic        underrun_o,         // sticky: consumed past the last valid bit
    output logic        tail_o,             // TLAST absorbed, FIFO empty (zero-padded tail)
    output logic [6:0]  occ_real_o,         // real (unpadded) bits still in the buffer
    output logic [31:0] bits_consumed_o     // decode bits consumed since START_BIT, UQ32.0
);

  localparam logic [6:0] MAXLEN = 7'd20;  // peek window width (uArch section 2)

  // ---------------- registers ----------------
  logic [63:0] bitbuf_q;      // top-aligned bit buffer; bits below occ_q are 0
  logic [6:0]  occ_q;         // valid bits in bitbuf_q, UQ7.0 (0..64)
  logic [31:0] f0_data_q;     // FIFO head: byte-swapped, tkeep-masked beat bits
  logic [5:0]  f0_nbits_q;    // FIFO head: valid bit count (0/8/16/24/32), UQ6.0
  logic [31:0] f1_data_q;     // FIFO tail entry data
  logic [5:0]  f1_nbits_q;    // FIFO tail entry valid bit count, UQ6.0
  logic [1:0]  fifo_cnt_q;    // FIFO occupancy 0..2, UQ2.0
  logic        last_seen_q;   // a TLAST beat has been accepted
  logic        started_q;     // start_i seen since reset
  logic [31:0] skip_left_q;   // START_BIT bits still to discard, UQ32.0
  logic        skip_done_q;   // skip finished (level)
  logic        underrun_q;    // sticky underrun flag
  logic [31:0] bits_q;        // decode bits consumed since START_BIT, UQ32.0

  // ---------------- combinational declarations (declare before use) ----------------
  logic [31:0] conv_raw;      // beat byte-swapped, byte-lane bit 7 first (bzip2 ingest form)
  logic [31:0] conv;          // ingest bits in stream order (DEFLATE: RFC 1951 LSB-first per byte)
  logic [5:0]  beat_nbits;    // valid bits of the incoming beat, UQ6.0
  logic [31:0] beat_data;     // conv masked to the valid (top-aligned) bits
  logic        accept;        // s_axis_bits handshake this cycle
  logic        push;          // FIFO push this cycle
  logic        pop;           // FIFO pop (refill into the buffer) this cycle
  logic        tail_active;   // every accepted bit is in the buffer and TLAST was seen
  logic        skip_active;   // START_BIT skip in progress
  logic [6:0]  skip_cap;      // min(skip_left, 32), UQ7.0
  logic [6:0]  skip_chunk;    // min(skip_left, 32, occ): this cycle's skip consume, UQ7.0
  logic [6:0]  ext_req;       // qualified external consume request, UQ7.0
  logic [6:0]  req;           // selected consume request (skip wins), UQ7.0
  logic [6:0]  eff;           // request clamped at the buffer occupancy, UQ7.0
  logic [6:0]  occ_ac;        // occupancy after the consume, before refill, UQ7.0
  logic [1:0]  cnt_ap;        // FIFO count after the pop, UQ2.0
  logic        underrun_ev;   // underrun detected this cycle
  logic [19:0] win_norm;      // bzip2-form window (top 20 buffer bits)
  logic [19:0] win_defl;      // DEFLATE-form window (reversed 15b in [19:5])

  // next-state values
  logic [63:0] bitbuf_next;
  logic [6:0]  occ_next;
  logic [31:0] f0_data_next;
  logic [5:0]  f0_nbits_next;
  logic [31:0] f1_data_next;
  logic [5:0]  f1_nbits_next;
  logic [1:0]  fifo_cnt_next;
  logic        last_seen_next;
  logic        started_next;
  logic [31:0] skip_left_next;
  logic        skip_done_next;
  logic        underrun_next;
  logic [31:0] bits_next;

  // ---------------- beat conversion: byte swap + tkeep mask ----------------
  // The first stream bit of byte 0 must become the top buffer bit, so the beat is
  // byte-swapped; in DEFLATE mode each byte lane is additionally bit-reversed because
  // RFC 1951 packs bits LSB-first within bytes (MAS 0x104: START_BIT bit 0 = byte 0 MSB
  // in bzip2, LSB in DEFLATE — R23 resolution). On a TLAST beat only the lowest
  // contiguous tkeep run counts and the rest is zeroed (the swapped word is then
  // top-aligned valid bits over zeros, like the buffer itself).
  always_comb begin
    conv_raw = {s_axis_bits_tdata[7:0], s_axis_bits_tdata[15:8],
                s_axis_bits_tdata[23:16], s_axis_bits_tdata[31:24]};
    conv = conv_raw;
    if (mode_deflate_i) begin
      for (int unsigned lane = 0; lane < 4; lane++) begin
        for (int unsigned k = 0; k < 8; k++) begin
          conv[8 * lane + k] = conv_raw[8 * lane + 7 - k];
        end
      end
    end
    if (!s_axis_bits_tlast) begin
      beat_nbits = 6'd32;
      beat_data  = conv;
    end else if (!s_axis_bits_tkeep[0]) begin
      beat_nbits = 6'd0;
      beat_data  = 32'h0000_0000;
    end else if (!s_axis_bits_tkeep[1]) begin
      beat_nbits = 6'd8;
      beat_data  = conv & 32'hFF00_0000;
    end else if (!s_axis_bits_tkeep[2]) begin
      beat_nbits = 6'd16;
      beat_data  = conv & 32'hFFFF_0000;
    end else if (!s_axis_bits_tkeep[3]) begin
      beat_nbits = 6'd24;
      beat_data  = conv & 32'hFFFF_FF00;
    end else begin
      beat_nbits = 6'd32;
      beat_data  = conv;
    end
  end

  // ---------------- handshake, consume selection, refill decision ----------------
  assign s_axis_bits_tready = enable_i && (fifo_cnt_q != 2'd2) && !last_seen_q;

  always_comb begin
    accept      = s_axis_bits_tready && s_axis_bits_tvalid;
    push        = accept;
    tail_active = last_seen_q && (fifo_cnt_q == 2'd0);
    tail_o      = tail_active;
    occ_real_o  = occ_q;
    skip_active = started_q && (skip_left_q != 32'd0);
    skip_cap    = (skip_left_q > 32'd32) ? 7'd32 : skip_left_q[6:0];
    skip_chunk  = (skip_cap > occ_q) ? occ_q : skip_cap;
    ext_req     = (skip_done_q && consume_en_i) ? {2'b00, consume_i} : 7'd0;
    req         = skip_active ? skip_chunk : ext_req;
    eff         = (req > occ_q) ? occ_q : req;
    occ_ac      = occ_q - eff;
    // refill: pop one FIFO word into the buffer whenever it fits (<= 32 bits occupied
    // after the consume) -- concurrent with the consume shift
    pop         = (fifo_cnt_q != 2'd0) && (occ_ac <= 7'd32);
    cnt_ap      = fifo_cnt_q - {1'b0, pop};
    // underrun: a decode consume reaching past the last valid bit, or the skip running
    // out of stream (START_BIT >= buffer bits -> underrun, skip never completes)
    underrun_ev = (skip_active && tail_active && (occ_q == 7'd0))
               || (skip_done_q && consume_en_i && tail_active
                   && ({2'b00, consume_i} > occ_q));
  end

  // ---------------- datapath next state ----------------
  always_comb begin
    // buffer: shift out the consumed bits, merge the popped word below the kept bits
    // (bits below occ_q are always 0, so OR-merge is exact)
    bitbuf_next = (bitbuf_q << eff) | (pop ? ({f0_data_q, 32'h0000_0000} >> occ_ac)
                                           : 64'h0);
    occ_next    = occ_ac + (pop ? {1'b0, f0_nbits_q} : 7'd0);

    // 2-deep shift-through FIFO
    f0_data_next  = f0_data_q;
    f0_nbits_next = f0_nbits_q;
    f1_data_next  = f1_data_q;
    f1_nbits_next = f1_nbits_q;
    if (pop) begin
      f0_data_next  = f1_data_q;
      f0_nbits_next = f1_nbits_q;
    end
    if (push) begin
      if (cnt_ap == 2'd0) begin
        f0_data_next  = beat_data;
        f0_nbits_next = beat_nbits;
      end else begin
        f1_data_next  = beat_data;
        f1_nbits_next = beat_nbits;
      end
    end
    fifo_cnt_next  = cnt_ap + {1'b0, push};
    last_seen_next = last_seen_q | (accept && s_axis_bits_tlast);

    // skip bookkeeping (start_i wins over an in-flight skip)
    started_next   = started_q | start_i;
    skip_left_next = skip_left_q;
    skip_done_next = skip_done_q;
    if (skip_active) begin
      skip_left_next = skip_left_q - {25'd0, eff};
    end
    if (skip_active && (skip_left_next == 32'd0)) begin
      skip_done_next = 1'b1;
    end
    if (start_i) begin
      skip_left_next = cfg_start_bit_i;
      skip_done_next = (cfg_start_bit_i == 32'd0);
      // R7: a new invocation restarts the stream — drop buffered/over-fetched bits and
      // the TLAST latch so tready can rise again (MAS: over-fetched beats dropped at DONE)
      bitbuf_next    = 64'h0;
      occ_next       = 7'd0;
      f0_nbits_next  = 6'd0;
      f1_nbits_next  = 6'd0;
      fifo_cnt_next  = 2'd0;
      last_seen_next = 1'b0;
    end

    // decode-bit counter (external consumes only; the skip is not counted -- MAS BITS
    // is "bits consumed since START_BIT"); counts the clamped amount on an underrun
    bits_next = bits_q;
    if (skip_done_q && consume_en_i) begin
      bits_next = bits_q + {25'd0, eff};
    end
    if (start_i) begin
      bits_next = 32'd0;
    end

    // sticky underrun, cleared by a new invocation
    underrun_next = start_i ? 1'b0 : (underrun_q | underrun_ev);

    // synchronous reset (folded into the next-state logic; always_ff stays simple)
    if (!rst_n) begin
      bitbuf_next    = 64'h0;
      occ_next       = 7'd0;
      f0_data_next   = 32'h0000_0000;
      f0_nbits_next  = 6'd0;
      f1_data_next   = 32'h0000_0000;
      f1_nbits_next  = 6'd0;
      fifo_cnt_next  = 2'd0;
      last_seen_next = 1'b0;
      started_next   = 1'b0;
      skip_left_next = 32'd0;
      skip_done_next = 1'b0;
      underrun_next  = 1'b0;
      bits_next      = 32'd0;
    end
  end

  // ---------------- state registers ----------------
  always_ff @(posedge clk) begin
    bitbuf_q    <= bitbuf_next;
    occ_q       <= occ_next;
    f0_data_q   <= f0_data_next;
    f0_nbits_q  <= f0_nbits_next;
    f1_data_q   <= f1_data_next;
    f1_nbits_q  <= f1_nbits_next;
    fifo_cnt_q  <= fifo_cnt_next;
    last_seen_q <= last_seen_next;
    started_q   <= started_next;
    skip_left_q <= skip_left_next;
    skip_done_q <= skip_done_next;
    underrun_q  <= underrun_next;
    bits_q      <= bits_next;
  end

  // ---------------- decode-facing view ----------------
  // bzip2: the top MAXLEN buffer bits.  DEFLATE: the next 15 bits bit-reversed into
  // window_o[19:5] (window_o[5] = next bit), window_o[4:0] = 0, so compares stay
  // MAXLEN-aligned and lengths 16..20 never match (uArch section 4).
  always_comb begin
    win_norm = bitbuf_q[63:44];
    win_defl = 20'd0;
    for (int unsigned k = 0; k < 15; k++) begin
      win_defl[5 + k] = bitbuf_q[63 - k];
    end
    window_o = mode_deflate_i ? win_defl : win_norm;
  end

  assign occ_ok_o        = tail_active || (occ_q >= MAXLEN);
  assign skip_done_o     = skip_done_q;
  assign underrun_o      = underrun_q;
  assign bits_consumed_o = bits_q;

endmodule

`default_nettype wire
