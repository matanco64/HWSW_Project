"""Unit tests for grape_regs behind axi_lite_if, with grape_body_rf as the committed bank
(MAS docs/mas.md par.4/par.5/par.8, ADR-0005). DUT: grape_regs_tb_top (TB-only wrapper).

The test plays the step FSM itself: it drives busy_i/done_set_i/aborted_set_i/fp_flags_set_i,
the counters, and the body RF datapath write/commit ports of the wrapper.

Run (from the repo root):

    make -C hw/grape_pipeline sim TOPLEVEL=grape_regs_tb_top MODULE=unit.test_regs

If concurrently developed rtl/fp64_*.sv files break the wildcard build, pin the sources on the
command line (no Makefile edits needed):

    make -C hw/grape_pipeline sim TOPLEVEL=grape_regs_tb_top MODULE=unit.test_regs \
        VERILOG_SOURCES="rtl/grape_regs.sv rtl/grape_body_rf.sv rtl/grape_regs_tb_top.sv \
                         ../common/rtl/axi_lite_if.sv"

KNOWN MAS MISMATCH (test green since the RTL fix): MAS par.8 "DOORBELL + ABORT in one write, BUSY:
ABORT acts AND ERR_BUSY (the doorbell was ignored)". grape_regs.sv takes the abort branch
exclusively (if wr_data[1] ... else if wr_data[0]) and (FIXED 2026-09-05: now sets ERR_BUSY per MAS §8), so
test_abort_doorbell_while_busy_sets_err_busy fails against the current RTL.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge
from cocotbext.axi import AxiLiteBus, AxiLiteMaster
from cocotbext.axi.constants import AxiResp

# ---- register map (byte offsets, MAS par.4) ----------------------------------------------------
R_ID         = 0x000
R_VERSION    = 0x004
R_CTRL       = 0x008
R_STATUS     = 0x00C
R_IRQ_EN     = 0x010
R_IRQ_STATUS = 0x014
R_CYCLES_LO  = 0x040
R_CYCLES_HI  = 0x044
R_STEPS_DONE = 0x048
R_DT_LO      = 0x100
R_DT_HI      = 0x104
R_NSTEPS     = 0x108
R_NPAIRS     = 0x10C

ID_VALUE = 0x47525031  # "GRP1"

# STATUS bits
S_BUSY      = 1 << 0
S_DONE      = 1 << 1
S_ABORTED   = 1 << 2
S_ERR_BUSY  = 1 << 8
S_ERR_PARAM = 1 << 9

# CTRL bits
C_DOORBELL = 1 << 0
C_ABORT    = 1 << 1

N_BODIES = 5
N_PAIRS_MAX = 10


def body_addr(body, field, hi=False):
    """Byte address of BODY[body] field (0..2 pos, 3..5 vel, 6 mass), low or high word."""
    return 0x200 + 64 * body + 8 * field + (4 if hi else 0)


def pair_addr(k):
    return 0x400 + 4 * k


class PulseCounter:
    """Counts single-cycle pulses of a registered signal, sampled after each rising edge."""

    def __init__(self, clk, sig):
        self.count = 0
        self._task = cocotb.start_soon(self._run(clk, sig))

    async def _run(self, clk, sig):
        while True:
            await RisingEdge(clk)
            if sig.value:
                self.count += 1


async def setup(dut):
    """Clock, reset, zeroed step-FSM/body-RF inputs; returns an AxiLiteMaster."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst_n.value = 0
    dut.busy_i.value = 0
    dut.done_set_i.value = 0
    dut.aborted_set_i.value = 0
    dut.fp_flags_set_i.value = 0
    dut.steps_done_i.value = 0
    dut.cycles_i.value = 0
    dut.bwr_en_i.value = 0
    dut.bwr_body_i.value = 0
    dut.bwr_field_i.value = 0
    dut.bwr_data_i.value = 0
    dut.commit_en_i.value = 0
    axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "s_axi"), dut.clk, dut.rst_n,
                         reset_active_level=False)
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)
    return axil


async def rd32(axil, addr):
    """32-bit read; returns (value, resp)."""
    r = await axil.read(addr, 4)
    return int.from_bytes(r.data, "little"), r.resp


async def wr32(axil, addr, value):
    """32-bit write; returns resp."""
    w = await axil.write(addr, value.to_bytes(4, "little"))
    return w.resp


async def rd_ok(axil, addr):
    v, resp = await rd32(axil, addr)
    assert resp == AxiResp.OKAY, f"read 0x{addr:03X}: RRESP {resp!r}, expected OKAY"
    return v


async def wr_ok(axil, addr, value):
    resp = await wr32(axil, addr, value)
    assert resp == AxiResp.OKAY, f"write 0x{addr:03X}: BRESP {resp!r}, expected OKAY"


async def rf_write(dut, body, field, value):
    """One working-bank write through the wrapper's body RF write port."""
    dut.bwr_body_i.value = body
    dut.bwr_field_i.value = field
    dut.bwr_data_i.value = value
    dut.bwr_en_i.value = 1
    await RisingEdge(dut.clk)
    dut.bwr_en_i.value = 0


async def rf_commit(dut):
    """One commit pulse (working -> committed)."""
    dut.commit_en_i.value = 1
    await RisingEdge(dut.clk)
    dut.commit_en_i.value = 0
    await RisingEdge(dut.clk)


GOOD_DT = 0x3FD0000000000000  # 0.25
GOOD_NSTEPS = 3
GOOD_NPAIRS = 2
GOOD_PAIRS = [0x0100, 0x0302]  # (i=0,j=1), (i=2,j=3)


async def write_good_config(axil):
    await wr_ok(axil, R_DT_LO, GOOD_DT & 0xFFFFFFFF)
    await wr_ok(axil, R_DT_HI, GOOD_DT >> 32)
    await wr_ok(axil, R_NSTEPS, GOOD_NSTEPS)
    await wr_ok(axil, R_NPAIRS, GOOD_NPAIRS)
    for k, p in enumerate(GOOD_PAIRS):
        await wr_ok(axil, pair_addr(k), p)


async def ring_doorbell_accepted(dut, axil):
    """Ring CTRL.DOORBELL, drive busy_i=1 on the doorbell_o pulse (as the step FSM would),
    check the ADR-0005 response ordering. Returns after BRESP with busy_i = 1."""
    db = PulseCounter(dut.clk, dut.doorbell_o)

    async def busy_on_doorbell():
        while True:
            await RisingEdge(dut.clk)
            if dut.doorbell_o.value:
                dut.busy_i.value = 1
                return

    busy_task = cocotb.start_soon(busy_on_doorbell())
    resp = await wr32(axil, R_CTRL, C_DOORBELL)
    assert resp == AxiResp.OKAY, f"doorbell BRESP {resp!r}, expected OKAY"
    # ADR-0005: BRESP only after acceptance is visible in STATUS -> the doorbell pulse (and the
    # busy_i the FSM raises on it) must precede the write response.
    assert db.count == 1, f"doorbell_o pulsed {db.count} times before BRESP, expected exactly 1"
    assert busy_task.done() and int(dut.busy_i.value) == 1
    status = await rd_ok(axil, R_STATUS)
    assert status & S_BUSY, f"STATUS 0x{status:X}: BUSY clear right after accepted doorbell"


# ---- tests -------------------------------------------------------------------------------------

@cocotb.test()
async def test_id_version_ctrl_reset(dut):
    """ID/VERSION constants, CTRL and STATUS read 0 after reset (MAS par.3, par.4)."""
    axil = await setup(dut)
    assert await rd_ok(axil, R_ID) == ID_VALUE
    assert await rd_ok(axil, R_VERSION) == 0
    assert await rd_ok(axil, R_CTRL) == 0
    assert await rd_ok(axil, R_STATUS) == 0
    assert await rd_ok(axil, R_IRQ_EN) == 0
    assert await rd_ok(axil, R_IRQ_STATUS) == 0
    assert int(dut.irq_o.value) == 0


@cocotb.test()
async def test_config_roundtrip_idle(dut):
    """While idle every RW config register reads back what was written, incl. wstrb partial
    writes; reserved low bits (NPAIRS[31:8], PAIR[31:16], IRQ_EN[0]) read 0 (MAS par.4)."""
    axil = await setup(dut)
    # DT full 64-bit round trip
    await wr_ok(axil, R_DT_LO, 0x89ABCDEF)
    await wr_ok(axil, R_DT_HI, 0x01234567)
    assert await rd_ok(axil, R_DT_LO) == 0x89ABCDEF
    assert await rd_ok(axil, R_DT_HI) == 0x01234567
    # NSTEPS + wstrb partial write (single byte at offset +2 -> byte lane 2 only)
    await wr_ok(axil, R_NSTEPS, 0x11223344)
    w = await axil.write(R_NSTEPS + 2, b"\xAA")
    assert w.resp == AxiResp.OKAY
    assert await rd_ok(axil, R_NSTEPS) == 0x11AA3344
    # NPAIRS: bits 7:0 RW, upper bits reserved read 0
    await wr_ok(axil, R_NPAIRS, 0xFFFFFF07)
    assert await rd_ok(axil, R_NPAIRS) == 0x07
    # BODY window: first and last used words, plus a partial byte write
    await wr_ok(axil, body_addr(0, 0), 0xDEADBEEF)          # body0 x lo
    await wr_ok(axil, body_addr(0, 0, hi=True), 0x40080000) # body0 x hi
    await wr_ok(axil, body_addr(4, 6), 0x55667788)          # body4 mass lo (0x330)
    await wr_ok(axil, body_addr(4, 6, hi=True), 0x3FF00000)
    w = await axil.write(body_addr(0, 0) + 3, b"\x99")      # byte lane 3 of x lo
    assert w.resp == AxiResp.OKAY
    assert await rd_ok(axil, body_addr(0, 0)) == 0x99ADBEEF
    assert await rd_ok(axil, body_addr(0, 0, hi=True)) == 0x40080000
    assert await rd_ok(axil, body_addr(4, 6)) == 0x55667788
    assert await rd_ok(axil, body_addr(4, 6, hi=True)) == 0x3FF00000
    # PAIR window: bits 15:0 RW, upper bits reserved read 0
    await wr_ok(axil, pair_addr(0), 0xFFFF0201)
    await wr_ok(axil, pair_addr(9), 0x00000403)
    assert await rd_ok(axil, pair_addr(0)) == 0x0201
    assert await rd_ok(axil, pair_addr(9)) == 0x0403
    # IRQ_EN: bits 16:1 RW, bit 0 reserved reads 0
    await wr_ok(axil, R_IRQ_EN, 0x1FFFF)
    assert await rd_ok(axil, R_IRQ_EN) == 0x1FFFE


@cocotb.test()
async def test_reserved_and_unmapped(dut):
    """Listed reserved words: write ignored + OKAY, read 0 + OKAY (0x018, 0x0FC, 0x110, 0x238,
    0x340). Unmapped words 0x428, 0xFFC: SLVERR on read AND write (MAS par.4)."""
    axil = await setup(dut)
    for addr in (0x018, 0x0FC, 0x110, 0x238, 0x340):
        resp = await wr32(axil, addr, 0xFFFFFFFF)
        assert resp == AxiResp.OKAY, f"reserved 0x{addr:03X}: BRESP {resp!r}, expected OKAY"
        v, resp = await rd32(axil, addr)
        assert resp == AxiResp.OKAY, f"reserved 0x{addr:03X}: RRESP {resp!r}, expected OKAY"
        assert v == 0, f"reserved 0x{addr:03X} reads 0x{v:08X}, expected 0"
    for addr in (0x428, 0xFFC):
        resp = await wr32(axil, addr, 0x12345678)
        assert resp == AxiResp.SLVERR, f"unmapped 0x{addr:03X}: BRESP {resp!r}, expected SLVERR"
        _, resp = await rd32(axil, addr)
        assert resp == AxiResp.SLVERR, f"unmapped 0x{addr:03X}: RRESP {resp!r}, expected SLVERR"
    # reserved words behave the same while BUSY (no ERR_BUSY)
    dut.busy_i.value = 1
    await wr_ok(axil, 0x018, 0xFFFFFFFF)
    status = await rd_ok(axil, R_STATUS)
    assert not (status & S_ERR_BUSY), "reserved write while BUSY set ERR_BUSY"
    dut.busy_i.value = 0


@cocotb.test()
async def test_doorbell_accept_and_busy_lockout(dut):
    """Good config -> doorbell_o pulse, BRESP only after STATUS shows BUSY, config latched;
    while BUSY config writes are ignored with sticky ERR_BUSY and config reads return the
    latched values (MAS par.4, par.5, ADR-0005)."""
    axil = await setup(dut)
    await write_good_config(axil)
    await ring_doorbell_accepted(dut, axil)
    # latched copies visible on the decoder outputs
    assert int(dut.dt_o.value) == GOOD_DT
    assert int(dut.nsteps_o.value) == GOOD_NSTEPS
    assert int(dut.npairs_o.value) == GOOD_NPAIRS
    pairs = int(dut.pairs_o.value)
    assert pairs & 0xFFFF == GOOD_PAIRS[0]
    assert (pairs >> 16) & 0xFFFF == GOOD_PAIRS[1]
    # config writes while BUSY: ignored, OKAY, sticky ERR_BUSY
    for addr, val in ((R_DT_LO, 0x0BAD0000), (R_NSTEPS, 999), (R_NPAIRS, 1),
                      (body_addr(0, 0), 0x0BAD0001), (pair_addr(0), 0x0403)):
        await wr_ok(axil, addr, val)
    status = await rd_ok(axil, R_STATUS)
    assert status & S_ERR_BUSY, f"STATUS 0x{status:X}: ERR_BUSY clear after config write while BUSY"
    # doorbell while BUSY: ignored with ERR_BUSY too (clear first to see it set again)
    await wr_ok(axil, R_STATUS, S_ERR_BUSY)
    status = await rd_ok(axil, R_STATUS)
    assert not (status & S_ERR_BUSY), "ERR_BUSY did not W1C-clear"
    db = PulseCounter(dut.clk, dut.doorbell_o)
    await wr_ok(axil, R_CTRL, C_DOORBELL)
    status = await rd_ok(axil, R_STATUS)
    assert status & S_ERR_BUSY, "doorbell while BUSY did not set ERR_BUSY"
    assert db.count == 0, "doorbell while BUSY pulsed doorbell_o"
    # config reads while BUSY return the latched values, not the attempted writes
    assert await rd_ok(axil, R_DT_LO) == GOOD_DT & 0xFFFFFFFF
    assert await rd_ok(axil, R_DT_HI) == GOOD_DT >> 32
    assert await rd_ok(axil, R_NSTEPS) == GOOD_NSTEPS
    assert await rd_ok(axil, R_NPAIRS) == GOOD_NPAIRS
    assert await rd_ok(axil, pair_addr(0)) == GOOD_PAIRS[0]
    dut.busy_i.value = 0
    await RisingEdge(dut.clk)
    # back to idle: pending values (the ignored writes never landed -> still the good config)
    assert await rd_ok(axil, R_NSTEPS) == GOOD_NSTEPS


@cocotb.test()
async def test_err_param_rejection(dut):
    """Pair index >= N_BODIES or NPAIRS > N_PAIRS_MAX -> doorbell rejected: no doorbell_o,
    sticky ERR_PARAM, BRESP still OKAY, not BUSY, nothing latched; a later accepted doorbell
    does not clear the sticky bit (MAS par.4, par.8, F17)."""
    axil = await setup(dut)
    await write_good_config(axil)
    # case 1: pair index i = 5 >= N_BODIES
    await wr_ok(axil, R_NPAIRS, 1)
    await wr_ok(axil, pair_addr(0), 0x0005)
    db = PulseCounter(dut.clk, dut.doorbell_o)
    resp = await wr32(axil, R_CTRL, C_DOORBELL)
    assert resp == AxiResp.OKAY
    await ClockCycles(dut.clk, 4)
    assert db.count == 0, "rejected doorbell still pulsed doorbell_o"
    status = await rd_ok(axil, R_STATUS)
    assert status & S_ERR_PARAM, f"STATUS 0x{status:X}: ERR_PARAM clear after bad pair index"
    assert not (status & S_BUSY)
    assert int(dut.nsteps_o.value) == 0, "rejected doorbell latched the config"
    await wr_ok(axil, R_STATUS, S_ERR_PARAM)
    # case 2: NPAIRS = 11 > N_PAIRS_MAX (pairs all valid)
    await wr_ok(axil, pair_addr(0), GOOD_PAIRS[0])
    await wr_ok(axil, R_NPAIRS, N_PAIRS_MAX + 1)
    resp = await wr32(axil, R_CTRL, C_DOORBELL)
    assert resp == AxiResp.OKAY
    await ClockCycles(dut.clk, 4)
    assert db.count == 0
    status = await rd_ok(axil, R_STATUS)
    assert status & S_ERR_PARAM, f"STATUS 0x{status:X}: ERR_PARAM clear after NPAIRS > max"
    # fix the config; the accepted doorbell must NOT clear the sticky ERR_PARAM (F12)
    await wr_ok(axil, R_NPAIRS, GOOD_NPAIRS)
    await ring_doorbell_accepted(dut, axil)
    status = await rd_ok(axil, R_STATUS)
    assert status & S_ERR_PARAM, "accepted doorbell cleared sticky ERR_PARAM"
    dut.busy_i.value = 0


@cocotb.test()
async def test_body_window_committed_while_busy(dut):
    """While BUSY the BODY window reads the committed bank of grape_body_rf: the doorbell load
    first (pending -> both banks), then only after a commit pulse the datapath writes
    (MAS par.4, PRD-F10)."""
    axil = await setup(dut)
    await write_good_config(axil)
    x0 = 0x40091EB851EB851F  # 3.14
    await wr_ok(axil, body_addr(0, 0), x0 & 0xFFFFFFFF)
    await wr_ok(axil, body_addr(0, 0, hi=True), x0 >> 32)
    await ring_doorbell_accepted(dut, axil)
    # doorbell loaded pending into both banks -> committed == written pending
    assert await rd_ok(axil, body_addr(0, 0)) == x0 & 0xFFFFFFFF
    assert await rd_ok(axil, body_addr(0, 0, hi=True)) == x0 >> 32
    # datapath write to the working bank must NOT show before commit
    x0new = 0x4012000000000000  # 4.5
    await rf_write(dut, 0, 0, x0new)
    assert await rd_ok(axil, body_addr(0, 0)) == x0 & 0xFFFFFFFF, \
        "BODY read while BUSY showed an uncommitted working-bank write"
    await rf_commit(dut)
    assert await rd_ok(axil, body_addr(0, 0)) == x0new & 0xFFFFFFFF
    assert await rd_ok(axil, body_addr(0, 0, hi=True)) == x0new >> 32
    dut.busy_i.value = 0


@cocotb.test()
async def test_done_irq_w1c_and_readback(dut):
    """done_set_i -> sticky DONE; irq when IRQ_EN.DONE; W1C clears both; at DONE the committed
    state is copied into the BODY pending registers so the idle read-back returns the result
    (MAS par.4, par.5 step 3, par.8)."""
    axil = await setup(dut)
    await write_good_config(axil)
    x0 = 0x3FF8000000000000  # 1.5
    await wr_ok(axil, body_addr(0, 0), x0 & 0xFFFFFFFF)
    await wr_ok(axil, body_addr(0, 0, hi=True), x0 >> 32)
    await wr_ok(axil, R_IRQ_EN, S_DONE)
    await ring_doorbell_accepted(dut, axil)
    assert int(dut.irq_o.value) == 0
    # "datapath" produces a result and commits it, then the FSM pulses DONE and drops busy
    x0res = 0x4004000000000000  # 2.5
    await rf_write(dut, 0, 0, x0res)
    await rf_commit(dut)
    dut.done_set_i.value = 1
    await RisingEdge(dut.clk)
    dut.done_set_i.value = 0
    dut.busy_i.value = 0
    await RisingEdge(dut.clk)
    assert int(dut.irq_o.value) == 1, "irq did not rise the cycle after DONE was set"
    status = await rd_ok(axil, R_STATUS)
    assert status & S_DONE, f"STATUS 0x{status:X}: DONE clear after done_set_i"
    assert not (status & S_BUSY)
    assert await rd_ok(axil, R_IRQ_STATUS) == S_DONE
    # committed -> pending copy: idle BODY read returns the result
    assert await rd_ok(axil, body_addr(0, 0)) == x0res & 0xFFFFFFFF
    assert await rd_ok(axil, body_addr(0, 0, hi=True)) == x0res >> 32
    # W1C clears DONE, irq falls
    await wr_ok(axil, R_STATUS, S_DONE)
    status = await rd_ok(axil, R_STATUS)
    assert not (status & S_DONE), "DONE did not W1C-clear"
    await ClockCycles(dut.clk, 2)
    assert int(dut.irq_o.value) == 0, "irq did not fall after the W1C"


@cocotb.test()
async def test_abort_pulses(dut):
    """CTRL.ABORT -> abort_o pulse; DOORBELL+ABORT in one write while idle -> abort only, no
    doorbell, no flags; ABORT alone while BUSY -> abort only, no ERR_BUSY (MAS par.4, par.8)."""
    axil = await setup(dut)
    await write_good_config(axil)
    ab = PulseCounter(dut.clk, dut.abort_o)
    db = PulseCounter(dut.clk, dut.doorbell_o)
    # ABORT while idle: pulse to the FSM, no STATUS change
    await wr_ok(axil, R_CTRL, C_ABORT)
    await ClockCycles(dut.clk, 2)
    assert ab.count == 1, f"abort_o pulsed {ab.count} times, expected 1"
    assert await rd_ok(axil, R_STATUS) == 0
    # DOORBELL+ABORT in one write while idle: ABORT wins, nothing starts, no flags
    await wr_ok(axil, R_CTRL, C_ABORT | C_DOORBELL)
    await ClockCycles(dut.clk, 4)
    assert ab.count == 2
    assert db.count == 0, "doorbell_o pulsed although ABORT wins the combined write"
    assert await rd_ok(axil, R_STATUS) == 0
    # ABORT alone while BUSY: abort pulse, no ERR_BUSY
    await ring_doorbell_accepted(dut, axil)
    await wr_ok(axil, R_CTRL, C_ABORT)
    await ClockCycles(dut.clk, 2)
    assert ab.count == 3
    status = await rd_ok(axil, R_STATUS)
    assert not (status & S_ERR_BUSY), "plain ABORT while BUSY set ERR_BUSY"
    # aborted_set_i -> sticky ABORTED (the FSM reaction)
    dut.aborted_set_i.value = 1
    await RisingEdge(dut.clk)
    dut.aborted_set_i.value = 0
    dut.busy_i.value = 0
    status = await rd_ok(axil, R_STATUS)
    assert status & S_ABORTED, f"STATUS 0x{status:X}: ABORTED clear after aborted_set_i"


@cocotb.test()
async def test_abort_doorbell_while_busy_sets_err_busy(dut):
    """MAS par.8: DOORBELL+ABORT in one write while BUSY -> ABORT acts AND ERR_BUSY (the
    doorbell was ignored). KNOWN RED: grape_regs.sv takes the abort branch exclusively and
    (FIXED 2026-09-05: now sets ERR_BUSY per MAS §8) for the ignored doorbell."""
    axil = await setup(dut)
    await write_good_config(axil)
    await ring_doorbell_accepted(dut, axil)
    ab = PulseCounter(dut.clk, dut.abort_o)
    db = PulseCounter(dut.clk, dut.doorbell_o)
    await wr_ok(axil, R_CTRL, C_ABORT | C_DOORBELL)
    await ClockCycles(dut.clk, 4)
    assert ab.count == 1, "abort_o did not pulse for the combined write while BUSY"
    assert db.count == 0, "doorbell_o pulsed for the combined write while BUSY"
    status = await rd_ok(axil, R_STATUS)
    dut.busy_i.value = 0
    assert status & S_ERR_BUSY, \
        "MAS par.8: DOORBELL+ABORT while BUSY must set ERR_BUSY (doorbell ignored)"


@cocotb.test()
async def test_fp_flags_sticky(dut):
    """fp_flags_set_i pulses set the FP_* sticky bits 15:12; W1C clears (MAS par.4, F13)."""
    axil = await setup(dut)
    dut.fp_flags_set_i.value = 0b1000  # invalid
    await RisingEdge(dut.clk)
    dut.fp_flags_set_i.value = 0b0011  # overflow + underflow
    await RisingEdge(dut.clk)
    dut.fp_flags_set_i.value = 0
    status = await rd_ok(axil, R_STATUS)
    exp = (1 << 12) | (1 << 14) | (1 << 15)
    assert status & 0xF000 == exp, f"STATUS 0x{status:X}: FP flags != 0x{exp:X}"
    await wr_ok(axil, R_STATUS, 0xF000)
    status = await rd_ok(axil, R_STATUS)
    assert status & 0xF000 == 0, "FP flags did not W1C-clear"


@cocotb.test()
async def test_counters(dut):
    """CYCLES_LO/HI and STEPS_DONE mirror the live cycles_i/steps_done_i inputs, 64-bit value
    low word at the lower offset (MAS par.4, ADR-0005)."""
    axil = await setup(dut)
    dut.cycles_i.value = 0x1122334455667788
    dut.steps_done_i.value = 42
    await RisingEdge(dut.clk)
    assert await rd_ok(axil, R_CYCLES_LO) == 0x55667788
    assert await rd_ok(axil, R_CYCLES_HI) == 0x11223344
    assert await rd_ok(axil, R_STEPS_DONE) == 42
    dut.cycles_i.value = 7
    dut.steps_done_i.value = 1
    await RisingEdge(dut.clk)
    assert await rd_ok(axil, R_CYCLES_LO) == 7
    assert await rd_ok(axil, R_CYCLES_HI) == 0
    assert await rd_ok(axil, R_STEPS_DONE) == 1
