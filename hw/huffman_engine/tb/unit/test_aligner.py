"""Unit TB for huff_aligner (docs/rtl_contracts.md) against a pure-Python bit-slicer oracle.

Exact green command (from the repo root, after ``source hw/env.sh``)::

    make -C hw/huffman_engine sim TOPLEVEL=huff_aligner MODULE=unit.test_aligner \
        VERILOG_SOURCES="rtl/huff_aligner.sv"

Oracle: the reference bit string is built from the driven beats exactly as uArch section 2
defines the stream order -- within each beat, byte lane 0 first, and within each byte bit 7
first (bzip2 MSB-first order); a TLAST beat contributes only the bytes selected by the
lowest contiguous run of tkeep (MAS section 2).  After the START_BIT skip, every cycle in
which occ_ok_o is high the DUT's window_o must equal the next MAXLEN = 20 reference bits at
position start_bit + consumed, zero-padded past the end of the stream; in DEFLATE mode the
next 15 bits appear bit-reversed in window_o[19:5] with [4:0] = 0.

Invariants checked continuously (every falling edge once skip_done_o is seen):
  * accepted-unconsumed cap: accepted_bits - start_bit - consumed <= 128 (uArch section 5/8,
    MAS OVERFETCH cap; SKIP-discarded bits count as consumed, so start_bit is subtracted).
  * occ_ok_o safety: occ_ok_o == 1 before the TLAST beat was accepted implies at least
    MAXLEN real unconsumed bits exist (occ_ok may otherwise only come from the tail rule).
  * underrun_o stays 0 (sessions never consume past the last valid bit),
    bits_consumed_o == externally consumed bits.

TB/DUT synchronization: everything happens in one falling-edge loop (drive inputs and
sample outputs mid-cycle, race-free -- tready/occ_ok/window are functions of registered
state only, so their falling-edge value is their value at the next rising edge).
Consume lengths are 1..20 when issued (gaps modeled by not issuing); a directed test also
pokes consume_en with consume_i = 0 (contract allows 0..20 -- must be a no-op).
"""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge

MAXLEN = 20      # peek window width (uArch section 2)
CAP_BITS = 128   # accepted-unconsumed bound (uArch section 5/8: 64b buffer + 2x32b FIFO)
SEED = 1         # fixed RNG seed for reproducibility

# lowest contiguous run of tkeep from lane 0 -> valid bit count (MAS section 2)
KEEP_NBITS = {0x1: 8, 0x3: 16, 0x7: 24, 0xF: 32}


# --------------------------------------------------------------------------- oracle helpers
def beat_ref_bits(data, keep):
    """Reference bits contributed by one beat: lane 0..3, bit 7 first within each byte."""
    n = KEEP_NBITS[keep]
    return "".join(format((data >> (8 * lane)) & 0xFF, "08b") for lane in range(n // 8))


def gen_stream(rng, n_words, last_keep=0xF):
    """Random n_words-beat stream; returns (beats, ref_bits). beats = (data, keep, last)."""
    beats = []
    ref = []
    for i in range(n_words):
        data = rng.getrandbits(32)
        last = i == n_words - 1
        keep = last_keep if last else 0xF
        beats.append((data, keep, last))
        ref.append(beat_ref_bits(data, keep))
    return beats, "".join(ref)


def expected_window(ref, pos, deflate):
    """Next MAXLEN reference bits at pos, zero-padded; DEFLATE: reversed 15 in [19:5]."""
    seg = ref[pos:pos + MAXLEN]
    seg = seg + "0" * (MAXLEN - len(seg))
    if deflate:
        return int(seg[:15][::-1], 2) << 5
    return int(seg, 2)


# --------------------------------------------------------------------------- DUT harness
async def init_dut(dut):
    """Start the clock (fresh per test), zero all inputs, apply synchronous reset."""
    Clock(dut.clk, 10, "ns").start()
    dut.s_axis_bits_tdata.value = 0
    dut.s_axis_bits_tkeep.value = 0
    dut.s_axis_bits_tlast.value = 0
    dut.s_axis_bits_tvalid.value = 0
    dut.start_i.value = 0
    dut.cfg_start_bit_i.value = 0
    dut.mode_deflate_i.value = 0
    dut.enable_i.value = 0
    dut.consume_i.value = 0
    dut.consume_en_i.value = 0
    dut.rst_n.value = 0
    for _ in range(4):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    dut.enable_i.value = 1


async def pulse_start(dut, start_bit):
    """One-cycle start_i pulse latching cfg_start_bit_i (driven mid-cycle, race-free)."""
    await FallingEdge(dut.clk)
    dut.cfg_start_bit_i.value = start_bit
    dut.start_i.value = 1
    await FallingEdge(dut.clk)
    dut.start_i.value = 0


class Session:
    """One invocation: drive a stream + consume sequence, check every invariant per cycle."""

    def __init__(self, dut, rng, beats, ref, start_bit, *, deflate=False,
                 src_gap=0.0, cons_gap=0.0, consume_hi=MAXLEN, stop_margin=0):
        self.dut = dut
        self.rng = rng
        self.beats = beats
        self.ref = ref
        self.start_bit = start_bit
        self.deflate = deflate
        self.src_gap = src_gap
        self.cons_gap = cons_gap
        self.consume_hi = consume_hi
        self.stop_margin = stop_margin  # leave this many bits unconsumed at session end
        self.total = len(ref)
        # model state
        self.beat_idx = 0
        self.cur_beat = None       # beat currently held on the bus (until accepted)
        self.accepted_bits = 0     # valid bits of every accepted beat
        self.consumed = 0          # externally consumed bits (post-skip)
        self.pending_accept = None  # nbits of the beat handshaking at the next rising edge
        self.pending_consume = 0   # consume length applied at the next rising edge
        self.last_accepted = False
        self.saw_tready_low = False
        self.skip_done_seen = False

    # -- per-cycle phases ------------------------------------------------------------
    def commit(self):
        """Account for the events that committed at the rising edge just passed."""
        if self.pending_accept is not None:
            self.accepted_bits += self.pending_accept
            if self.cur_beat[2]:
                self.last_accepted = True
            self.cur_beat = None
            self.beat_idx += 1
            self.pending_accept = None
        self.consumed += self.pending_consume
        self.pending_consume = 0

    def check(self):
        dut = self.dut
        assert int(dut.underrun_o.value) == 0, "spurious underrun_o"
        skip_done = int(dut.skip_done_o.value) == 1
        if self.skip_done_seen:
            assert skip_done, "skip_done_o deasserted after asserting"
        if not skip_done:
            return
        self.skip_done_seen = True
        pos = self.start_bit + self.consumed
        unconsumed = self.accepted_bits - pos
        assert unconsumed <= CAP_BITS, (
            f"cap violated: accepted {self.accepted_bits} - consumed {pos} = "
            f"{unconsumed} > {CAP_BITS}")
        assert int(dut.bits_consumed_o.value) == self.consumed, (
            f"bits_consumed_o {int(dut.bits_consumed_o.value)} != model {self.consumed}")
        if int(dut.occ_ok_o.value) == 1:
            if not self.last_accepted:
                assert unconsumed >= MAXLEN, (
                    f"occ_ok_o high with only {unconsumed} real bits before TLAST")
            exp = expected_window(self.ref, pos, self.deflate)
            got = int(dut.window_o.value)
            assert got == exp, (
                f"window mismatch at pos {pos}: expected {exp:05x} got {got:05x} "
                f"(ref[{pos}:{pos + MAXLEN}]={self.ref[pos:pos + MAXLEN]!r})")

    def drive(self):
        dut = self.dut
        rng = self.rng
        # stream side: hold the current beat until accepted; gaps only between beats
        if self.cur_beat is None and self.beat_idx < len(self.beats):
            if rng.random() >= self.src_gap:
                self.cur_beat = self.beats[self.beat_idx]
        if self.cur_beat is not None:
            data, keep, last = self.cur_beat
            dut.s_axis_bits_tdata.value = data
            dut.s_axis_bits_tkeep.value = keep
            dut.s_axis_bits_tlast.value = 1 if last else 0
            dut.s_axis_bits_tvalid.value = 1
        else:
            dut.s_axis_bits_tvalid.value = 0
        # consume side: only when the DUT presents a valid window, never past the end
        dut.consume_en_i.value = 0
        remaining = self.total - self.stop_margin - (self.start_bit + self.consumed)
        if (self.skip_done_seen and int(dut.occ_ok_o.value) == 1 and remaining > 0
                and rng.random() >= self.cons_gap):
            c = rng.randint(1, min(self.consume_hi, remaining))
            dut.consume_i.value = c
            dut.consume_en_i.value = 1
            self.pending_consume = c
        # handshake resolution (tready is a function of registered state: stable to the edge)
        if self.cur_beat is not None and int(dut.s_axis_bits_tready.value) == 1:
            self.pending_accept = KEEP_NBITS[self.cur_beat[1]]
        if int(dut.s_axis_bits_tready.value) == 0:
            self.saw_tready_low = True

    async def run(self, max_cycles=None):
        """Falling-edge loop until everything up to stop_margin is consumed."""
        dut = self.dut
        goal = self.total - self.stop_margin - self.start_bit
        if max_cycles is None:
            max_cycles = 500 + 8 * (self.total + len(self.beats))
        for _ in range(max_cycles):
            await FallingEdge(dut.clk)
            self.commit()
            self.check()
            if self.consumed >= goal:
                break
            self.drive()
        else:
            raise AssertionError(
                f"session timeout: consumed {self.consumed}/{goal} bits "
                f"(skip_done={int(dut.skip_done_o.value)}, "
                f"occ_ok={int(dut.occ_ok_o.value)}, accepted={self.accepted_bits})")
        dut.consume_en_i.value = 0
        dut.s_axis_bits_tvalid.value = 0

    async def finish_checks(self):
        """After consuming to the exact stream end: tail is zero-padded and quiescent."""
        dut = self.dut
        for _ in range(4):
            await FallingEdge(dut.clk)
            self.commit()
            self.check()
        assert int(dut.occ_ok_o.value) == 1, "occ_ok_o low at fully-consumed tail"
        assert int(dut.window_o.value) == 0, "window_o not zero-padded at stream end"
        assert int(dut.bits_consumed_o.value) == self.total - self.start_bit


async def run_session(dut, rng, n_words, start_bit, **kw):
    """Reset, generate a stream, pulse start, run a full session to the stream end."""
    last_keep = kw.pop("last_keep", 0xF)
    await init_dut(dut)
    beats, ref = gen_stream(rng, n_words, last_keep)
    dut.mode_deflate_i.value = 1 if kw.get("deflate", False) else 0
    await pulse_start(dut, start_bit)
    ses = Session(dut, rng, beats, ref, start_bit, **kw)
    await ses.run()
    if ses.stop_margin == 0:
        await ses.finish_checks()
    return ses


# --------------------------------------------------------------------------- tests
@cocotb.test()
async def test_smoke_basic(dut):
    """Small gap-free stream, start_bit 0: every window against the oracle, full drain."""
    rng = random.Random(SEED)
    await run_session(dut, rng, 8, 0)


@cocotb.test()
async def test_random_streams(dut):
    """Random streams x random consume lengths with tvalid/consume gaps (both modes of gap)."""
    rng = random.Random(SEED + 1)
    for trial in range(8):
        n_words = rng.randint(5, 30)
        start_bit = rng.choice([0, rng.randint(0, 40)])
        await run_session(
            dut, rng, n_words, start_bit,
            last_keep=rng.choice([0x1, 0x3, 0x7, 0xF]),
            src_gap=rng.choice([0.0, 0.3, 0.6]),
            cons_gap=rng.choice([0.0, 0.3, 0.6]))


@cocotb.test()
async def test_start_bit_alignments(dut):
    """START_BIT skip at 0 / word-aligned / +-1 boundaries (uArch section 3.1 SKIP)."""
    rng = random.Random(SEED + 2)
    for sb in [0, 1, 31, 32, 33, 63, 64, 65]:
        await run_session(dut, rng, 12, sb)


@cocotb.test()
async def test_start_bit_large(dut):
    """Large skip (~9000 bits, sub-word remainder) with concurrent stream delivery."""
    rng = random.Random(SEED + 3)
    await run_session(dut, rng, 300, 8991, src_gap=0.1)


@cocotb.test()
async def test_start_bit_equals_stream_end(dut):
    """START_BIT == total bits: skip completes, tail is empty, no underrun until consumed."""
    rng = random.Random(SEED + 4)
    await init_dut(dut)
    beats, ref = gen_stream(rng, 6)
    await pulse_start(dut, len(ref))
    ses = Session(dut, rng, beats, ref, len(ref))
    await ses.run()  # goal is 0 consumed; loop still delivers the stream via drive()
    # deliver remaining beats (goal was met immediately); push them through
    for _ in range(200):
        await FallingEdge(dut.clk)
        ses.commit()
        ses.check()
        if ses.last_accepted and int(dut.skip_done_o.value) == 1 \
                and int(dut.occ_ok_o.value) == 1:
            break
        ses.drive()
    assert int(dut.skip_done_o.value) == 1, "skip_done_o low with START_BIT == stream bits"
    assert int(dut.underrun_o.value) == 0
    assert int(dut.window_o.value) == 0, "window not zero-padded when skip ate the stream"


@cocotb.test()
async def test_tkeep_partial_tail(dut):
    """TLAST beats with tkeep 0x1/0x3/0x7: last-valid-bit tracking and zero-padded tail."""
    rng = random.Random(SEED + 5)
    for keep in [0x1, 0x3, 0x7, 0xF]:
        await run_session(dut, rng, 7, 0, last_keep=keep)


@cocotb.test()
async def test_underrun_consume_past_tail(dut):
    """Consume past the last valid bit -> underrun_o (sticky), consumption clamped."""
    rng = random.Random(SEED + 6)
    for margin in [0, 1, 5, 19]:
        await init_dut(dut)
        beats, ref = gen_stream(rng, 6, rng.choice([0x1, 0x3, 0x7, 0xF]))
        await pulse_start(dut, 0)
        ses = Session(dut, rng, beats, ref, 0, stop_margin=margin)
        await ses.run()
        # wait for the tail to be fully absorbed (occ_ok via the zero-pad rule)
        for _ in range(50):
            await FallingEdge(dut.clk)
            ses.commit()
            ses.check()
            if int(dut.occ_ok_o.value) == 1:
                break
            ses.drive()
        assert int(dut.occ_ok_o.value) == 1
        # window is the zero-padded remainder; now consume more than remains
        over = rng.randint(margin + 1, MAXLEN)
        dut.consume_i.value = over
        dut.consume_en_i.value = 1
        await FallingEdge(dut.clk)
        dut.consume_en_i.value = 0
        assert int(dut.underrun_o.value) == 1, (
            f"underrun_o low after consuming {over} of {margin} remaining bits")
        for _ in range(5):
            await FallingEdge(dut.clk)
            assert int(dut.underrun_o.value) == 1, "underrun_o not sticky"
        # consumption clamps at the last valid bit (BITS stays exact, MAS F13)
        assert int(dut.bits_consumed_o.value) == len(ref), (
            "bits_consumed_o ran past the last valid bit")


@cocotb.test()
async def test_underrun_start_bit_past_end(dut):
    """START_BIT beyond the buffer -> underrun during SKIP, skip_done_o never asserts."""
    rng = random.Random(SEED + 7)
    await init_dut(dut)
    beats, ref = gen_stream(rng, 5, 0x7)
    await pulse_start(dut, len(ref) + 37)
    ses = Session(dut, rng, beats, ref, 0, stop_margin=len(ref))  # drive stream only
    for _ in range(300):
        await FallingEdge(dut.clk)
        ses.commit()
        if int(dut.underrun_o.value) == 1:
            break
        ses.drive()
    assert int(dut.underrun_o.value) == 1, "no underrun for START_BIT past the buffer end"
    for _ in range(10):
        await FallingEdge(dut.clk)
        assert int(dut.skip_done_o.value) == 0, "skip_done_o asserted past the buffer end"
        assert int(dut.underrun_o.value) == 1, "underrun_o not sticky during SKIP"


@cocotb.test()
async def test_deflate_window(dut):
    """DEFLATE mode: bit-reversed 15-bit peek in window[19:5], [4:0] = 0, incl. the tail."""
    rng = random.Random(SEED + 8)
    for trial in range(4):
        ses = await run_session(
            dut, rng, rng.randint(6, 20), rng.choice([0, 3, 32]),
            deflate=True, consume_hi=15,
            last_keep=rng.choice([0x3, 0xF]),
            src_gap=rng.choice([0.0, 0.4]))
        assert ses.skip_done_seen


@cocotb.test()
async def test_backpressure_cap(dut):
    """Stalled consumer + eager source: tready must drop (2-beat FIFO full), cap holds."""
    rng = random.Random(SEED + 9)
    ses = await run_session(dut, rng, 20, 0, cons_gap=0.9)
    assert ses.saw_tready_low, "tready never dropped with a stalled consumer (no cap?)"


@cocotb.test()
async def test_occ_ok_gating(dut):
    """Starved source: occ_ok_o gates consumption; windows stay exact through refills."""
    rng = random.Random(SEED + 10)
    await run_session(dut, rng, 15, 5, src_gap=0.9)


@cocotb.test()
async def test_consume_zero_noop(dut):
    """consume_en_i with consume_i = 0 (contract allows 0..20) is a no-op."""
    rng = random.Random(SEED + 11)
    await init_dut(dut)
    beats, ref = gen_stream(rng, 6)
    await pulse_start(dut, 0)
    ses = Session(dut, rng, beats, ref, 0, cons_gap=1.0)  # never consumes on its own
    # deliver a few beats, then poke a zero-length consume
    for _ in range(20):
        await FallingEdge(dut.clk)
        ses.commit()
        ses.check()
        ses.drive()
    for _ in range(60):
        await FallingEdge(dut.clk)
        ses.commit()
        ses.check()
        if int(dut.skip_done_o.value) == 1 and int(dut.occ_ok_o.value) == 1:
            break
        ses.drive()
    dut.s_axis_bits_tvalid.value = 0
    win_before = int(dut.window_o.value)
    dut.consume_i.value = 0
    dut.consume_en_i.value = 1
    await FallingEdge(dut.clk)
    dut.consume_en_i.value = 0
    assert int(dut.window_o.value) == win_before, "consume_i = 0 moved the window"
    assert int(dut.bits_consumed_o.value) == 0, "consume_i = 0 counted bits"
    assert int(dut.underrun_o.value) == 0
