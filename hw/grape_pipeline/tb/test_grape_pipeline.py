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
from smoke import (CTRL, CYCLES_LO, IRQ_EN, STATUS, ST_DONE, BODY_BASE, DT_LO,
                   CornerSeq, GrapeBaseSeq, SmokeSeq)
from random_abort import AbortSeq
from random_cfg import RandCfgSeq
from random_err import ErrSeq
from random_fp import FpSeq


class GrapeBaseTest(BaseTest):
    env_class = GrapeEnv
    clk_period_ns = 20                     # MAS §3: 50 MHz target

    k1_enforce = False                     # True for benchmark-shaped configs (PRD KPI)

    def build_phase(self):
        ConfigDB().set(None, "*", "golden", emulation)
        ConfigDB().set(None, "*", "k1_enforce", self.k1_enforce)
        super().build_phase()


class GrapeSmokeTest(GrapeBaseTest):
    k1_enforce = True

    async def main(self):
        bodies, _ = nbody_ref.benchmark_system()
        seq = SmokeSeq("smoke", dt=0.01, nsteps=2,
                       bodies=copy.deepcopy(bodies), pairs=[(0, 1), (0, 2)])
        await seq.start(self.env.agent.sequencer)


@cocotb.test()
async def smoke(_dut):
    await uvm_root().run_test("GrapeSmokeTest")


class GrapeCornerTest(GrapeBaseTest):
    k1_enforce = True

    async def main(self):
        bodies, _ = nbody_ref.benchmark_system()
        await CornerSeq("corner", bodies=copy.deepcopy(bodies)).start(self.env.agent.sequencer)


@cocotb.test()
async def corner(_dut):
    await uvm_root().run_test("GrapeCornerTest")


class GrapeRandomTest(GrapeBaseTest):
    async def main(self):
        import os
        seed = int(os.environ.get("RANDOM_SEED", "1"))
        await RandCfgSeq("rand_cfg", seed=seed, n_runs=25).start(self.env.agent.sequencer)


@cocotb.test()
async def random_cfg(_dut):
    await uvm_root().run_test("GrapeRandomTest")


class GrapeErrTest(GrapeBaseTest):
    async def main(self):
        await ErrSeq("err", seed=2).start(self.env.agent.sequencer)


@cocotb.test()
async def errors(_dut):
    await uvm_root().run_test("GrapeErrTest")


class GrapeAbortTest(GrapeBaseTest):
    async def main(self):
        await AbortSeq("abort", seed=3, clk=self.clk).start(self.env.agent.sequencer)


@cocotb.test()
async def abort(_dut):
    await uvm_root().run_test("GrapeAbortTest")


class QuietSeq(GrapeBaseSeq):
    async def body(self):
        await self.rd(STATUS)


class GrapeFpTest(GrapeBaseTest):
    async def main(self):
        from cocotb.triggers import ClockCycles
        await FpSeq("fp").start(self.env.agent.sequencer)
        await ClockCycles(self.clk, 100)           # F-24: flags stay quiet while idle
        await QuietSeq("quiet").start(self.env.agent.sequencer)


@cocotb.test()
async def fp_flags(_dut):
    await uvm_root().run_test("GrapeFpTest")


class IrqOnSeq(GrapeBaseSeq):
    """Enable DONE irq, run one short invocation to DONE."""
    def __init__(self, name="irq_on", bodies=None):
        super().__init__(name)
        self.bodies = bodies

    async def body(self):
        await self.wr(IRQ_EN, ST_DONE)
        await self.program(0.01, 1, self.bodies, [(0, 1)])
        await self.run_to_done(1)


class W1cSeq(GrapeBaseSeq):
    async def body(self):
        await self.wr(STATUS, ST_DONE)
        await self.rd(STATUS)                      # W1C efficacy: DONE must read back 0


class GrapeIrqTest(GrapeBaseTest):
    async def main(self):
        from cocotb.triggers import ClockCycles
        bodies, _ = nbody_ref.benchmark_system()
        await IrqOnSeq("irq_on", bodies=copy.deepcopy(bodies)).start(self.env.agent.sequencer)
        await ClockCycles(self.clk, 3)
        assert int(self.dut.irq.value) == 1, "irq low after DONE with IRQ_EN set (PRD-F12)"
        await W1cSeq("w1c").start(self.env.agent.sequencer)
        await ClockCycles(self.clk, 3)
        assert int(self.dut.irq.value) == 0, "irq high after W1C (PRD-F12)"


@cocotb.test()
async def irq(_dut):
    await uvm_root().run_test("GrapeIrqTest")


class DoorbellOnlySeq(GrapeBaseSeq):
    def __init__(self, name="db_only", bodies=None):
        super().__init__(name)
        self.bodies = bodies

    async def body(self):
        await self.program(0.02, 5, self.bodies, [(0, 1), (1, 2), (2, 3)])
        await self.wr(CTRL, 1)


class ReadbackSeq(GrapeBaseSeq):
    async def body(self):
        await self.rd(STATUS)                      # sticky must be 0 after reset
        await self.rd(DT_LO)                       # config regs at reset values
        await self.rd(CYCLES_LO)
        await self.rd(BODY_BASE)
        await self.rd(BODY_BASE + 4)


class GrapeResetTest(GrapeBaseTest):
    async def main(self):
        from cocotb.triggers import ClockCycles, RisingEdge
        bodies, _ = nbody_ref.benchmark_system()
        await DoorbellOnlySeq("db", bodies=copy.deepcopy(bodies)).start(self.env.agent.sequencer)
        await ClockCycles(self.clk, 60)            # mid-run (step ~ half done)
        self.rst_n.value = 0                       # PRD-F15: synchronous reset mid-invocation
        await ClockCycles(self.clk, 3)
        self.rst_n.value = 1
        await ClockCycles(self.clk, 3)
        await ReadbackSeq("rb").start(self.env.agent.sequencer)
        # re-run from scratch: bit-exact as any fresh invocation
        seq = SmokeSeq("rerun", dt=0.01, nsteps=2,
                       bodies=copy.deepcopy(bodies), pairs=[(0, 1), (0, 2)])
        await seq.start(self.env.agent.sequencer)


@cocotb.test()
async def reset_midrun(_dut):
    await uvm_root().run_test("GrapeResetTest")


class GrapeFullBenchTest(GrapeBaseTest):
    """Sign-off equivalence (testplan §4): the whole benchmark call through the DUT, then the
    PRD-F4/F5 tolerances against nbody_ref (the benchmark's own libm-pow advance)."""
    k1_enforce = True

    def build_phase(self):
        ConfigDB().set(None, "*", "min_body_compares", 70)   # review S5: the F-04/F-05 chain
        super().build_phase()                                # rests on these compares happening

    async def main(self):
        from full_bench import FullBenchSeq

        bodies, pair_objs = nbody_ref.benchmark_system()
        idx = {id(b): i for i, b in enumerate(bodies)}
        pairs = [(idx[id(b1)], idx[id(b2)]) for (b1, b2) in pair_objs]
        await FullBenchSeq("full_bench", bodies=copy.deepcopy(bodies), pairs=pairs,
                           nsteps=20000).start(self.env.agent.sequencer)
        # DUT-equivalent state: emulation model (scoreboard proves DUT == emulation bit-exact)
        em = copy.deepcopy(bodies)
        em_pairs = [(em[i], em[j]) for (i, j) in pairs]
        emulation.advance(0.01, 20000, em, em_pairs)
        # Reference: the benchmark's own module-level SYSTEM through its generated advance()
        ref_sys = nbody_ref._bm.SYSTEM
        nbody_ref.offset_momentum(ref_sys[0], ref_sys)
        nbody_ref.advance(0.01, 20000)
        e_ref = nbody_ref.report_energy()
        e_hw = nbody_ref.report_energy(bodies=em, pairs=nbody_ref.combinations(em))
        rel_e = abs(e_hw - e_ref) / abs(e_ref)
        assert rel_e <= 1e-12, f"PRD-F4: |dE/E| = {rel_e:.3e} > 1e-12"
        worst_r = worst_v = 0.0
        for (r_h, v_h, _), (r_r, v_r, _) in zip(em, ref_sys):
            nr = max(sum(x * x for x in r_r) ** 0.5, 1e-300)
            nv = max(sum(x * x for x in v_r) ** 0.5, 1e-300)
            dr = sum((a - b) ** 2 for a, b in zip(r_h, r_r)) ** 0.5 / nr
            dv = sum((a - b) ** 2 for a, b in zip(v_h, v_r)) ** 0.5 / nv
            worst_r, worst_v = max(worst_r, dr), max(worst_v, dv)
        assert worst_r <= 2e-9, f"PRD-F5: r deviation {worst_r:.3e} > 2e-9"
        assert worst_v <= 5e-11, f"PRD-F5: v deviation {worst_v:.3e} > 5e-11"
        self.logger.info(f"full benchmark: |dE/E| = {rel_e:.3e} (<= 1e-12), "
                         f"r dev {worst_r:.3e} (<= 2e-9), v dev {worst_v:.3e} (<= 5e-11)")


@cocotb.test()
async def full_benchmark(_dut):
    import cocotb as _c
    if "icarus" in _c.SIM_NAME.lower():
        _c.log.info("full_benchmark: Verilator-only (Icarus ~8x slower; 4-state X-check "
                    "covered by the 8-test suite)")
        return
    await uvm_root().run_test("GrapeFullBenchTest")
