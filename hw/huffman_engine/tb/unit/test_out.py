"""huff_out unit TB: skid ordering, tvalid/tready decoupling, flush withdrawal, beat count."""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge


async def start(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.push_i.value = 0
    dut.push_data_i.value = 0
    dut.push_last_i.value = 0
    dut.flush_i.value = 0
    dut.m_sym_tready.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


@cocotb.test()
async def order_backpressure_flush(dut):
    await start(dut)
    rng = random.Random(3)
    sent, got = [], []
    beats = 0

    async def sink():
        nonlocal beats
        from cocotb.triggers import ReadOnly
        while True:
            dut.m_sym_tready.value = rng.random() < 0.5
            await ReadOnly()                 # sample the handshake THIS cycle, pre-edge
            take = int(dut.m_sym_tvalid.value) and int(dut.m_sym_tready.value)
            data = int(dut.m_sym_tdata.value) if take else 0
            await RisingEdge(dut.clk)
            if take:
                got.append(data)
                beats += 1

    cocotb.start_soon(sink())
    from cocotb.triggers import ReadOnly
    for i in range(200):
        while True:
            await ReadOnly()
            full = int(dut.full_o.value)
            await RisingEdge(dut.clk)
            if not full:
                break
            dut.push_i.value = 0
        dut.push_i.value = 1
        dut.push_data_i.value = i
        sent.append(i)
        await RisingEdge(dut.clk)
        dut.push_i.value = 0
        if rng.random() < 0.3:
            await ClockCycles(dut.clk, rng.randrange(1, 3))
    dut.push_i.value = 0
    dut.m_sym_tready.value = 1
    for _ in range(50):
        await RisingEdge(dut.clk)
        if int(dut.empty_o.value):
            break
    assert got == sent, f"order/loss: {len(got)} vs {len(sent)}"
    # flush withdrawal: push two, flush, nothing must emerge
    dut.m_sym_tready.value = 0
    for i in (901, 902):
        dut.push_i.value = 1
        dut.push_data_i.value = i
        await RisingEdge(dut.clk)
    dut.push_i.value = 0
    dut.flush_i.value = 1
    await RisingEdge(dut.clk)
    dut.flush_i.value = 0
    dut.m_sym_tready.value = 1
    await ClockCycles(dut.clk, 5)
    assert int(dut.empty_o.value) == 1 and got == sent, "withdrawn beat leaked"
