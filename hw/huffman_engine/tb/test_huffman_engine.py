"""cocotb entry for the huffman_engine pyuvm testbench (testplan.md §3).

PYTHONPATH (from Makefile.cocotb) provides hw/common/tb, tb/, tb/sequences and golden/.
The golden module is bound via ConfigDB key "golden" — the scoreboard calls
canonical_model.decode_bzip2_symbols, never a re-implementation."""
import canonical_model
import cocotb
from cocotbext.axi import AxiStreamFrame
from pyuvm import ConfigDB, uvm_root

from base_test import BaseTest
from bench import BenchSeq
from env import HuffEnv
from smoke import SmokeSeq


class HuffBaseTest(BaseTest):
    env_class = HuffEnv
    clk_period_ns = 20                     # MAS §3: 50 MHz target

    k1_enforce = False                     # True for benchmark-shaped configs (F-30)

    def build_phase(self):
        ConfigDB().set(None, "*", "golden", canonical_model)
        ConfigDB().set(None, "*", "k1_enforce", self.k1_enforce)
        super().build_phase()

    async def queue_streams(self, bits: bytes, selectors: bytes | None):
        """Queue stream frames; they wait on tready (0 until the doorbell's PREP)."""
        await self.env.bits_source.send(AxiStreamFrame(bits))
        if selectors is not None:
            await self.env.sel_source.send(AxiStreamFrame(selectors))


class HuffSmokeTest(HuffBaseTest):
    """testplan test_smoke: table [1,2,3,3], stream 0x59 0xC0 (s0 s1 s2 s0 EOB), one
    selector. Golden comparison and counters are the scoreboard's job."""

    async def main(self):
        await self.queue_streams(bytes([0x59, 0xC0]), bytes([0]))
        await SmokeSeq("smoke").start(self.env.agent.sequencer)


@cocotb.test()
async def smoke(_dut):
    await uvm_root().run_test("HuffSmokeTest")


class HuffBenchBlockTest(HuffBaseTest):
    """testplan test_bench_block (F-30): the real benchmark block — 148,271 symbols,
    6 tables, START_BIT 8,844 — trace-exact via the scoreboard, K1 enforced here."""

    k1_enforce = True

    async def main(self):
        import json
        import pathlib
        vecdir = pathlib.Path(__file__).resolve().parent / "vectors"
        vec = json.loads((vecdir / "bench_block.json").read_text())
        stream = (vecdir / "bench_stream.bin").read_bytes()
        await self.queue_streams(stream, bytes(vec["selectors"]))
        seq = BenchSeq("bench", vec=vec)
        await seq.start(self.env.agent.sequencer)
        c = seq.counters
        assert c["symbols"] == vec["n_symbols"], (c, vec["n_symbols"])
        k1 = c["cycles"] / c["symbols"]
        self.logger.info(f"bench block: CYCLES={c['cycles']} SYMBOLS={c['symbols']} "
                         f"BITS={c['bits']} BUILD_CYCLES={c['build_cycles']} "
                         f"OVERFETCH={c['overfetch']} K1={k1:.4f}")
        if self.k1_enforce:
            assert k1 <= 1.1, f"K1 {k1:.4f} > 1.1 (PRD KPI, model 1.0068)"


@cocotb.test()
async def bench_block(_dut):
    await uvm_root().run_test("HuffBenchBlockTest")


class HuffSmokeBpTest(HuffBaseTest):
    """B2: the smoke decode under a deterministic toggling m_sym sink — tready drops on
    alternating cycles, exercising the R1 stall-credit withdrawal (out_occ reaching 2 with
    c1_v set) that an always-ready sink never hits. The armed huff_out push-while-full
    assertion (B1) and the trace-exact scoreboard are the checkers."""

    async def main(self):
        import itertools
        self.env.sym_sink.set_pause_generator(itertools.cycle([True, False]))
        await self.queue_streams(bytes([0x59, 0xC0]), bytes([0]))
        await SmokeSeq("smoke_bp").start(self.env.agent.sequencer)


@cocotb.test()
async def smoke_backpressure(_dut):
    await uvm_root().run_test("HuffSmokeBpTest")
