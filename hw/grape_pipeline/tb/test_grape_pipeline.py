"""cocotb entry for the grape_pipeline pyuvm testbench (testplan.md §3).

PYTHONPATH (from Makefile.cocotb) provides hw/common/tb, tb/, tb/sequences, tb/tests and
golden/. The golden module is bound via ConfigDB key "golden" — the scoreboard calls
emulation.advance, never a re-implementation.
"""
import copy

import cocotb
import emulation
import nbody_ref
from pyuvm import ConfigDB, uvm_root

from base_test import BaseTest
from env import GrapeEnv
from smoke import CornerSeq, SmokeSeq


class GrapeBaseTest(BaseTest):
    env_class = GrapeEnv
    clk_period_ns = 20                     # MAS §3: 50 MHz target

    def build_phase(self):
        ConfigDB().set(None, "*", "golden", emulation)
        super().build_phase()


class GrapeSmokeTest(GrapeBaseTest):
    async def main(self):
        bodies, _ = nbody_ref.benchmark_system()
        seq = SmokeSeq("smoke", dt=0.01, nsteps=2,
                       bodies=copy.deepcopy(bodies), pairs=[(0, 1), (0, 2)])
        await seq.start(self.env.agent.sequencer)


@cocotb.test()
async def smoke(_dut):
    await uvm_root().run_test("GrapeSmokeTest")


class GrapeCornerTest(GrapeBaseTest):
    async def main(self):
        bodies, _ = nbody_ref.benchmark_system()
        await CornerSeq("corner", bodies=copy.deepcopy(bodies)).start(self.env.agent.sequencer)


@cocotb.test()
async def corner(_dut):
    await uvm_root().run_test("GrapeCornerTest")
