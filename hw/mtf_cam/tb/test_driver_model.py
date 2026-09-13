"""RTL-cosim of the stage-10 driver model (hw-integrate, SimBackend path).

This is a SEPARATE cocotb module so the default suite (`make sim`,
MODULE=test_mtf_cam) stays at 16/16 and does not collide with its directed
`test_driver`. Run this one explicitly:

    make -C hw/mtf_cam sim MODULE=test_driver_model

It builds the same MtfEnv (AXI-Lite agent + s_sym source + m_l sink +
scoreboard) and runs the driver-model API (`hw/mtf_cam/driver/mtf_cam_driver.py`)
against the DUT through `SimBackend`, driving the identical register constants
that `check_regmap.py` proves against the MAS and the RTL. The symbols are
queued on the cocotbext `s_sym` source; the scoreboard checks the L-vector,
counters and sticky STATUS against the frozen golden predictor, so a green run
means the driver's register sequence drove a correct block through the RTL."""
import os
import struct
import sys

import cocotb
import list_model
from cocotb.triggers import ClockCycles, RisingEdge
from cocotbext.axi import AxiStreamFrame
from pyuvm import ConfigDB, uvm_root

from base_test import BaseTest
from env import MtfEnv, make_beat, SYMBOLS_IN, BYTES_OUT, MAX_RUN
from smoke import MtfBaseSeq

# driver/ is not on the cocotb PYTHONPATH — add it.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "driver"))
from mtf_cam_driver import MtfDriver, SimBackend, ID, ID_VALUE  # noqa: E402

W = 8
SMOKE_USED = [65, 66, 67, 68]
SMOKE_SYMS = [0, 0, 2, 3, 2, 5]                 # RUNA,RUNA -> run 3 ; MTF r1,r2,r1 ; EOB
SMOKE_LVEC_LEN = 6                              # 65,65,65,66,67,66
SMOKE_MAX_RUN = 3


def _syms_to_bytes(symbols, alphabet):
    eob = alphabet - 1
    buf = bytearray()
    for s in symbols:
        buf += struct.pack("<I", make_beat(s, s == eob))
    return bytes(buf)


class DriverModelSeq(MtfBaseSeq):
    """Run the driver-model API over SimBackend (this sequence's own AXI wr/rd)."""

    async def body(self):
        backend = SimBackend(self)
        drv = MtfDriver(backend)
        ident = await backend.read32(ID)
        assert ident == ID_VALUE, f"ID 0x{ident:08x} != MTF1"
        caps = await drv.caps()
        assert caps["W"] in (4, 8, 16), caps
        # full API: configure -> doorbell -> wait_done -> read counters -> W1C
        c = await drv.expand_block(SMOKE_SYMS, SMOKE_USED, max_polls=5000)
        assert c["bytes_out"] == SMOKE_LVEC_LEN, f"BYTES_OUT {c['bytes_out']} != {SMOKE_LVEC_LEN}"
        assert c["symbols_in"] == len(SMOKE_SYMS), f"SYMBOLS_IN {c['symbols_in']} != {len(SMOKE_SYMS)}"
        assert c["max_run"] == SMOKE_MAX_RUN, f"MAX_RUN {c['max_run']} != {SMOKE_MAX_RUN}"
        assert c["init_cycles"] == len(SMOKE_USED), f"INIT_CYCLES {c['init_cycles']} != {len(SMOKE_USED)}"
        self.counters = c


class MtfDriverModelTest(BaseTest):
    env_class = MtfEnv
    clk_period_ns = 20

    def build_phase(self):
        ConfigDB().set(None, "*", "predictor", list_model)
        ConfigDB().set(None, "*", "W", W)
        super().build_phase()

    async def main(self):
        # queue the symbol frame on s_sym (waits on tready=0 until the doorbell's INIT)
        self.env.l_sink.clear_pause_generator()
        self.env.l_sink.pause = False
        await self.env.sym_source.send(AxiStreamFrame(_syms_to_bytes(SMOKE_SYMS, len(SMOKE_USED) + 2)))
        seq = DriverModelSeq("drivermodel")
        await seq.start(self.env.agent.sequencer)
        self.logger.info(f"driver_model counters: {seq.counters}")


@cocotb.test()
async def driver_model(_dut):
    await uvm_root().run_test("MtfDriverModelTest")
