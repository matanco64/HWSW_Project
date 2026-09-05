"""AXI4-Lite agent: pyuvm driver wrapping cocotbext-axi AxiLiteMaster, plus a passive monitor.

Config: "axil_bus_prefix" (default "s_axi"), plus "dut", "clk", "rst_n" from BaseTest.
Sequence items are AxiLiteSeqItem(kind="write"|"read", addr, data); reads fill `item.data`
and both fill `item.resp`. The monitor samples the pins independently of the driver
(PRD-F16-style protocol independence), emits completed transactions on `ap` (bus order),
`ap_write` and `ap_read`, and asserts that DUT-driven signals are X-free after reset.
"""
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from pyuvm import (ConfigDB, uvm_agent, uvm_analysis_port, uvm_driver, uvm_monitor,
                   uvm_sequence_item, uvm_sequencer)


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
                r = await self.master.write(item.addr, item.data.to_bytes(4, "little"))
                item.resp = r.resp
            else:
                r = await self.master.read(item.addr, 4)
                item.data = int.from_bytes(r.data, "little")
                item.resp = r.resp
            self.seq_item_port.item_done()


class AxiLiteAgent(uvm_agent):
    def build_phase(self):
        super().build_phase()
        self.sequencer = uvm_sequencer("sequencer", self)
        self.driver = AxiLiteDriver.create("driver", self)
        self.monitor = AxiLiteMonitor.create("monitor", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)


class AxiLiteMonitor(uvm_monitor):
    """Passive: reconstructs write (AW+W+B) and read (AR+R) transactions from handshakes."""

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "dut")
        self.clk = ConfigDB().get(self, "", "clk")
        self.rst_n = ConfigDB().get(self, "", "rst_n")
        self.prefix = (ConfigDB().get(self, "", "axil_bus_prefix")
                       if ConfigDB().exists(self, "", "axil_bus_prefix") else "s_axi")
        self.ap = uvm_analysis_port("ap", self)
        self.ap_write = uvm_analysis_port("ap_write", self)
        self.ap_read = uvm_analysis_port("ap_read", self)

    def _sig(self, name):
        return getattr(self.dut, f"{self.prefix}_{name}")

    @staticmethod
    def _hs(valid, ready):
        # Called only after reset is deasserted: X on a handshake signal is a DUT bug, not
        # "no handshake" (review bring-up must-1).
        assert valid.value.is_resolvable, f"axi_lite monitor: {valid._name} is X after reset"
        assert ready.value.is_resolvable, f"axi_lite monitor: {ready._name} is X after reset"
        return int(valid.value) == 1 and int(ready.value) == 1

    async def run_phase(self):
        s = {n: self._sig(n) for n in
             ("awvalid", "awready", "awaddr", "wvalid", "wready", "wdata", "wstrb",
              "bvalid", "bready", "bresp", "arvalid", "arready", "araddr",
              "rvalid", "rready", "rdata", "rresp")}
        aw_q, w_q, ar_q = [], [], []
        while True:
            await RisingEdge(self.clk)
            await ReadOnly()
            if not self.rst_n.value.is_resolvable or int(self.rst_n.value) == 0:
                aw_q.clear(); w_q.clear(); ar_q.clear()
                continue
            if self._hs(s["awvalid"], s["awready"]):
                aw_q.append(int(s["awaddr"].value))
            if self._hs(s["wvalid"], s["wready"]):
                w_q.append((int(s["wdata"].value), int(s["wstrb"].value)))
            if self._hs(s["bvalid"], s["bready"]):
                assert s["bresp"].value.is_resolvable, "axi_lite monitor: BRESP is X"
                assert aw_q and w_q, "axi_lite monitor: B response with no matching AW/W"
                addr = aw_q.pop(0)
                data, strb = w_q.pop(0)
                item = AxiLiteSeqItem("mon_wr", kind="write", addr=addr, data=data)
                item.strb = strb
                item.resp = int(s["bresp"].value)
                self.ap_write.write(item)
                self.ap.write(item)
            if self._hs(s["arvalid"], s["arready"]):
                ar_q.append(int(s["araddr"].value))
            if self._hs(s["rvalid"], s["rready"]):
                assert s["rdata"].value.is_resolvable, "axi_lite monitor: RDATA is X"
                assert s["rresp"].value.is_resolvable, "axi_lite monitor: RRESP is X"
                assert ar_q, "axi_lite monitor: R response with no matching AR"
                item = AxiLiteSeqItem("mon_rd", kind="read",
                                      addr=ar_q.pop(0), data=int(s["rdata"].value))
                item.resp = int(s["rresp"].value)
                self.ap_read.write(item)
                self.ap.write(item)
