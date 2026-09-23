"""RTL-cosim of the stage-10 driver model (hw-integrate, SimBackend path).

This is a SEPARATE cocotb module so the default suite (`make sim`,
MODULE=test_grape_pipeline) keeps its test count. Run this one explicitly:

    make -C hw/grape_pipeline sim MODULE=test_driver_model

It builds the same GrapeEnv (AXI-Lite agent + scoreboard replaying golden
`emulation.advance`) and runs the driver-model API
(`hw/grape_pipeline/driver/grape_pipeline_driver.py`) against the DUT through
`SimBackend`, driving the identical register constants that `check_regmap.py`
proves against the MAS. One benchmark-shaped `advance(0.01, 2, bodies, pairs)`
(5 bodies, all 10 pairs, benchmark order) goes through load -> doorbell ->
poll -> read-back -> W1C; the state the driver reads back is asserted
bit-exact against the golden model run from the same initial state, and CYCLES
against K1 = 124 cycles/step with the scoreboard's tolerance (<= 128)."""
import copy
import os
import struct
import sys

import cocotb
import emulation
from pyuvm import ConfigDB, uvm_root

from base_test import BaseTest
from env import GrapeEnv, K1 as K1_TOL
from smoke import GrapeBaseSeq

# driver/ is not on the cocotb PYTHONPATH — add it.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "driver"))
from grape_pipeline_driver import (  # noqa: E402
    AsyncGrapeDriver, SimBackend, ID, ID_VALUE, K1_CYCLES_PER_STEP, ST_DONE)
from test_driver import BODIES, pairs_from  # noqa: E402

DT = 0.01
NSTEPS = 2


def _bits(x):
    return struct.pack("<d", float(x))


class DriverModelSeq(GrapeBaseSeq):
    """Run the driver-model API over SimBackend (this sequence's own AXI wr/rd)."""

    async def body(self):
        backend = SimBackend(self)
        drv = AsyncGrapeDriver(backend)
        ident = await backend.read32(ID)
        assert ident == ID_VALUE, f"ID 0x{ident:08x} != GRP1"

        # benchmark call shape: pairs are tuples of the same list objects as `bodies`
        bodies = copy.deepcopy(BODIES)
        pairs = pairs_from(bodies)
        await drv.advance(DT, NSTEPS, bodies, pairs)

        # golden reference from the same initial state, same pair order
        ref = copy.deepcopy(BODIES)
        ref_pairs = pairs_from(ref)
        flags = emulation.advance(DT, NSTEPS, ref, ref_pairs)
        assert not flags, f"golden raised FP flags on the benchmark system: {flags}"
        self.body_compares = 0
        for i, ((r_h, v_h, m_h), (r_g, v_g, m_g)) in enumerate(zip(bodies, ref)):
            for name, a, b in (("x", r_h[0], r_g[0]), ("y", r_h[1], r_g[1]), ("z", r_h[2], r_g[2]),
                               ("vx", v_h[0], v_g[0]), ("vy", v_h[1], v_g[1]), ("vz", v_h[2], v_g[2]),
                               ("m", m_h, m_g)):
                assert _bits(a) == _bits(b), \
                    f"body {i}.{name}: DUT {a!r} != golden {b!r} (bit-exact)"
                self.body_compares += 1

        c = await drv.counters()
        assert c["steps_done"] == NSTEPS, f"STEPS_DONE {c['steps_done']} != {NSTEPS}"
        per_step = c["cycles"] / NSTEPS
        assert c["cycles"] >= NSTEPS, f"CYCLES {c['cycles']} < steps {NSTEPS} (dead counter)"
        assert per_step <= K1_TOL, f"K1: {c['cycles']}/{NSTEPS} = {per_step:.1f} > {K1_TOL}"
        assert not (await drv.status() & ST_DONE), "DONE still set after advance()'s W1C"
        self.counters = c
        self.per_step = per_step


class GrapeDriverModelTest(BaseTest):
    env_class = GrapeEnv
    clk_period_ns = 20                     # MAS §3: 50 MHz target

    def build_phase(self):
        ConfigDB().set(None, "*", "golden", emulation)
        ConfigDB().set(None, "*", "k1_enforce", True)      # benchmark-shaped pair list
        ConfigDB().set(None, "*", "min_body_compares", 60)  # read_bodies: 5 x 6 x 2 words
        super().build_phase()

    async def main(self):
        seq = DriverModelSeq("drivermodel")
        await seq.start(self.env.agent.sequencer)
        self.logger.info(f"driver_model: {seq.body_compares} components bit-exact vs golden, "
                         f"counters {seq.counters}, {seq.per_step:.1f} cycles/step "
                         f"(K1 = {K1_CYCLES_PER_STEP}, tol <= {K1_TOL})")


@cocotb.test()
async def driver_model(_dut):
    await uvm_root().run_test("GrapeDriverModelTest")
