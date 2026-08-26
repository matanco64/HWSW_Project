"""Ready/valid stream agent for pyuvm.

Config (ConfigDB, per agent path): "stream_if" -> StreamIf(clk, valid, ready, data),
"mode" -> "source" (drives valid/data from sequences) or "sink" (drives ready with
random backpressure, probability `ready_prob`). Both modes run a StreamMonitor
that publishes every handshake as a StreamSeqItem on `agent.ap`.
"""
import random
from dataclasses import dataclass

from cocotb.triggers import RisingEdge
from pyuvm import (ConfigDB, uvm_agent, uvm_analysis_port, uvm_driver, uvm_monitor,
                   uvm_sequence, uvm_sequence_item, uvm_sequencer)


def _bit(sig) -> int:
    """Read a 1-bit signal as int; X/Z (4-state simulators before reset) count as 0."""
    v = sig.value
    return int(v) if v.is_resolvable else 0


@dataclass
class StreamIf:
    clk: object
    valid: object
    ready: object
    data: object


class StreamSeqItem(uvm_sequence_item):
    def __init__(self, name="item", data=0, gap=0):
        super().__init__(name)
        self.data = data      # payload word
        self.gap = gap        # idle cycles before asserting valid

    def __eq__(self, other):
        return isinstance(other, StreamSeqItem) and self.data == other.data

    def __str__(self):
        return f"{self.get_name()}(data=0x{self.data:x})"


class StreamRandomSeq(uvm_sequence):
    """N random words with random gaps; width in bits and max gap are attributes."""
    n = 32
    width = 32
    max_gap = 3

    async def body(self):
        for i in range(self.n):
            item = StreamSeqItem(f"w{i}", random.getrandbits(self.width), random.randint(0, self.max_gap))
            await self.start_item(item)
            await self.finish_item(item)


class StreamSourceDriver(uvm_driver):
    def build_phase(self):
        self.vif = ConfigDB().get(self, "", "stream_if")

    async def run_phase(self):
        self.vif.valid.value = 0
        self.vif.data.value = 0
        while True:
            item = await self.seq_item_port.get_next_item()
            for _ in range(item.gap):
                await RisingEdge(self.vif.clk)
            self.vif.valid.value = 1
            self.vif.data.value = item.data
            # Sample right after the edge: values are pre-NBA, i.e. what the DUT saw at this edge.
            while True:
                await RisingEdge(self.vif.clk)
                if _bit(self.vif.ready) == 1:
                    break
            self.vif.valid.value = 0
            self.seq_item_port.item_done()


class StreamSinkDriver(uvm_driver):
    """Drives `ready` with Bernoulli(ready_prob) backpressure each cycle."""
    def build_phase(self):
        self.vif = ConfigDB().get(self, "", "stream_if")
        self.ready_prob = ConfigDB().get(self, "", "ready_prob") if ConfigDB().exists(self, "", "ready_prob") else 0.5

    async def run_phase(self):
        self.vif.ready.value = 0
        while True:
            await RisingEdge(self.vif.clk)
            self.vif.ready.value = 1 if random.random() < self.ready_prob else 0


class StreamMonitor(uvm_monitor):
    def build_phase(self):
        self.vif = ConfigDB().get(self, "", "stream_if")
        self.ap = uvm_analysis_port("ap", self)
        self.count = 0

    async def run_phase(self):
        while True:
            await RisingEdge(self.vif.clk)
            if _bit(self.vif.valid) == 1 and _bit(self.vif.ready) == 1:
                self.count += 1
                self.ap.write(StreamSeqItem(f"mon{self.count}", int(self.vif.data.value)))


class StreamAgent(uvm_agent):
    def build_phase(self):
        super().build_phase()
        self.mode = ConfigDB().get(self, "", "mode") if ConfigDB().exists(self, "", "mode") else "source"
        self.monitor = StreamMonitor.create("monitor", self)
        self.ap = uvm_analysis_port("ap", self)   # monitor.ap is forwarded here in connect_phase
        self.sequencer = None
        self.driver = None
        if self.mode == "source":
            self.sequencer = uvm_sequencer("sequencer", self)
            self.driver = StreamSourceDriver.create("driver", self)
        else:
            self.driver = StreamSinkDriver.create("driver", self)

    def connect_phase(self):
        self.monitor.ap.connect(self.ap)
        if self.sequencer is not None:
            self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
