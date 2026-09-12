"""tests_errors — error-injection tests (testplan F-09, F-10, F-26; MAS §4/§8).

Run: make -C hw/huffman_engine sim MODULE=tests_errors SIM_BUILD=sim_build_errs

Two cocotb tests, each a chain of invocations (flush_sources + fresh frames + full
W1C between invocations — the ErrInvSeq ends every invocation with STATUS<=0xFF06):

  errors_reject   F-09 every ERR_PARAM clause (doorbell rejected, no BUSY, config
                  unchanged, reject-fix-accept) + F-26 doorbell ERR_TABLE badlen.
  errors_runtime  F-26 build-time Kraft ERR_TABLE, F-10 ERR_NOCODE / ERR_SELECTOR
                  (range at symbol 0 and at a 50-boundary; exhausted) /
                  ERR_UNDERRUN (mid-code and PREP-time) / ERR_LIMIT (+ tie->DONE).

The HuffScoreboard (env.py v2) independently predicts each invocation's beats,
SYMBOLS and sticky outcome from golden primitives; the sequences only engineer the
stimulus. Golden is imported READ-ONLY below to confirm the ERR_NOCODE stimulus
really hits unassigned code space (canonical_model.Table.decode raises).

SKIPPED here (documented): the DEFLATE-specific ERR_TABLE badlen bins 16..20 (F-26)
— DEFLATE decode is gated behind F-25/R23 (byte-order reconciliation), so only the
bzip2 21..31 badlen half is driven; and test_errors::busy_writes (F-11) — covered by
the busy/abort test owner."""
import canonical_model as cm
import cocotb
from cocotb.triggers import Timer
from cocotbext.axi import AxiStreamFrame
from pyuvm import uvm_root

from env import (ALPHABET, LEN_BASE, MODE, N_TABLES, ST_DONE, ST_ELIMIT, ST_ENOCODE,
                 ST_EPARAM, ST_ESEL, ST_ETABLE, ST_EUNDER, SYMBOL_LIMIT)
from errors import (ErrInvSeq, GOOD_BITS, GOOD_LENGTHS, GOOD_SELS, GOOD_STREAM,
                    GOOD_SYMBOLS)
from test_huffman_engine import HuffBaseTest

# ---- hand-crafted streams over the known table [1,2,3,3] (codes 0,10,110,111) -------
# MSB-first packing per byte, as in tb/unit/test_top_smoke.py.
NOCODE_LENGTHS = [[2, 2, 2, 3]]          # Kraft 0.875: incomplete-LEGAL; 111 unassigned
NOCODE_STREAM = bytes([0x1E, 0x00])      # '00 01 111 0...' -> s0 s1 then ERR_NOCODE
KRAFT_LENGTHS = [[1, 1, 2, 3]]           # Kraft 1.375 > 1: build-time ERR_TABLE
UNDER_STREAM = bytes([0x5B])             # '0 10 110 11' -> s0 s1 s2, then 11<truncated>
LIMIT_STREAM = bytes([0x0E])             # '0 0 0 0 111' -> s0 s0 s0 s0 EOB (5 symbols)
FIFTY_STREAM = bytes(7)                  # 56 zero bits: 50+ s0 symbols, never EOB
BADLEN_WORD = 21 | (2 << 5) | (3 << 10) | (3 << 15)   # sym0 length 21 (>MAXLEN 20)


def _confirm_nocode_golden():
    """READ-ONLY golden check: NOCODE_STREAM's third code hits unassigned space."""
    t = cm.Table(NOCODE_LENGTHS[0], cm.MAXLEN_BZ2)
    rd = cm.BitReader(NOCODE_STREAM, 0, msb_first=True)
    for exp in (0, 1):                                  # s0 ('00'), s1 ('01')
        sym, l = t.decode(rd.peek(cm.MAXLEN_BZ2))
        assert sym == exp, f"stimulus self-check: got sym {sym}, expected {exp}"
        rd.consume(l)
    try:
        t.decode(rd.peek(cm.MAXLEN_BZ2))
    except ValueError as e:
        assert "ERR_NOCODE" in str(e), e
        return
    raise AssertionError("stimulus self-check: golden Table did not raise ERR_NOCODE")


class HuffErrBaseTest(HuffBaseTest):
    """Per-invocation plumbing: flush parked frames, queue fresh ones, run the seq."""

    async def inv(self, seq, bits=None, sels=None):
        self.env.flush_sources()                 # MAS DMA rule: flushed before doorbell
        if bits is not None:
            await self.queue_streams(bits, sels)
        await seq.start(self.env.agent.sequencer)
        self.logger.info(
            f"[{seq.get_name()}] STATUS=0x{seq.status:x} SYMBOLS={seq.symbols} "
            f"BITS={seq.bits}")
        return seq

    async def good(self, tag):
        """Reject-fix-accept back half: a full known-good decode; the scoreboard
        checks its beats/SYMBOLS against golden."""
        seq = ErrInvSeq(f"good_{tag}", alphabet=4, n_tables=1, lengths=GOOD_LENGTHS,
                        outcome=ST_DONE)
        await self.inv(seq, GOOD_STREAM, GOOD_SELS)
        assert seq.symbols == GOOD_SYMBOLS and seq.bits == GOOD_BITS, (
            f"good_{tag}: SYMBOLS={seq.symbols} BITS={seq.bits} != "
            f"({GOOD_SYMBOLS},{GOOD_BITS})")
        return seq


class HuffErrRejectTest(HuffErrBaseTest):
    """F-09: each ERR_PARAM clause rejected at the doorbell (no BUSY, config holds),
    each followed by a good invocation; then F-26 doorbell ERR_TABLE (length 21)."""

    async def main(self):
        cases = [
            # (tag, ErrInvSeq kwargs) — readback proves the config regs still hold
            # the rejected values (MAS: rejection is sticky-flag only).
            ("limit_zero", dict(symbol_limit=0,
                                readback=[(SYMBOL_LIMIT, 0)])),
            ("limit_over", dict(symbol_limit=(1 << 27) + 1,
                                readback=[(SYMBOL_LIMIT, (1 << 27) + 1)])),
            ("alphabet_2", dict(alphabet=2, readback=[(ALPHABET, 2)])),
            ("alphabet_289", dict(alphabet=289, readback=[(ALPHABET, 289)])),
            ("ntables_0", dict(n_tables=0, readback=[(N_TABLES, 0)])),
            ("ntables_7", dict(n_tables=7, readback=[(N_TABLES, 7)])),
            # DEFLATE combination clause: MODE=1 with N_TABLES!=2 (ALPHABET kept in
            # the DEFLATE-legal 257..288 so N_TABLES is the offending field).
            # Rejection only — no DEFLATE decode is attempted (F-25 gated).
            ("deflate_ntables_1", dict(mode=1, alphabet=257, n_tables=1,
                                       readback=[(MODE, 1), (N_TABLES, 1)])),
        ]
        for tag, kw in cases:
            seq = ErrInvSeq(f"param_{tag}", lengths=None, outcome=ST_EPARAM,
                            reject=True, read_counters=False, **kw)
            await self.inv(seq)                  # no streams: doorbell must bounce
            await self.good(tag)                 # reject-fix-accept

        # F-26 doorbell-time ERR_TABLE: raw LEN word with a 21 in a used field.
        seq = ErrInvSeq("badlen_21", lengths=GOOD_LENGTHS,
                        raw_writes=[(LEN_BASE, BADLEN_WORD)], outcome=ST_ETABLE,
                        reject=True, read_counters=False,
                        readback=[(LEN_BASE, BADLEN_WORD)])
        await self.inv(seq)
        # DEFLATE 16..20 badlen bin: SKIPPED — DEFLATE mode gated (F-25/R23); the
        # 16..20 range is only illegal with MODE=1, which cannot be exercised yet.
        await self.good("badlen_fix")            # good() rewrites LEN word 0


@cocotb.test()
async def errors_reject(_dut):
    await uvm_root().run_test("HuffErrRejectTest")


class HuffErrRuntimeTest(HuffErrBaseTest):
    """F-26 Kraft + F-10 run-time errors; SYMBOLS checked here AND by the scoreboard
    against the golden prefix; BITS-on-error observations logged (not auto-checked)."""

    async def main(self):
        bits_on_error = []

        # 3. build-time ERR_TABLE: over-subscribed table; accepted at the doorbell,
        # errors in the build, no beats (s_sel never consumed -> no selector queued).
        seq = ErrInvSeq("kraft_oversub", lengths=KRAFT_LENGTHS, outcome=ST_ETABLE)
        await self.inv(seq, bytes(4), None)
        assert seq.symbols == 0, f"kraft: SYMBOLS={seq.symbols} != 0 (no beats)"
        bits_on_error.append(("kraft_oversub", seq.bits))

        # 4. ERR_NOCODE: incomplete-legal table, stream hits unassigned '111...'.
        _confirm_nocode_golden()
        seq = ErrInvSeq("nocode_mid", lengths=NOCODE_LENGTHS, outcome=ST_ENOCODE)
        await self.inv(seq, NOCODE_STREAM, bytes([0]))
        assert seq.symbols == 2, f"nocode: SYMBOLS={seq.symbols} != 2"
        bits_on_error.append(("nocode_mid", seq.bits))

        # 5a. ERR_SELECTOR range at symbol 0: selector 5 with N_TABLES=2.
        seq = ErrInvSeq("sel_range_sym0", n_tables=2, lengths=GOOD_LENGTHS * 2,
                        outcome=ST_ESEL)
        await self.inv(seq, GOOD_STREAM, bytes([5]))
        assert seq.symbols == 0, f"sel_range_sym0: SYMBOLS={seq.symbols} != 0"
        bits_on_error.append(("sel_range_sym0", seq.bits))

        # 5b. ERR_SELECTOR range at the 50-boundary: selector 7 applied for group 2
        # after 50 good symbols. The bad selector is delivered LATE (stalled-refill,
        # the F-21 "DMA stalled" boundary flavor): with [0,7] queued up-front the
        # skid-resident 7 makes err_sel fire in the SAME cycle as the boundary
        # advance (huff_selector.sv line 55/64), withdrawing the boundary-coincident
        # 50th beat — DUT then reports SYMBOLS=49/BITS=50 while the golden predictor
        # expects 50 beats (documented finding; see module docstring of the report).
        self.env.flush_sources()
        await self.queue_streams(FIFTY_STREAM, bytes([0]))

        async def late_bad_selector():
            await Timer(30, "us")            # group 1 long decoded; refill stalled
            await self.env.sel_source.send(AxiStreamFrame(bytes([7])))

        cocotb.start_soon(late_bad_selector())
        seq = ErrInvSeq("sel_range_50", n_tables=2, lengths=GOOD_LENGTHS * 2,
                        outcome=ST_ESEL)
        await seq.start(self.env.agent.sequencer)
        self.logger.info(f"[sel_range_50] STATUS=0x{seq.status:x} "
                         f"SYMBOLS={seq.symbols} BITS={seq.bits}")
        assert seq.symbols == 50, f"sel_range_50: SYMBOLS={seq.symbols} != 50"
        bits_on_error.append(("sel_range_50", seq.bits))

        # 6. ERR_SELECTOR exhausted: one selector, 51st symbol needs a refill.
        seq = ErrInvSeq("sel_exhausted", lengths=GOOD_LENGTHS, outcome=ST_ESEL)
        await self.inv(seq, FIFTY_STREAM, bytes([0]))
        assert seq.symbols == 50, f"sel_exhausted: SYMBOLS={seq.symbols} != 50"
        bits_on_error.append(("sel_exhausted", seq.bits))

        # 7a. ERR_UNDERRUN mid-code: TLAST with the last codeword truncated ('11').
        seq = ErrInvSeq("under_midcode", lengths=GOOD_LENGTHS, outcome=ST_EUNDER)
        await self.inv(seq, UNDER_STREAM, bytes([0]))
        assert seq.symbols == 3, f"under_midcode: SYMBOLS={seq.symbols} != 3"
        bits_on_error.append(("under_midcode", seq.bits))

        # 7b. ERR_UNDERRUN at PREP: START_BIT >= total stream bits (16 >= 16).
        seq = ErrInvSeq("under_prep", lengths=GOOD_LENGTHS, start_bit=16,
                        outcome=ST_EUNDER)
        await self.inv(seq, bytes([0xAA, 0x55]), bytes([0]))
        assert seq.symbols == 0, f"under_prep: SYMBOLS={seq.symbols} != 0"
        bits_on_error.append(("under_prep", seq.bits))

        # 8a. ERR_LIMIT: SYMBOL_LIMIT=3, 5-symbol stream -> exactly 3 beats.
        seq = ErrInvSeq("limit_3of5", lengths=GOOD_LENGTHS, symbol_limit=3,
                        outcome=ST_ELIMIT)
        await self.inv(seq, LIMIT_STREAM, bytes([0]))
        assert seq.symbols == 3, f"limit_3of5: SYMBOLS={seq.symbols} != 3"
        bits_on_error.append(("limit_3of5", seq.bits))

        # 8b. tie rule: SYMBOL_LIMIT=5 and beat 5 IS the EOB -> DONE, not ERR_LIMIT.
        seq = ErrInvSeq("limit_tie_eob", lengths=GOOD_LENGTHS, symbol_limit=5,
                        outcome=ST_DONE)
        await self.inv(seq, LIMIT_STREAM, bytes([0]))
        assert seq.symbols == 5 and seq.bits == 7, (
            f"limit_tie_eob: SYMBOLS={seq.symbols} BITS={seq.bits} != (5,7)")

        for tag, b in bits_on_error:
            self.logger.info(f"BITS-on-error observation: {tag}: BITS={b}")


@cocotb.test()
async def errors_runtime(_dut):
    await uvm_root().run_test("HuffErrRuntimeTest")
