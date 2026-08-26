"""AXI4-Lite agent: pyuvm driver wrapping cocotbext-axi AxiLiteMaster.

Config: "axil_bus_prefix" (default "s_axi"), plus "dut", "clk", "rst_n" from BaseTest.
Sequence items are AxiLiteSeqItem(kind="write"|"read", addr, data); reads fill `item.data`
and both fill `item.resp`.
"""
from cocotb.triggers import Timer
from pyuvm import ConfigDB, uvm_agent, uvm_driver, uvm_sequence_item, uvm_sequencer


class AxiLiteSeqItem(uvm_sequence_item):
    def __init__(self, name="axil", kind="read", addr=0, data=0):
        super().__init__(name)
        self.kind = kind
        self.addr = addr
        self.data = data
        self.resp = None

    def __str__(self):
        return f"{self.kind} @0x{self.addr:x} data=0x{self.data:x} resp={self.resp}"


class AxiLiteDriver(uvm_driver):
    def build_phase(self):
        from cocotbext.axi import AxiLiteBus, AxiLiteMaster  # lazy: optional dependency

        dut = ConfigDB().get(self, "", "dut")
        clk = ConfigDB().get(self, "", "clk")
        rst_n = ConfigDB().get(self, "", "rst_n")
        prefix = ConfigDB().get(self, "", "axil_bus_prefix") if ConfigDB().exists(self, "", "axil_bus_prefix") else "s_axi"
        self.master = AxiLiteMaster(AxiLiteBus.from_prefix(dut, prefix), clk, rst_n, reset_active_level=False)

    async def run_phase(self):
        while True:
            item = await self.seq_item_port.get_next_item()
            if item.kind == "write":
                r = await self.master.write_dword(item.addr, item.data)
                item.resp = r.resp
            else:
                r = await self.master.read_dword(item.addr)
                item.data = r.data if isinstance(r.data, int) else int.from_bytes(r.data, "little")
                item.resp = r.resp
            self.seq_item_port.item_done()


class AxiLiteAgent(uvm_agent):
    def build_phase(self):
        super().build_phase()
        self.sequencer = uvm_sequencer("sequencer", self)
        self.driver = AxiLiteDriver.create("driver", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)
