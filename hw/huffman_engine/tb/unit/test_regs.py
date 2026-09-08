"""Unit tests for huff_regs behind axi_lite_if (MAS docs/mas.md par.4/par.5/par.8 including the
2026-09-08 amendments: per-table 48-word lengths strides, wstrb != F lengths writes ignored
whole; uArch par.3.2 folded counts RMW). DUT: huff_regs_tb_top (TB-only wrapper).

The test plays the core FSM itself: it drives busy_i/done_set_i/aborted_set_i/err_set_i, the
live counters and dbg_data_i, and reads the builder-side lengths_rd/counts_rd ports of the
wrapper (that is how the folded count bins are verified directly).

Run (from the repo root, after `source ./hw/env.sh`):

    make -C hw/huffman_engine sim TOPLEVEL=huff_regs_tb_top MODULE=unit.test_regs \
        VERILOG_SOURCES="rtl/huff_regs.sv rtl/huff_regs_tb_top.sv ../common/rtl/axi_lite_if.sv"
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer
from cocotbext.axi import AxiLiteBus, AxiLiteMaster
from cocotbext.axi.constants import AxiResp

# ---- register map (byte offsets, MAS par.4) ----------------------------------------------------
R_ID           = 0x000
R_VERSION      = 0x004
R_CTRL         = 0x008
R_STATUS       = 0x00C
R_IRQ_EN       = 0x010
R_IRQ_STATUS   = 0x014
R_CYCLES_LO    = 0x040
R_CYCLES_HI    = 0x044
R_SYMBOLS      = 0x048
R_BITS         = 0x04C
R_BUILD_CYCLES = 0x050
R_OVERFETCH    = 0x054
R_MODE         = 0x100
R_START_BIT    = 0x104
R_ALPHABET     = 0x108
R_N_TABLES     = 0x10C
R_SYMBOL_LIMIT = 0x110
R_DBG_SEL      = 0x114
R_DBG_DATA     = 0x118
LEN_BASE       = 0x400

ID_VALUE = 0x48554631  # "HUF1"
MAXLEN = 20

# STATUS bits
S_BUSY          = 1 << 0
S_DONE          = 1 << 1
S_ABORTED       = 1 << 2
S_ERR_BUSY      = 1 << 8
S_ERR_PARAM     = 1 << 9
S_ERR_TABLE     = 1 << 10
S_ERR_NOCODE    = 1 << 11
S_ERR_SELECTOR  = 1 << 12
S_ERR_SYMBOL    = 1 << 13
S_ERR_LIMIT     = 1 << 14
S_ERR_UNDERRUN  = 1 << 15

# CTRL bits
C_DOORBELL = 1 << 0
C_ABORT    = 1 << 1

# DBG_SEL writable-bit mask: [2:0] table, [5:4] kind, [16:8] index
DBG_SEL_MASK = 0x0001FF37


def len_addr(t, w):
    """Byte address of lengths-window word w (0..47) of table t (0..5): per-table 48-word
    strides (MAS amendment 2026-09-08)."""
    return LEN_BASE + 4 * (48 * t + w)


def pack6(fields):
    """Pack up to six 5-bit length fields into one lengths-window word."""
    v = 0
    for i, f in enumerate(fields):
        v |= (f & 0x1F) << (5 * i)
    return v


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
    """Clock, reset, zeroed core-side inputs; returns an AxiLiteMaster."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst_n.value = 0
    dut.busy_i.value = 0
    dut.done_set_i.value = 0
    dut.aborted_set_i.value = 0
    dut.err_set_i.value = 0
    dut.cycles_i.value = 0
    dut.symbols_i.value = 0
    dut.bits_i.value = 0
    dut.build_cycles_i.value = 0
    dut.overfetch_i.value = 0
    dut.dbg_data_i.value = 0
    dut.lengths_rd_addr_i.value = 0
    dut.counts_rd_table_i.value = 0
    dut.counts_rd_len_i.value = 0
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


async def counts_rd(dut, t, l):
    """Combinational builder count-bin read: count[t][l]."""
    dut.counts_rd_table_i.value = t
    dut.counts_rd_len_i.value = l
    await Timer(1, unit="ns")
    return int(dut.counts_rd_data_o.value)


async def lengths_rd(dut, t, sym):
    """Registered (1-cycle) builder lengths read: length of symbol sym in table t."""
    dut.lengths_rd_addr_i.value = (t << 9) | sym
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    return int(dut.lengths_rd_data_o.value)


GOOD_MODE = 0          # bzip2
GOOD_START_BIT = 96
GOOD_ALPHABET = 6
GOOD_N_TABLES = 2
GOOD_LIMIT = 1000
GOOD_LENGTHS = [1, 2, 3, 4, 4, 3]  # table-0 word 0 (Kraft-complete, not that regs checks that)


async def write_good_config(axil):
    await wr_ok(axil, R_MODE, GOOD_MODE)
    await wr_ok(axil, R_START_BIT, GOOD_START_BIT)
    await wr_ok(axil, R_ALPHABET, GOOD_ALPHABET)
    await wr_ok(axil, R_N_TABLES, GOOD_N_TABLES)
    await wr_ok(axil, R_SYMBOL_LIMIT, GOOD_LIMIT)
    await wr_ok(axil, len_addr(0, 0), pack6(GOOD_LENGTHS))
    await wr_ok(axil, len_addr(1, 0), pack6(GOOD_LENGTHS))


async def ring_doorbell_accepted(dut, axil):
    """Ring CTRL.DOORBELL, drive busy_i=1 on the doorbell_o pulse (as the core FSM would),
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
    # ADR-0005: BRESP only after acceptance is visible in STATUS -> the doorbell pulse (and
    # the busy_i the FSM raises on it) must precede the write response.
    assert db.count == 1, f"doorbell_o pulsed {db.count} times before BRESP, expected exactly 1"
    assert busy_task.done() and int(dut.busy_i.value) == 1
    status = await rd_ok(axil, R_STATUS)
    assert status & S_BUSY, f"STATUS 0x{status:X}: BUSY clear right after accepted doorbell"


async def ring_doorbell_rejected(dut, axil, flag, name):
    """Ring CTRL.DOORBELL expecting rejection: no doorbell_o pulse, sticky `flag`, BRESP OKAY,
    not BUSY. Clears the flag afterwards (W1C)."""
    db = PulseCounter(dut.clk, dut.doorbell_o)
    resp = await wr32(axil, R_CTRL, C_DOORBELL)
    assert resp == AxiResp.OKAY, f"{name}: rejected doorbell BRESP {resp!r}, expected OKAY"
    await ClockCycles(dut.clk, 4)
    assert db.count == 0, f"{name}: rejected doorbell still pulsed doorbell_o"
    status = await rd_ok(axil, R_STATUS)
    assert status & flag, f"{name}: STATUS 0x{status:X} missing expected flag 0x{flag:X}"
    assert not (status & S_BUSY), f"{name}: BUSY set after rejected doorbell"
    await wr_ok(axil, R_STATUS, flag)


# ---- tests -------------------------------------------------------------------------------------

@cocotb.test()
async def test_id_version_ctrl_reset(dut):
    """ID/VERSION constants, CTRL/STATUS/IRQ_EN/IRQ_STATUS read 0 after reset (MAS par.3/4)."""
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
    """While idle every RW config register reads back what was written (reserved bits RAZ),
    incl. a wstrb partial write on START_BIT; DBG_SEL fields land on the outputs and DBG_DATA
    reads dbg_data_i through (MAS par.4)."""
    axil = await setup(dut)
    await wr_ok(axil, R_MODE, 0xFFFFFFFF)
    assert await rd_ok(axil, R_MODE) == 1                        # bit 0 only
    await wr_ok(axil, R_MODE, 0)
    await wr_ok(axil, R_START_BIT, 0x89ABCDEF)
    assert await rd_ok(axil, R_START_BIT) == 0x89ABCDEF
    # wstrb partial write: one byte at offset +2 -> byte lane 2 only
    w = await axil.write(R_START_BIT + 2, b"\xAA")
    assert w.resp == AxiResp.OKAY
    assert await rd_ok(axil, R_START_BIT) == 0x89AACDEF
    await wr_ok(axil, R_ALPHABET, 0xFFFFFFFF)
    assert await rd_ok(axil, R_ALPHABET) == 0x1FF                # bits 8:0
    await wr_ok(axil, R_N_TABLES, 0xFFFFFFFF)
    assert await rd_ok(axil, R_N_TABLES) == 0x7                  # bits 2:0
    await wr_ok(axil, R_SYMBOL_LIMIT, 0x12345678)
    assert await rd_ok(axil, R_SYMBOL_LIMIT) == 0x12345678
    # DBG_SEL: [2:0] table, [5:4] kind, [16:8] index, others RAZ; live on the outputs
    await wr_ok(axil, R_DBG_SEL, 0xFFFFFFFF)
    assert await rd_ok(axil, R_DBG_SEL) == DBG_SEL_MASK
    assert int(dut.dbg_table_o.value) == 0x7
    assert int(dut.dbg_kind_o.value) == 0x3
    assert int(dut.dbg_index_o.value) == 0x1FF
    await wr_ok(axil, R_DBG_SEL, (5 << 8) | (1 << 4) | 2)
    assert int(dut.dbg_table_o.value) == 2
    assert int(dut.dbg_kind_o.value) == 1
    assert int(dut.dbg_index_o.value) == 5
    # DBG_DATA is a read-through of dbg_data_i
    dut.dbg_data_i.value = 0xCAFEF00D
    await RisingEdge(dut.clk)
    assert await rd_ok(axil, R_DBG_DATA) == 0xCAFEF00D
    # IRQ_EN: bits 15:1 RW, bit 0 RAZ
    await wr_ok(axil, R_IRQ_EN, 0xFFFFFFFF)
    assert await rd_ok(axil, R_IRQ_EN) == 0xFFFE
    await wr_ok(axil, R_IRQ_EN, 0)


@cocotb.test()
async def test_reserved_and_unmapped(dut):
    """Listed reserved words: write ignored + OKAY, read 0 + OKAY. Unmapped words (0x880 up):
    SLVERR on read AND write (MAS par.4)."""
    axil = await setup(dut)
    for addr in (0x018, 0x03C, 0x058, 0x0FC, 0x11C, 0x3FC):
        resp = await wr32(axil, addr, 0xFFFFFFFF)
        assert resp == AxiResp.OKAY, f"reserved 0x{addr:03X}: BRESP {resp!r}, expected OKAY"
        v, resp = await rd32(axil, addr)
        assert resp == AxiResp.OKAY, f"reserved 0x{addr:03X}: RRESP {resp!r}, expected OKAY"
        assert v == 0, f"reserved 0x{addr:03X} reads 0x{v:08X}, expected 0"
    for addr in (0x880, 0xA00, 0xFFC):
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
async def test_lengths_stride_addressing(dut):
    """Lengths-window words live at LEN_BASE + 4*(48*t + w) (MAS amendment 2026-09-08): full
    round-trip on first/last word of first/last table, no aliasing between tables, bits 31:30
    RAZ; the builder lengths_rd port sees the same fields by (t, sym) (contract)."""
    axil = await setup(dut)
    w00 = pack6([1, 2, 3, 4, 5, 6])
    w10 = pack6([7, 8, 9, 10, 11, 12])
    w547 = pack6([20, 0, 1, 0, 2, 0])
    await wr_ok(axil, len_addr(0, 0), w00 | 0xC0000000)     # bits 31:30 must be dropped
    await wr_ok(axil, len_addr(1, 0), w10)
    await wr_ok(axil, len_addr(5, 47), w547)
    assert await rd_ok(axil, len_addr(0, 0)) == w00
    assert await rd_ok(axil, len_addr(1, 0)) == w10
    assert await rd_ok(axil, len_addr(5, 47)) == w547
    assert await rd_ok(axil, len_addr(0, 47)) == 0          # untouched words read 0
    assert await rd_ok(axil, len_addr(2, 0)) == 0
    # builder lengths_rd: addr {t[2:0], sym[8:0]} -> 5-bit field, 1-cycle
    for s, exp in enumerate([1, 2, 3, 4, 5, 6]):
        assert await lengths_rd(dut, 0, s) == exp, f"lengths_rd(0,{s})"
    for s, exp in enumerate([7, 8, 9, 10, 11, 12]):
        assert await lengths_rd(dut, 1, s) == exp, f"lengths_rd(1,{s})"
    # table 5 word 47 covers symbols 282..287
    for i, exp in enumerate([20, 0, 1, 0, 2, 0]):
        assert await lengths_rd(dut, 5, 282 + i) == exp, f"lengths_rd(5,{282 + i})"


@cocotb.test()
async def test_counts_rmw(dut):
    """Folded count bins (uArch par.3.2): a lengths write increments the 6 new fields' bins of
    the ADDRESS-attributed table; a rewrite decrements the old fields' bins first; repeated
    lengths in one word add up; zero fields touch no bin (verified via the counts_rd port)."""
    axil = await setup(dut)
    await wr_ok(axil, len_addr(2, 0), pack6([3, 3, 2, 0, 1, 3]))
    assert await counts_rd(dut, 2, 1) == 1
    assert await counts_rd(dut, 2, 2) == 1
    assert await counts_rd(dut, 2, 3) == 3
    assert await counts_rd(dut, 2, 4) == 0
    # a second word of the same table accumulates
    await wr_ok(axil, len_addr(2, 1), pack6([3, 0, 0, 0, 0, 20]))
    assert await counts_rd(dut, 2, 3) == 4
    assert await counts_rd(dut, 2, 20) == 1
    # another table's bins are independent
    assert await counts_rd(dut, 3, 3) == 0
    await wr_ok(axil, len_addr(3, 0), pack6([5, 5, 5, 5, 5, 5]))
    assert await counts_rd(dut, 3, 5) == 6
    assert await counts_rd(dut, 2, 5) == 0
    # rewrite decrements the old bins ([3,3,2,0,1,3]) and increments the new ([2,2,0,...])
    await wr_ok(axil, len_addr(2, 0), pack6([2, 2, 0, 0, 0, 0]))
    assert await counts_rd(dut, 2, 1) == 0
    assert await counts_rd(dut, 2, 2) == 2        # 1 old decremented, 2 new added
    assert await counts_rd(dut, 2, 3) == 1        # word 1's single 3 remains
    assert await counts_rd(dut, 2, 20) == 1
    # rewrite to all-zero empties the word's contribution
    await wr_ok(axil, len_addr(2, 1), 0)
    assert await counts_rd(dut, 2, 3) == 0
    assert await counts_rd(dut, 2, 20) == 0


@cocotb.test()
async def test_wstrb_partial_length_write_ignored(dut):
    """A lengths-window write with wstrb != 4'hF is ignored WHOLE (MAS amendment 2026-09-08):
    word unchanged, count bins unchanged, BRESP OKAY."""
    axil = await setup(dut)
    orig = pack6([4, 4, 4, 0, 0, 0])
    await wr_ok(axil, len_addr(1, 2), orig)
    assert await counts_rd(dut, 1, 4) == 3
    # partial write (1, 2 and 3 byte strobes) must change nothing
    w = await axil.write(len_addr(1, 2), b"\xFF")
    assert w.resp == AxiResp.OKAY
    w = await axil.write(len_addr(1, 2), b"\xFF\xFF")
    assert w.resp == AxiResp.OKAY
    w = await axil.write(len_addr(1, 2) + 1, b"\xFF\xFF\xFF")
    assert w.resp == AxiResp.OKAY
    assert await rd_ok(axil, len_addr(1, 2)) == orig, "partial-strobe lengths write landed"
    assert await counts_rd(dut, 1, 4) == 3, "partial-strobe lengths write moved count bins"
    status = await rd_ok(axil, R_STATUS)
    assert status == 0, f"partial-strobe lengths write set STATUS 0x{status:X}"


@cocotb.test()
async def test_doorbell_accept_and_busy_lockout(dut):
    """Good config -> doorbell_o pulse, BRESP only after STATUS shows BUSY, config latched on
    the cfg_* outputs; while BUSY config and lengths writes are ignored with sticky ERR_BUSY,
    config reads return the latched values, DBG_SEL/IRQ_EN/STATUS stay writable without
    ERR_BUSY (MAS par.4/par.5, ADR-0005)."""
    axil = await setup(dut)
    await write_good_config(axil)
    await ring_doorbell_accepted(dut, axil)
    # latched copies visible on the decoder outputs
    assert int(dut.cfg_mode_o.value) == GOOD_MODE
    assert int(dut.cfg_start_bit_o.value) == GOOD_START_BIT
    assert int(dut.cfg_alphabet_o.value) == GOOD_ALPHABET
    assert int(dut.cfg_n_tables_o.value) == GOOD_N_TABLES
    assert int(dut.cfg_symbol_limit_o.value) == GOOD_LIMIT
    # config + lengths writes while BUSY: ignored, OKAY, sticky ERR_BUSY
    for addr, val in ((R_MODE, 1), (R_START_BIT, 7), (R_ALPHABET, 99), (R_N_TABLES, 5),
                      (R_SYMBOL_LIMIT, 1), (len_addr(0, 0), pack6([9, 9, 9, 9, 9, 9]))):
        await wr_ok(axil, addr, val)
    status = await rd_ok(axil, R_STATUS)
    assert status & S_ERR_BUSY, f"STATUS 0x{status:X}: ERR_BUSY clear after config write while BUSY"
    # the ignored lengths write moved neither the stored word nor the bins
    assert await rd_ok(axil, len_addr(0, 0)) == pack6(GOOD_LENGTHS)
    assert await counts_rd(dut, 0, 9) == 0
    # doorbell while BUSY: ignored with ERR_BUSY too (clear first to see it set again)
    await wr_ok(axil, R_STATUS, S_ERR_BUSY)
    status = await rd_ok(axil, R_STATUS)
    assert not (status & S_ERR_BUSY), "ERR_BUSY did not W1C-clear"
    db = PulseCounter(dut.clk, dut.doorbell_o)
    await wr_ok(axil, R_CTRL, C_DOORBELL)
    status = await rd_ok(axil, R_STATUS)
    assert status & S_ERR_BUSY, "doorbell while BUSY did not set ERR_BUSY"
    assert db.count == 0, "doorbell while BUSY pulsed doorbell_o"
    await wr_ok(axil, R_STATUS, S_ERR_BUSY)
    # DBG_SEL and IRQ_EN stay writable while BUSY, no ERR_BUSY
    await wr_ok(axil, R_DBG_SEL, 3)
    await wr_ok(axil, R_IRQ_EN, S_DONE)
    status = await rd_ok(axil, R_STATUS)
    assert not (status & S_ERR_BUSY), "DBG_SEL/IRQ_EN write while BUSY set ERR_BUSY"
    assert int(dut.dbg_table_o.value) == 3
    # config reads while BUSY return the latched values, not the attempted writes
    assert await rd_ok(axil, R_MODE) == GOOD_MODE
    assert await rd_ok(axil, R_START_BIT) == GOOD_START_BIT
    assert await rd_ok(axil, R_ALPHABET) == GOOD_ALPHABET
    assert await rd_ok(axil, R_N_TABLES) == GOOD_N_TABLES
    assert await rd_ok(axil, R_SYMBOL_LIMIT) == GOOD_LIMIT
    dut.busy_i.value = 0
    await RisingEdge(dut.clk)
    # back to idle: pending values (the ignored writes never landed -> still the good config)
    assert await rd_ok(axil, R_ALPHABET) == GOOD_ALPHABET


@cocotb.test()
async def test_err_param_cases(dut):
    """MAS par.4 F9 doorbell rejections: ALPHABET out of range per mode, N_TABLES out of range
    per mode, SYMBOL_LIMIT out of 1..2^27; nothing latched; a later accepted doorbell does not
    clear the sticky bit."""
    axil = await setup(dut)
    await write_good_config(axil)
    # bzip2 ALPHABET < 3 and > 288
    await wr_ok(axil, R_ALPHABET, 2)
    await ring_doorbell_rejected(dut, axil, S_ERR_PARAM, "alphabet=2")
    await wr_ok(axil, R_ALPHABET, 289)
    await ring_doorbell_rejected(dut, axil, S_ERR_PARAM, "alphabet=289")
    await wr_ok(axil, R_ALPHABET, GOOD_ALPHABET)
    # bzip2 N_TABLES 0 and 7
    await wr_ok(axil, R_N_TABLES, 0)
    await ring_doorbell_rejected(dut, axil, S_ERR_PARAM, "n_tables=0")
    await wr_ok(axil, R_N_TABLES, 7)
    await ring_doorbell_rejected(dut, axil, S_ERR_PARAM, "n_tables=7")
    await wr_ok(axil, R_N_TABLES, GOOD_N_TABLES)
    # SYMBOL_LIMIT 0 (the reset value is rejected) and 2^27 + 1
    await wr_ok(axil, R_SYMBOL_LIMIT, 0)
    await ring_doorbell_rejected(dut, axil, S_ERR_PARAM, "symbol_limit=0")
    await wr_ok(axil, R_SYMBOL_LIMIT, (1 << 27) + 1)
    await ring_doorbell_rejected(dut, axil, S_ERR_PARAM, "symbol_limit=2^27+1")
    await wr_ok(axil, R_SYMBOL_LIMIT, 1 << 27)               # boundary value is legal
    # DEFLATE: N_TABLES must be 2, ALPHABET 257..288
    await wr_ok(axil, R_MODE, 1)
    await wr_ok(axil, R_ALPHABET, 257)
    await wr_ok(axil, R_N_TABLES, 1)
    await ring_doorbell_rejected(dut, axil, S_ERR_PARAM, "deflate n_tables=1")
    await wr_ok(axil, R_N_TABLES, 2)
    await wr_ok(axil, R_ALPHABET, 256)
    await ring_doorbell_rejected(dut, axil, S_ERR_PARAM, "deflate alphabet=256")
    # nothing was latched by any rejection
    assert int(dut.cfg_alphabet_o.value) == 0
    assert int(dut.cfg_n_tables_o.value) == 0
    # fix the config; the accepted doorbell must NOT clear a sticky ERR_PARAM
    await wr_ok(axil, R_MODE, GOOD_MODE)
    await wr_ok(axil, R_ALPHABET, GOOD_ALPHABET)
    await wr_ok(axil, R_N_TABLES, GOOD_N_TABLES)
    await wr_ok(axil, R_SYMBOL_LIMIT, 0)
    await wr32(axil, R_CTRL, C_DOORBELL)                     # leave ERR_PARAM sticky
    await ClockCycles(dut.clk, 4)
    await wr_ok(axil, R_SYMBOL_LIMIT, GOOD_LIMIT)
    await ring_doorbell_accepted(dut, axil)
    status = await rd_ok(axil, R_STATUS)
    assert status & S_ERR_PARAM, "accepted doorbell cleared sticky ERR_PARAM"
    dut.busy_i.value = 0


@cocotb.test()
async def test_err_table_invalid_length_at_doorbell(dut):
    """A field > MAXLEN in a used table feeds the per-table invalid bin -> doorbell rejected
    with sticky ERR_TABLE, no BUSY (uArch par.3.2, MAS par.4 bit 10); rewriting the word with
    valid lengths drains the bin and the doorbell is accepted; an invalid length in a table
    beyond N_TABLES is ignored by the check."""
    axil = await setup(dut)
    await write_good_config(axil)
    bad = pack6([21, 2, 3, 4, 4, 3])                         # 21 > MAXLEN = 20
    await wr_ok(axil, len_addr(1, 1), bad)
    await ring_doorbell_rejected(dut, axil, S_ERR_TABLE, "len=21 in used table")
    # rewrite decrements the invalid bin -> accepted now
    await wr_ok(axil, len_addr(1, 1), pack6([20, 2, 3, 4, 4, 3]))
    await ring_doorbell_accepted(dut, axil)
    dut.busy_i.value = 0
    await RisingEdge(dut.clk)
    await wr_ok(axil, R_STATUS, 0xFFFE)
    # invalid length in table 5 (>= N_TABLES = 2): ignored by the doorbell check
    await wr_ok(axil, len_addr(5, 0), pack6([31, 31, 31, 0, 0, 0]))
    await ring_doorbell_accepted(dut, axil)
    status = await rd_ok(axil, R_STATUS)
    assert not (status & S_ERR_TABLE), "invalid length beyond N_TABLES raised ERR_TABLE"
    dut.busy_i.value = 0


@cocotb.test()
async def test_err_table_deflate_bins_16_20(dut):
    """DEFLATE (MAXLEN_eff = 15): a nonzero count in bins 16..20 of a used table -> ERR_TABLE
    at the doorbell; the identical lengths are legal in bzip2 mode (uArch par.3.2 N9)."""
    axil = await setup(dut)
    await wr_ok(axil, R_MODE, 1)
    await wr_ok(axil, R_ALPHABET, 257)
    await wr_ok(axil, R_N_TABLES, 2)
    await wr_ok(axil, R_SYMBOL_LIMIT, GOOD_LIMIT)
    await wr_ok(axil, len_addr(1, 0), pack6([16, 5, 5, 0, 0, 0]))   # distance table, len 16
    await ring_doorbell_rejected(dut, axil, S_ERR_TABLE, "deflate len=16")
    # same lengths accepted in bzip2 mode
    await wr_ok(axil, R_MODE, 0)
    await wr_ok(axil, R_ALPHABET, GOOD_ALPHABET)
    await ring_doorbell_accepted(dut, axil)
    status = await rd_ok(axil, R_STATUS)
    assert not (status & S_ERR_TABLE), "bzip2 mode rejected a legal 16-bit length"
    dut.busy_i.value = 0
    await RisingEdge(dut.clk)
    await wr_ok(axil, R_STATUS, 0xFFFE)
    # back in DEFLATE: fixing the word drains the bin -> accepted
    await wr_ok(axil, R_MODE, 1)
    await wr_ok(axil, R_ALPHABET, 257)
    await wr_ok(axil, len_addr(1, 0), pack6([15, 5, 5, 0, 0, 0]))
    await ring_doorbell_accepted(dut, axil)
    dut.busy_i.value = 0


@cocotb.test()
async def test_w1c_irq_and_err_sets(dut):
    """done_set_i -> sticky DONE, registered irq when IRQ_EN.DONE, W1C clears both;
    err_set_i[6:0] pulses set STATUS bits 15:9 one-hot; IRQ_STATUS = STATUS & IRQ_EN
    (MAS par.4/par.8)."""
    axil = await setup(dut)
    await wr_ok(axil, R_IRQ_EN, S_DONE)
    dut.done_set_i.value = 1
    await RisingEdge(dut.clk)
    dut.done_set_i.value = 0
    await RisingEdge(dut.clk)
    assert int(dut.irq_o.value) == 1, "irq did not rise the cycle after DONE was set"
    status = await rd_ok(axil, R_STATUS)
    assert status & S_DONE, f"STATUS 0x{status:X}: DONE clear after done_set_i"
    assert await rd_ok(axil, R_IRQ_STATUS) == S_DONE
    await wr_ok(axil, R_STATUS, S_DONE)
    status = await rd_ok(axil, R_STATUS)
    assert not (status & S_DONE), "DONE did not W1C-clear"
    await ClockCycles(dut.clk, 2)
    assert int(dut.irq_o.value) == 0, "irq did not fall after the W1C"
    # aborted_set_i -> ABORTED
    dut.aborted_set_i.value = 1
    await RisingEdge(dut.clk)
    dut.aborted_set_i.value = 0
    status = await rd_ok(axil, R_STATUS)
    assert status & S_ABORTED
    await wr_ok(axil, R_STATUS, S_ABORTED)
    # err_set_i[k] sets STATUS bit 9+k (ERR_PARAM..ERR_UNDERRUN); not IRQ-enabled -> irq low
    for k, bit in enumerate((S_ERR_PARAM, S_ERR_TABLE, S_ERR_NOCODE, S_ERR_SELECTOR,
                             S_ERR_SYMBOL, S_ERR_LIMIT, S_ERR_UNDERRUN)):
        dut.err_set_i.value = 1 << k
        await RisingEdge(dut.clk)
        dut.err_set_i.value = 0
        status = await rd_ok(axil, R_STATUS)
        assert status & bit, f"err_set_i[{k}] did not set STATUS bit 0x{bit:X}"
        assert int(dut.irq_o.value) == 0
        await wr_ok(axil, R_STATUS, bit)
    assert await rd_ok(axil, R_STATUS) == 0


@cocotb.test()
async def test_abort_pulses(dut):
    """CTRL.ABORT -> abort_o pulse (idle: no flags); DOORBELL+ABORT in one write: ABORT wins,
    while BUSY it also sets ERR_BUSY for the ignored doorbell; plain ABORT while BUSY sets no
    ERR_BUSY (MAS par.4/par.8)."""
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
    # DOORBELL+ABORT while BUSY: abort acts AND ERR_BUSY for the ignored doorbell
    await wr_ok(axil, R_CTRL, C_ABORT | C_DOORBELL)
    await ClockCycles(dut.clk, 4)
    assert ab.count == 4, "abort_o did not pulse for the combined write while BUSY"
    status = await rd_ok(axil, R_STATUS)
    assert status & S_ERR_BUSY, "DOORBELL+ABORT while BUSY must set ERR_BUSY"
    dut.busy_i.value = 0


@cocotb.test()
async def test_counters_readthrough(dut):
    """CYCLES_LO/HI, SYMBOLS, BITS, BUILD_CYCLES (15:0), OVERFETCH (7:0) mirror the live
    inputs (MAS par.4)."""
    axil = await setup(dut)
    dut.cycles_i.value = 0x1122334455667788
    dut.symbols_i.value = 12345
    dut.bits_i.value = 0xDEADBEEF
    dut.build_cycles_i.value = 0xABCD
    dut.overfetch_i.value = 3
    await RisingEdge(dut.clk)
    assert await rd_ok(axil, R_CYCLES_LO) == 0x55667788
    assert await rd_ok(axil, R_CYCLES_HI) == 0x11223344
    assert await rd_ok(axil, R_SYMBOLS) == 12345
    assert await rd_ok(axil, R_BITS) == 0xDEADBEEF
    assert await rd_ok(axil, R_BUILD_CYCLES) == 0xABCD
    assert await rd_ok(axil, R_OVERFETCH) == 3
    dut.cycles_i.value = 7
    dut.symbols_i.value = 1
    dut.bits_i.value = 2
    dut.build_cycles_i.value = 3
    dut.overfetch_i.value = 4
    await RisingEdge(dut.clk)
    assert await rd_ok(axil, R_CYCLES_LO) == 7
    assert await rd_ok(axil, R_CYCLES_HI) == 0
    assert await rd_ok(axil, R_SYMBOLS) == 1
    assert await rd_ok(axil, R_BITS) == 2
    assert await rd_ok(axil, R_BUILD_CYCLES) == 3
    assert await rd_ok(axil, R_OVERFETCH) == 4
