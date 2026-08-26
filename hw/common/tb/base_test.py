"""BaseTest: uvm_test that starts clock/reset and builds the env named in ConfigDB.

Subclass, set `env_class`, and override `main()` with the stimulus. The DUT is
`cocotb.top`; clock/reset signal names default to `clk`/`rst_n`.
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge
from pyuvm import ConfigDB, uvm_test

from base_env import BaseEnv


class BaseTest(uvm_test):
    env_class = BaseEnv
    clk_period_ns = 10
    reset_cycles = 5
    clk_name = "clk"
    rst_name = "rst_n"

    def build_phase(self):
        self.dut = cocotb.top
        self.clk = getattr(self.dut, self.clk_name)
        self.rst_n = getattr(self.dut, self.rst_name)
        ConfigDB().set(None, "*", "dut", self.dut)
        ConfigDB().set(None, "*", "clk", self.clk)
        ConfigDB().set(None, "*", "rst_n", self.rst_n)
        self.env = self.env_class.create("env", self)

    async def start_clock_and_reset(self):
        cocotb.start_soon(Clock(self.clk, self.clk_period_ns, unit="ns").start())
        self.rst_n.value = 0
        await ClockCycles(self.clk, self.reset_cycles)
        self.rst_n.value = 1
        await RisingEdge(self.clk)

    async def main(self):  # override
        await ClockCycles(self.clk, 10)

    async def run_phase(self):
        self.raise_objection()
        await self.start_clock_and_reset()
        await self.main()
        await ClockCycles(self.clk, 5)
        self.drop_objection()
