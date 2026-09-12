"""cocotb entry for the mtf_cam pyuvm testbench (testplan §5, stage 6 hw-dv-bringup).

PYTHONPATH (Makefile.cocotb) provides hw/common/tb, tb/, tb/sequences and golden/. The golden
lives under golden/: `list_model` is the per-beat PREDICTOR the scoreboard checks the DUT against
(bound via ConfigDB "predictor"); `mtf_ref` is the ==libbzip2 GOLDEN the predictor is cross-checked
against per block. The scoreboard never re-implements the MTF/run math."""
import itertools
import random
import struct

import cocotb
import list_model
import mtf_ref
from cocotb.triggers import ClockCycles, RisingEdge
from cocotbext.axi import AxiStreamFrame
from pyuvm import ConfigDB, uvm_root

from base_test import BaseTest
from env import (MtfEnv, make_beat, cov, ST_ERANK, ST_ERUN, ST_ELIMIT, ST_EUNDER)
from smoke import BenchSeq, MtfBaseSeq, SmokeSeq
import random_streams
from random_streams import RandStreamSeq, make_random_stream, pause_gen, n_to_runs
from corner import (ParamRejectSeq, RunSeq, BusyDoorbellSeq, AxiProbeSeq,
                    AbortSeq, RegSweepSeq, BusyConfigSeq)

W = 8                                   # build default (CAPS 0x0100_0808)


def symbols_to_bytes(symbols, alphabet):
    """Pack raw symbol values into the 32-bit s_sym byte stream (one beat per symbol; the last,
    the EOB, is TYPE 3 and carries TLAST as the last beat of the frame)."""
    eob = alphabet - 1
    buf = bytearray()
    for s in symbols:
        buf += struct.pack("<I", make_beat(s, s == eob))
    return bytes(buf)


class MtfBaseTest(BaseTest):
    env_class = MtfEnv
    clk_period_ns = 20                  # MAS §3: 50 MHz target

    def build_phase(self):
        ConfigDB().set(None, "*", "predictor", list_model)
        ConfigDB().set(None, "*", "W", W)
        super().build_phase()

    async def queue_symbols(self, symbols, alphabet):
        """Queue the symbol frame on s_sym; it waits on tready = 0 until the doorbell's INIT."""
        await self.env.sym_source.send(AxiStreamFrame(symbols_to_bytes(symbols, alphabet)))

    async def queue_beats(self, beats):
        """Queue a raw (value, type) beat frame (TLAST auto on the last beat). For error streams
        that need a specific TYPE / a non-EOB TLAST beat the value-based helper cannot express."""
        buf = bytearray()
        for value, typ in beats:
            buf += struct.pack("<I", (typ << 9) | (value & 0x1FF))
        await self.env.sym_source.send(AxiStreamFrame(bytes(buf)))

    def sink_ready(self):
        """Make the m_l sink always ready. clear_pause_generator() alone leaves cocotbext's
        `.pause` latched at the generator's last value (True after a heavy-backpressure run),
        which would keep m_ready stuck low and deadlock the pipe — clear the latch too."""
        self.env.l_sink.clear_pause_generator()
        self.env.l_sink.pause = False

    async def pulse_reset(self, cycles=4):
        """Synchronous reset pulse mid-test: clears the DUT, the cocotbext source/sink queues
        (verified in dv) and — via the AXI monitor's reset event — the scoreboard's replay
        state, so the next invocation starts from a clean, leftover-free source (F-16)."""
        self.rst_n.value = 0
        await ClockCycles(self.clk, cycles)
        self.rst_n.value = 1
        await RisingEdge(self.clk)
        await ClockCycles(self.clk, 2)


# ---------------------------------------------------------------------------------------------
# test_smoke — 4 used bytes, a run + MTF symbols + EOB. Expected L-vector 65,65,65,66,67,66.
# ---------------------------------------------------------------------------------------------
SMOKE_USED = [65, 66, 67, 68]           # N_USED = 4, alphabet 6, EOB value 5
SMOKE_SYMS = [0, 0, 2, 3, 2, 5]         # RUNA,RUNA -> run 3 ; MTF r1,r2,r1 ; EOB


class MtfSmokeTest(MtfBaseTest):
    async def main(self):
        await self.queue_symbols(SMOKE_SYMS, alphabet=len(SMOKE_USED) + 2)
        await SmokeSeq("smoke").start(self.env.agent.sequencer)


@cocotb.test()
async def smoke(_dut):
    await uvm_root().run_test("MtfSmokeTest")


class MtfSmokeBpTest(MtfBaseTest):
    """test_smoke under a deterministic toggling m_l sink (backpressure): exercises the packer
    skid/hold under !tready that an always-ready sink never hits."""

    async def main(self):
        self.env.l_sink.set_pause_generator(itertools.cycle([True, False]))
        await self.queue_symbols(SMOKE_SYMS, alphabet=len(SMOKE_USED) + 2)
        await SmokeSeq("smoke_bp").start(self.env.agent.sequencer)


@cocotb.test()
async def smoke_backpressure(_dut):
    await uvm_root().run_test("MtfSmokeBpTest")


# ---------------------------------------------------------------------------------------------
# test_backpressure — a long multi-beat run drained under toggling tready (packer/expander stress)
# ---------------------------------------------------------------------------------------------
class MtfBackpressureTest(MtfBaseTest):
    """used {65,66}: 6x RUNB -> run of 126 bytes (15 full beats + 6), then MTF r1, then EOB,
    under a toggling m_l sink. Stresses the expander's multi-beat drain and the packer skid."""

    async def main(self):
        used = [65, 66]
        alphabet = len(used) + 2         # EOB value 3
        syms = [1, 1, 1, 1, 1, 1, 2, 3]  # RUNB x6 (n=126) ; MTF r1 (66) ; EOB
        self.env.l_sink.set_pause_generator(itertools.cycle([True, True, False]))
        await self.queue_symbols(syms, alphabet)

        class _Seq(MtfBaseSeq):
            async def body(s):
                await s.program_used(used)
                await s.run_to_done(max_polls=5000)
                mr = await s.rd(0x054)
                self.logger.info(f"backpressure: MAX_RUN={mr} (expect 126)")
                await s.wr(0x00C, 2)     # W1C DONE
        await _Seq("bp").start(self.env.agent.sequencer)


@cocotb.test()
async def backpressure(_dut):
    await uvm_root().run_test("MtfBackpressureTest")


# ---------------------------------------------------------------------------------------------
# test_multiblock — two blocks back-to-back; MAX_RUN must reset per invocation (R1 / F-22)
# ---------------------------------------------------------------------------------------------
class MtfMultiblockTest(MtfBaseTest):
    async def main(self):
        # Block 1: big run (5x RUNB -> n=62) then MTF then EOB. Block 2: small run (2x RUNA ->
        # n=3) then MTF then EOB. Block 2's MAX_RUN must read 3, not the stale 62 (R1).
        b1_used, b2_used = [65, 66, 67], [65, 66, 67]
        alpha = len(b1_used) + 2         # EOB value 4
        b1 = [1, 1, 1, 1, 1, 2, 4]       # RUNB x5 (n=62) ; MTF r1 ; EOB
        b2 = [0, 0, 3, 4]                # RUNA x2 (n=3) ; MTF r2 ; EOB
        await self.queue_symbols(b1, alpha)

        class _Blk(MtfBaseSeq):
            def __init__(s, name, used):
                super().__init__(name)
                s.used = used
                s.max_run = None

            async def body(s):
                await s.program_used(s.used)
                await s.run_to_done(max_polls=5000)
                s.max_run = await s.rd(0x054)
                await s.wr(0x00C, 2)     # W1C DONE

        seq1 = _Blk("blk1", b1_used)
        await seq1.start(self.env.agent.sequencer)
        # queue block 2 only after block 1 completed (empty s_sym at every doorbell, MAS §5)
        await self.queue_symbols(b2, alpha)
        seq2 = _Blk("blk2", b2_used)
        await seq2.start(self.env.agent.sequencer)
        self.logger.info(f"multiblock MAX_RUN: block1={seq1.max_run} (62) "
                         f"block2={seq2.max_run} (3)")
        assert seq1.max_run == 62, f"block1 MAX_RUN {seq1.max_run} != 62"
        assert seq2.max_run == 3, f"block2 MAX_RUN {seq2.max_run} != 3 (R1 per-invocation reset)"
        cov("cg_maxrun", "big_then_small")                  # F-22 block1 max > block2 max


@cocotb.test()
async def multiblock(_dut):
    await uvm_root().run_test("MtfMultiblockTest")


# ---------------------------------------------------------------------------------------------
# test_k1 — a run-free MTF stream (K1 measurement, R2). CYCLES ~ INIT_CYCLES + N + latency.
# ---------------------------------------------------------------------------------------------
class MtfK1Test(MtfBaseTest):
    async def main(self):
        n_used = 255                     # used bytes 0..254 ; alphabet 257 ; EOB value 256
        used = list(range(n_used))
        alphabet = n_used + 2
        n = 4096
        syms = [2 + (i % (n_used - 1)) for i in range(n)]   # MTF values 2..255 (ranks 1..254)
        syms.append(alphabet - 1)        # EOB
        await self.queue_symbols(syms, alphabet)

        class _Seq(MtfBaseSeq):
            async def body(s):
                for w in range(8):
                    word = 0
                    for b in range(32):
                        if 32 * w + b < n_used:
                            word |= 1 << b
                    await s.wr(0x200 + 4 * w, word)
                await s.wr(0x100, 1 << 20)     # SYMBOL_LIMIT
                await s.wr(0x104, 1 << 20)     # BYTES_LIMIT
                await s.run_to_done(max_polls=20000)
                s.cyc = await s.rd(0x040)
                s.sym = await s.rd(0x048)
                s.ini = await s.rd(0x050)
                await s.wr(0x00C, 2)
        seq = _Seq("k1")
        await seq.start(self.env.agent.sequencer)
        k1 = seq.cyc / seq.sym
        self.logger.info(f"K1 (run-free {n} MTF): CYCLES={seq.cyc} SYMBOLS_IN={seq.sym} "
                         f"INIT_CYCLES={seq.ini} K1={k1:.4f} (target <= 1.10)")
        assert seq.sym == n + 1, f"SYMBOLS_IN {seq.sym} != {n + 1}"
        assert k1 <= 1.10, f"K1 {k1:.4f} > 1.10"
        cov("cg_k1", "runfree_4096")
        cov("cg_k1", "rank_spread")


@cocotb.test()
async def k1(_dut):
    await uvm_root().run_test("MtfK1Test")


# ---------------------------------------------------------------------------------------------
# test_full_benchmark — the whole benchmark block (148,271 symbols); L-vector exact vs golden,
# K3 measured and reconciled against the model 1.063 (R2 / F-21).
# ---------------------------------------------------------------------------------------------
class MtfFullBenchTest(MtfBaseTest):
    async def main(self):
        mt = mtf_ref.trace_benchmark()
        used = mt.used
        alphabet = mt.alphabet
        symbols = mt.symbols
        # predictor vs golden, once (testplan §2.2, == calibrate.py)
        l_bytes, events = list_model.expand(symbols, used, alphabet)
        assert l_bytes == mt.l_vector, "predictor L-vector != golden mtf_ref.l_vector"
        model_cycles = list_model.cycles(symbols, used, alphabet, W=W, D=8)
        self.logger.info(f"benchmark: symbols={len(symbols)} L-vector={len(l_bytes)} B "
                         f"beats={-(-len(l_bytes) // W)} model_cycles={model_cycles} "
                         f"model_K3={model_cycles / len(symbols):.4f}")

        used_bytes = [b for b in range(256) if used[b]]
        await self.queue_symbols(symbols, alphabet)
        seq = BenchSeq("bench", used_bytes=used_bytes)
        await seq.start(self.env.agent.sequencer)
        c = seq.counters
        cycles = c["cycles_lo"] | (c["cycles_hi"] << 32)
        k3 = cycles / c["symbols_in"]
        self.logger.info(
            f"benchmark DUT: CYCLES={cycles} SYMBOLS_IN={c['symbols_in']} "
            f"BYTES_OUT={c['bytes_out']} INIT_CYCLES={c['init_cycles']} MAX_RUN={c['max_run']} "
            f"DUT_K3={k3:.4f} (model 1.063) delta={k3 - model_cycles / len(symbols):+.4f}")
        assert c["symbols_in"] == len(symbols), f"SYMBOLS_IN {c['symbols_in']} != {len(symbols)}"
        assert c["bytes_out"] == len(l_bytes), f"BYTES_OUT {c['bytes_out']} != {len(l_bytes)}"
        assert c["max_run"] == max(e[1] for e in events if e[0] == "run"), "MAX_RUN mismatch"
        assert k3 <= 1.10, f"K3 {k3:.4f} > 1.10 (R2/F-21)"
        cov("cg_k2", "run_8157")                            # benchmark MAX_RUN == 8157
        cov("cg_k2", "w_8")
        cov("cg_k3", "w_8")
        cov("cg_k3", "le_1p10")
        cov("cg_pack", "exact_multiple")                    # 336,184 % 8 == 0 (S3)


@cocotb.test()
async def full_benchmark(_dut):
    await uvm_root().run_test("MtfFullBenchTest")


# =============================================================================================
# Stage 7 (dv_coverage): constrained-random + directed corner/error tests.
# =============================================================================================
import os

RAND_SEED = int(os.environ.get("MTF_RAND_SEED", "48815"))    # logged per run (SEED=)


# ---------------------------------------------------------------------------------------------
# test_random — constrained-random used-maps / rank+run+EOB streams under randomized m_l tready
# duty (0/50/90 %). Every run must pass the golden scoreboard (0 mismatches). SEED logged.
# ---------------------------------------------------------------------------------------------
class MtfRandomTest(MtfBaseTest):
    N_INVOCATIONS = 14

    async def main(self):
        self.logger.info(f"test_random: SEED={RAND_SEED} invocations={self.N_INVOCATIONS}")
        rng = random.Random(RAND_SEED)                       # stream generation (deterministic)
        prng = random.Random(RAND_SEED ^ 0x5A5A5A)           # sink pause timing (kept separate so
        duties = ["none", "half", "heavy"]                   # streams are reproducible from SEED)
        for i in range(self.N_INVOCATIONS):
            duty = duties[i % 3]
            if i:
                await self.pulse_reset()                     # isolate each invocation cleanly
            self.sink_ready()
            gen, bin_name = pause_gen(duty, prng)
            if gen is not None:
                self.env.l_sink.set_pause_generator(gen)
            cov("cg_pack", bin_name)
            used_bytes, symbols, alphabet = make_random_stream(rng)
            self.logger.info(f"  inv {i}: SEED={RAND_SEED} duty={duty} n_used={len(used_bytes)} "
                             f"symbols={len(symbols)}")
            await self.queue_symbols(symbols, alphabet)
            seq = RandStreamSeq(f"rand{i}", used_bytes=used_bytes)
            await seq.start(self.env.agent.sequencer)


@cocotb.test()
async def test_random(_dut):
    await uvm_root().run_test("MtfRandomTest")


# ---------------------------------------------------------------------------------------------
# test_corner — ERR_PARAM clauses, empty block, ERR_BUSY, AXI SLVERR/RAZ/WI, N_USED=1/256,
# counter-read-while-BUSY. None of these leave un-accepted s_sym beats, so they run back-to-back.
# ---------------------------------------------------------------------------------------------
class MtfCornerTest(MtfBaseTest):
    async def main(self):
        sq = self.env.agent.sequencer
        # F-09 ERR_PARAM (each clause): doorbell rejected, no BUSY, sticky ERR_PARAM
        await ParamRejectSeq("p_nused0", used_bytes=[]).start(sq)                 # N_USED=0
        await ParamRejectSeq("p_symlim0", used_bytes=[65], symbol_limit=0).start(sq)
        await ParamRejectSeq("p_symhi", used_bytes=[65], symbol_limit=(1 << 27) + 1).start(sq)
        await ParamRejectSeq("p_bytlim0", used_bytes=[65], bytes_limit=0).start(sq)
        await ParamRejectSeq("p_bythi", used_bytes=[65], bytes_limit=(1 << 30) + 1).start(sq)

        # F-13 empty block: EOB as the first symbol -> DONE, no m_l beat, BYTES_OUT = 0
        await self.queue_symbols([2], alphabet=3)            # used {65}: EOB value = 2
        await RunSeq("empty", used_bytes=[65], expect_done=True).start(sq)

        # F-14 AXI: SLVERR (unmapped), RAZ/WI (reserved)
        await AxiProbeSeq("axi").start(sq)

        # cg_init N_USED = 1 (run + EOB) and N_USED = 256 (all bytes used)
        await self.queue_symbols([0, 2], alphabet=3)         # used {65}: RUNA(1B) + EOB
        await RunSeq("nused1", used_bytes=[65], expect_done=True).start(sq)
        await self.queue_symbols([2, 257], alphabet=258)     # used all 256: MTF r1 + EOB(257)
        await RunSeq("nused256", used_bytes=list(range(256)), expect_done=True,
                     max_polls=4000).start(sq)

        # cg_counters read while BUSY + F-11 ERR_BUSY (needs a longer run so BUSY is observable)
        run = n_to_runs(4000)
        await self.queue_symbols(run + [3], alphabet=4)      # used {65,66}: run(4000B) + EOB(3)
        await RunSeq("cbusy", used_bytes=[65, 66], expect_done=True, read_busy=True,
                     max_polls=8000).start(sq)
        await self.queue_symbols(run + [3], alphabet=4)
        await BusyDoorbellSeq("busy", used_bytes=[65, 66]).start(sq)


@cocotb.test()
async def test_corner(_dut):
    await uvm_root().run_test("MtfCornerTest")


# ---------------------------------------------------------------------------------------------
# Runtime-error directed tests (F-10). Each is its own cocotb test so the (deliberately
# non-EOB-terminated) error frame leaves no un-accepted beat for a later invocation; the
# scoreboard is the oracle for the truncated/flush output, each asserts its own sticky bit.
# ---------------------------------------------------------------------------------------------
class MtfErrUnderrunTest(MtfBaseTest):
    async def main(self):
        sq = self.env.agent.sequencer
        # used {65,66,67}: two MTF symbols, TLAST on the 2nd (non-EOB) -> ERR_UNDERRUN (pos_mid)
        await self.queue_symbols([2, 3], alphabet=5)
        await RunSeq("underrun", used_bytes=[65, 66, 67], err_bit=ST_EUNDER).start(sq)
        await self.pulse_reset()
        # single-beat non-EOB frame: TLAST on the very first beat -> ERR_UNDERRUN at beat 0
        # (cg_errrt.pos_first)
        await self.queue_symbols([2], alphabet=5)
        await RunSeq("underrun_first", used_bytes=[65, 66, 67], err_bit=ST_EUNDER).start(sq)


@cocotb.test()
async def test_err_underrun(_dut):
    await uvm_root().run_test("MtfErrUnderrunTest")


class MtfErrRankTest(MtfBaseTest):
    async def main(self):
        # used {65,66,67} (N_USED=3, EOB=4): 2 MTF, RUNA,RUNA (run pending), then value 6 > N_USED
        # (TYPE0, non-last) -> ERR_RANK with a run pending (F-23 discard); trailing dummy leaks
        # harmlessly (test ends).
        await self.queue_beats([(2, 0), (3, 0), (0, 0), (0, 0), (6, 0), (0, 0)])
        await RunSeq("rank_gt", used_bytes=[65, 66, 67], err_bit=ST_ERANK).start(
            self.env.agent.sequencer)


@cocotb.test()
async def test_err_rank(_dut):
    await uvm_root().run_test("MtfErrRankTest")


class MtfErrEobTest(MtfBaseTest):
    """The three bad-EOB / bad-type ERR_RANK variants (cg_block eob_*), reset between so each
    non-EOB-terminated frame is cleared from the source."""

    async def main(self):
        sq = self.env.agent.sequencer
        # (a) TYPE3 with the wrong value (last beat, TLAST): is_type3 so not underrun -> ERR_RANK
        await self.queue_beats([(2, 0), (5, 3)])             # used {65,66}: EOB should be value 3
        await RunSeq("eob_type3_badval", used_bytes=[65, 66], err_bit=ST_ERANK).start(sq)
        await self.pulse_reset()
        # (b) TYPE0 carrying the EOB value 3 (non-last) -> ERR_RANK (eob_type0_eobval)
        await self.queue_beats([(2, 0), (3, 0), (0, 0)])
        await RunSeq("eob_type0_eobval", used_bytes=[65, 66], err_bit=ST_ERANK).start(sq)
        await self.pulse_reset()
        # (c) TYPE1 beat (non-last) -> ERR_RANK (eob_type12)
        await self.queue_beats([(2, 0), (0, 1), (0, 0)])
        await RunSeq("eob_type12", used_bytes=[65, 66], err_bit=ST_ERANK).start(sq)


@cocotb.test()
async def test_err_eob(_dut):
    await uvm_root().run_test("MtfErrEobTest")


class MtfErrLimitTest(MtfBaseTest):
    async def main(self):
        sq = self.env.agent.sequencer
        # (a) ERR_LIMIT symbol budget: SYMBOL_LIMIT=3, the 3rd accepted beat is a non-EOB MTF
        # (used {65,66,67} so values 2,3 are valid MTF ranks, not ERR_RANK)
        await self.queue_beats([(2, 0), (3, 0), (2, 0), (0, 0)])
        await RunSeq("limit_sym", used_bytes=[65, 66, 67], symbol_limit=3,
                     err_bit=ST_ELIMIT).start(sq)
        await self.pulse_reset()
        # (b) ERR_LIMIT byte budget: a run of 10 bytes against BYTES_LIMIT=5 -> item over budget
        run10 = n_to_runs(10)
        await self.queue_symbols(run10 + [2], alphabet=3)    # used {65}: run(10B) + EOB(2)
        await RunSeq("limit_byte", used_bytes=[65], bytes_limit=5,
                     err_bit=ST_ELIMIT).start(sq)


@cocotb.test()
async def test_err_limit(_dut):
    await uvm_root().run_test("MtfErrLimitTest")


class MtfRunMaxTest(MtfBaseTest):
    """F-03: n = 2^20 accepted (drains 131,072 beats), then reset, n = 2^20+1 rejected (ERR_RUN)."""

    async def main(self):
        sq = self.env.agent.sequencer
        big = n_to_runs(1 << 20)                             # 20 run symbols summing to exactly 2^20
        await self.queue_symbols(big + [2], alphabet=3)      # used {65}: run(2^20 B) + EOB(2)
        await RunSeq("runmax", used_bytes=[65], expect_done=True, max_polls=400000).start(sq)
        await self.pulse_reset()
        over = n_to_runs((1 << 20) + 1)                      # overflows at the last run symbol
        await self.queue_beats([(s, 0) for s in over] + [(0, 0)])
        await RunSeq("runover", used_bytes=[65], err_bit=ST_ERUN, max_polls=4000).start(sq)
        cov("cg_run", "n_2p20p1")                            # attempted run = 2^20+1 (ERR_RUN)


@cocotb.test()
async def test_run_max(_dut):
    await uvm_root().run_test("MtfRunMaxTest")


class _ProgRingSeq(MtfBaseSeq):
    """Program the used map + limits and ring the doorbell (no polling — the test resets the DUT
    mid-state right after)."""

    def __init__(self, name, used_bytes):
        super().__init__(name)
        self.used_bytes = used_bytes

    async def body(self):
        from env import CTRL
        await self.program_used(self.used_bytes)
        await self.wr(CTRL, 1)


class _ReadbackSeq(MtfBaseSeq):
    """Read a set of registers back; store the values in `self.vals`."""

    def __init__(self, name, addrs):
        super().__init__(name)
        self.addrs = addrs
        self.vals = {}

    async def body(self):
        for a in self.addrs:
            self.vals[a] = await self.rd(a)


class MtfResetStateTest(MtfBaseTest):
    """F-16 reset-in-state: assert reset while the FSM is in INIT / DECODE / DECODE-stalled /
    DRAIN, then read back the reset values (STATUS, counters, used map all 0)."""

    async def main(self):
        from env import STATUS, SYMBOLS_IN, BYTES_OUT, USED_BASE
        sq = self.env.agent.sequencer
        run = n_to_runs(2000)

        async def ring(used_bytes, symbols, alphabet, wait):
            await self.queue_symbols(symbols, alphabet)
            await _ProgRingSeq("prep", used_bytes).start(sq)
            await ClockCycles(self.clk, wait)

        async def readback_zero(tag):
            rb = _ReadbackSeq("rb", [STATUS, SYMBOLS_IN, BYTES_OUT, USED_BASE])
            await rb.start(sq)
            for addr, v in rb.vals.items():
                assert v == 0, f"reset-{tag}: @0x{addr:x} read 0x{v:x} != 0 after reset"

        # INIT: doorbell a 256-used block (256-cycle fill), reset a few cycles in
        await ring(list(range(256)), [2, 257], 258, wait=4)
        await self.pulse_reset()
        await readback_zero("init")
        # DECODE (stalled): many single-item MTF symbols with the sink stalled fill the item FIFO,
        # so s_sym.tready drops and the FSM parks in DECODE — reset there (at_decode + at_stalled)
        self.env.l_sink.set_pause_generator(itertools.cycle([True]))
        await ring([65, 66, 67], [2, 3] * 30, 5, wait=30)
        cov("cg_reset", "at_stalled")
        await self.pulse_reset()
        self.sink_ready()
        await readback_zero("decode")
        # DRAIN: a longer run + EOB with the sink ready enters DRAIN and drains for ~250 cycles;
        # reset mid-drain
        await ring([65, 66], run + [3], 4, wait=18)
        await self.pulse_reset()
        await readback_zero("drain")


@cocotb.test()
async def test_reset(_dut):
    await uvm_root().run_test("MtfResetStateTest")


class MtfXinvTest(MtfBaseTest):
    """F-24 cg_xinv: an ERR_UNDERRUN flush parks a partial m_l beat under a stalled sink; the
    next accepted doorbell's pack_discard must withdraw it (discard_pending_beat)."""

    async def main(self):
        sq = self.env.agent.sequencer
        self.env.l_sink.set_pause_generator(itertools.cycle([True]))   # sink never ready
        # 5 MTF symbols so >= 1 byte reaches the packer buffer before the underrun flush parks a
        # partial beat; last beat TLAST (non-EOB) -> ERR_UNDERRUN
        await self.queue_symbols([2, 3, 2, 3, 2], alphabet=5)
        await RunSeq("park", used_bytes=[65, 66, 67], err_bit=ST_EUNDER,
                     max_polls=4000).start(sq)
        # A partial error-flush beat is now parked in the packer (sink still stalled). Ring a
        # valid doorbell for an EMPTY block (EOB first): its pack_discard withdraws the parked
        # beat (cg_xinv.discard_pending_beat) and an empty block reaches DONE without needing the
        # sink to drain a beat (F-13/F-24). The sink stays stalled through the doorbell.
        await self.queue_symbols([4], alphabet=5)            # used {65,66,67}: EOB value = 4
        await RunSeq("discard", used_bytes=[65, 66, 67], expect_done=True,
                     max_polls=4000).start(sq)
        self.sink_ready()


@cocotb.test()
async def test_xinv(_dut):
    await uvm_root().run_test("MtfXinvTest")


class MtfDriverTest(MtfBaseTest):
    """F-11/F-12/F-04 control-plane driver checks: register/IRQ_EN/DBG sweep, ERR_BUSY on config
    writes while BUSY, and ABORT honoured in INIT / DECODE / DRAIN (reset between the abort cases,
    whose invocations abandon their queued symbols)."""

    async def main(self):
        sq = self.env.agent.sequencer
        await RegSweepSeq("regs").start(sq)
        await self.pulse_reset()

        await self.queue_symbols(n_to_runs(4000) + [3], alphabet=4)   # used {65,66}
        await BusyConfigSeq("busycfg", used_bytes=[65, 66]).start(sq)
        await self.pulse_reset()

        # ABORT in INIT: a 256-used block (256-cycle fill), abort immediately
        await self.queue_symbols([2, 257], alphabet=258)
        await AbortSeq("abort_init", used_bytes=list(range(256)), pre_reads=0).start(sq)
        await self.pulse_reset()
        # ABORT in DECODE: a long run, abort a couple of polls in
        await self.queue_symbols(n_to_runs(6000) + [3], alphabet=4)
        await AbortSeq("abort_decode", used_bytes=[65, 66], pre_reads=2).start(sq)
        await self.pulse_reset()
        # ABORT in DRAIN: a longer run + EOB so the drain is in flight when the abort lands
        await self.queue_symbols(n_to_runs(8000) + [3], alphabet=4)
        await AbortSeq("abort_drain", used_bytes=[65, 66], pre_reads=4).start(sq)


@cocotb.test()
async def test_driver(_dut):
    await uvm_root().run_test("MtfDriverTest")
