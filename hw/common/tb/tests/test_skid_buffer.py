"""Smoke test for skid_buffer and the shared pyuvm library.

Pushes N random words through the skid buffer from a source StreamAgent, with a
sink StreamAgent applying random backpressure, and checks order + values with the
identity golden model in Scoreboard.
"""
import os

import cocotb
from cocotb.triggers import ClockCycles
from pyuvm import ConfigDB, uvm_root

from base_env import BaseEnv
from base_test import BaseTest
from scoreboard import Scoreboard
from stream_agent import StreamAgent, StreamIf, StreamRandomSeq

N_WORDS = int(os.getenv("N_WORDS", "200"))


class SkidEnv(BaseEnv):
    def build_phase(self):
        dut = ConfigDB().get(self, "", "dut")
        ConfigDB().set(self, "src*", "stream_if", StreamIf(dut.clk, dut.in_valid, dut.in_ready, dut.in_data))
        ConfigDB().set(self, "src", "mode", "source")
        ConfigDB().set(self, "snk*", "stream_if", StreamIf(dut.clk, dut.out_valid, dut.out_ready, dut.out_data))
        ConfigDB().set(self, "snk", "mode", "sink")
        ConfigDB().set(self, "snk*", "ready_prob", 0.6)
        self.src = StreamAgent.create("src", self)
        self.snk = StreamAgent.create("snk", self)
        self.scoreboard = Scoreboard.create("scoreboard", self)

    def connect_phase(self):
        self.src.ap.connect(self.scoreboard.in_export)
        self.snk.ap.connect(self.scoreboard.out_export)


class SkidTest(BaseTest):
    env_class = SkidEnv

    async def main(self):
        seq = StreamRandomSeq("seq")
        seq.n = N_WORDS
        seq.width = int(self.dut.WIDTH.value) if hasattr(self.dut, "WIDTH") else 32
        await seq.start(self.env.src.sequencer)
        # wait for the sink to drain everything (bounded)
        for _ in range(N_WORDS * 4):
            if self.env.scoreboard.n_actual() >= N_WORDS:
                break
            await ClockCycles(self.clk, 4)
        assert self.env.scoreboard.n_actual() == N_WORDS, "sink did not receive all words"


@cocotb.test()
async def skid_buffer_random(dut):
    await uvm_root().run_test("SkidTest")
