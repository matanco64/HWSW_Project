"""cocotb entry for the huffman_engine pyuvm testbench (testplan.md §3).

PYTHONPATH (from Makefile.cocotb) provides hw/common/tb, tb/, tb/sequences and golden/.
The golden module is bound via ConfigDB key "golden" — the scoreboard calls
canonical_model.decode_bzip2_symbols, never a re-implementation."""
import canonical_model
import cocotb
from cocotbext.axi import AxiStreamFrame
from pyuvm import ConfigDB, uvm_root

from base_test import BaseTest
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
