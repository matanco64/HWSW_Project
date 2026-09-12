"""cocotb entry for the mtf_cam pyuvm testbench (testplan §5, stage 6 hw-dv-bringup).

PYTHONPATH (Makefile.cocotb) provides hw/common/tb, tb/, tb/sequences and golden/. The golden
lives under golden/: `list_model` is the per-beat PREDICTOR the scoreboard checks the DUT against
(bound via ConfigDB "predictor"); `mtf_ref` is the ==libbzip2 GOLDEN the predictor is cross-checked
against per block. The scoreboard never re-implements the MTF/run math."""
import itertools
import struct

import cocotb
import list_model
import mtf_ref
from cocotbext.axi import AxiStreamFrame
from pyuvm import ConfigDB, uvm_root

from base_test import BaseTest
from env import MtfEnv, make_beat
from smoke import BenchSeq, MtfBaseSeq, SmokeSeq

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


@cocotb.test()
async def full_benchmark(_dut):
    await uvm_root().run_test("MtfFullBenchTest")
