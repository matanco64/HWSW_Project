"""Full-chip smoke (RTL-stage integration check, per the grape lesson: the first whole-module
sim catches what unit TBs cannot): one tiny bzip2 table, hand-packed stream, decode to EOB,
compare the m_sym beats and DONE/counters against hand-computed expectations."""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge

from cocotbext.axi import AxiLiteBus, AxiLiteMaster

CTRL, STATUS = 0x008, 0x00C
CYCLES_LO, SYMBOLS, BITS = 0x040, 0x048, 0x04C
MODE, START_BIT, ALPHABET, N_TABLES, SYMBOL_LIMIT = 0x100, 0x104, 0x108, 0x10C, 0x110
LEN_BASE = 0x400
ST_BUSY, ST_DONE = 1, 2


async def wr32(axil, addr, val):
    r = await axil.write(addr, val.to_bytes(4, "little"))
    return r.resp


async def rd32(axil, addr):
    r = await axil.read(addr, 4)
    return int.from_bytes(r.data, "little")


@cocotb.test()
async def smoke_decode(dut):
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    dut.rst_n.value = 0
    dut.s_axis_bits_tvalid.value = 0
    dut.s_axis_sel_tvalid.value = 0
    dut.m_axis_sym_tready.value = 1
    await ClockCycles(dut.clk, 4)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)
    axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "s_axi"), dut.clk, dut.rst_n,
                         reset_active_level=False)

    # table: lengths [1,2,3,3] -> codes 0, 10, 110, 111 (sym3 = EOB, alphabet-1)
    assert await rd32(axil, 0x000) == 0x48554631      # ID 'HUF1'
    await wr32(axil, MODE, 0)
    await wr32(axil, START_BIT, 0)
    await wr32(axil, ALPHABET, 4)
    await wr32(axil, N_TABLES, 1)
    await wr32(axil, SYMBOL_LIMIT, 1000)
    await wr32(axil, LEN_BASE, (3 << 15) | (3 << 10) | (2 << 5) | 1)  # word 0, fields 0..3

    await wr32(axil, CTRL, 1)                          # doorbell
    st = await rd32(axil, STATUS)
    assert st & ST_BUSY, f"not busy after doorbell: {st:#x}"

    # stream: s0 s1 s2 s0 EOB = 0 10 110 0 111 -> 0101 1001 11 pad -> 0x59, 0xC0
    dut.s_axis_bits_tdata.value = 0x0000C059
    dut.s_axis_bits_tkeep.value = 0x3
    dut.s_axis_bits_tlast.value = 1
    dut.s_axis_bits_tvalid.value = 1
    # first selector (table 0), TLAST
    dut.s_axis_sel_tdata.value = 0
    dut.s_axis_sel_tlast.value = 1
    dut.s_axis_sel_tvalid.value = 1

    got = []
    for _ in range(400):
        await ReadOnly()
        if int(dut.s_axis_bits_tready.value) and int(dut.s_axis_bits_tvalid.value):
            beats_taken = True
        if int(dut.m_axis_sym_tvalid.value) and int(dut.m_axis_sym_tready.value):
            got.append((int(dut.m_axis_sym_tdata.value), int(dut.m_axis_sym_tlast.value)))
        await RisingEdge(dut.clk)
        if int(dut.s_axis_bits_tready.value) == 0 and len(got) >= 5:
            pass
        if got and got[-1][1] == 1:
            break
    dut.s_axis_bits_tvalid.value = 0
    dut.s_axis_sel_tvalid.value = 0

    exp = [(0, 0), (1, 0), (2, 0), (0, 0), ((3 << 9) | 3, 1)]  # TYPE0 x4, TYPE3 EOB val 3
    assert got == exp, f"beats {got} != {exp}"

    for _ in range(50):
        st = await rd32(axil, STATUS)
        if st & ST_DONE:
            break
    assert st & ST_DONE, f"no DONE: {st:#x}"
    assert not (st & ST_BUSY)
    assert await rd32(axil, SYMBOLS) == 5
    assert await rd32(axil, BITS) == 10                # 1+2+3+1+3 code bits exactly
    cyc = await rd32(axil, CYCLES_LO)
    assert 0 < cyc < 1000
    dut._log.info(f"smoke: 5 beats, BITS=10, CYCLES={cyc}")
