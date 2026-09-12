"""Directed corner / error sequences (testplan F-09/F-10/F-13/F-16; MAS §4/§8 error rows).

These drive the error covergroups (cg_errparam, cg_errrt, cg_empty, cg_ctrl, cg_axi) and the
error-flush behaviour. Each sequence asserts its OWN expected sticky bit and behaviour with a
loud `assert` (per testplan); the MtfScoreboard remains the golden oracle for the emitted
L-bytes (it derives the truncation/flush the frozen model has no argument for, §2.1). The
symbol frame (if any) is queued on the cocotbext source by the test before the sequence starts.
"""
from axi_lite_agent import AxiLiteSeqItem
from pyuvm import uvm_sequence

from env import (BYTES_LIMIT, CAPS, CTRL, MAX_RUN, STATUS, ST_ABORTED, ST_BUSY, ST_DONE,
                 ST_EPARAM, ST_ERANK, ST_ERUN, ST_ELIMIT, ST_EUNDER, ST_EBUSY, STICKY_MASK,
                 SYMBOL_LIMIT, SYMBOLS_IN, BYTES_OUT, INIT_CYCLES, USED_BASE, cov,
                 ID_REG, VERSION, IRQ_EN, IRQ_STATUS, CYCLES_LO, CYCLES_HI, DBG_SEL, DBG_DATA)
from smoke import MtfBaseSeq


class CornerBaseSeq(MtfBaseSeq):
    async def clear_used(self):
        for w in range(8):
            await self.wr(USED_BASE + 4 * w, 0)

    async def set_used(self, used_bytes):
        words = [0] * 8
        for b in used_bytes:
            words[b >> 5] |= 1 << (b & 31)
        for w in range(8):
            await self.wr(USED_BASE + 4 * w, words[w])

    async def set_limits(self, symbol_limit=1 << 20, bytes_limit=1 << 20):
        await self.wr(SYMBOL_LIMIT, symbol_limit)
        await self.wr(BYTES_LIMIT, bytes_limit)


class ParamRejectSeq(CornerBaseSeq):
    """F-09: program one bad-parameter config, ring the doorbell, and require the doorbell to be
    REJECTED — sticky ERR_PARAM set, BUSY never rises. Then W1C. `used_bytes=[]` leaves the used
    map cleared (N_USED=0 clause)."""

    def __init__(self, name="param", *, used_bytes=(65,), symbol_limit=1 << 20,
                 bytes_limit=1 << 20):
        super().__init__(name)
        self.used_bytes = list(used_bytes)
        self.symbol_limit = symbol_limit
        self.bytes_limit = bytes_limit

    async def body(self):
        await self.clear_used()
        if self.used_bytes:
            await self.set_used(self.used_bytes)
        await self.set_limits(self.symbol_limit, self.bytes_limit)
        await self.wr(CTRL, 1)                               # doorbell
        st = await self.rd(STATUS)
        for _ in range(8):
            assert not (st & ST_BUSY), \
                f"{self.get_name()}: BUSY rose on a doorbell that must be rejected (0x{st:x})"
            if st & ST_EPARAM:
                break
            st = await self.rd(STATUS)
        assert (st & ST_EPARAM) and not (st & ST_BUSY), \
            f"{self.get_name()}: expected sticky ERR_PARAM, no BUSY; got STATUS=0x{st:x}"
        await self.wr(STATUS, ST_EPARAM)                     # W1C


class RunSeq(CornerBaseSeq):
    """Program config, doorbell, poll to !BUSY, and land on the expected terminal outcome
    (`err_bit`, or DONE when `expect_done`). Optionally read one counter while BUSY (read_busy
    coverage). Reads the counters back, then W1C every sticky bit. The scoreboard independently
    checks the emitted L-bytes, the sticky mirror and the counters."""

    def __init__(self, name="run", *, used_bytes, symbol_limit=1 << 20, bytes_limit=1 << 20,
                 err_bit=None, expect_done=False, max_polls=4000, read_busy=False):
        super().__init__(name)
        self.used_bytes = list(used_bytes)
        self.symbol_limit = symbol_limit
        self.bytes_limit = bytes_limit
        self.err_bit = err_bit
        self.expect_done = expect_done
        self.max_polls = max_polls
        self.read_busy = read_busy
        self.counters = {}

    async def body(self):
        await self.set_used(self.used_bytes)
        await self.set_limits(self.symbol_limit, self.bytes_limit)
        before = await self.rd(STATUS)
        await self.wr(CTRL, 1)                               # doorbell
        busy_seen = False
        did_busy_read = False
        st = before
        for _ in range(self.max_polls):
            st = await self.rd(STATUS)
            if st & ST_BUSY:
                busy_seen = True
                if self.read_busy and not did_busy_read:
                    await self.rd(SYMBOLS_IN)                # counter read while BUSY
                    did_busy_read = True
                continue
            if busy_seen:
                break
        assert busy_seen, f"{self.get_name()}: BUSY never observed (STATUS=0x{st:x})"
        assert not (st & ST_BUSY), f"{self.get_name()}: still BUSY after poll (0x{st:x})"
        if self.expect_done:
            assert st & ST_DONE, f"{self.get_name()}: expected DONE, STATUS=0x{st:x}"
        else:
            assert st & self.err_bit, \
                f"{self.get_name()}: expected sticky 0x{self.err_bit:x}, STATUS=0x{st:x}"
            assert not (st & ST_DONE), \
                f"{self.get_name()}: DONE set on an error invocation (0x{st:x})"
        for name, addr in (("symbols_in", SYMBOLS_IN), ("bytes_out", BYTES_OUT),
                           ("max_run", MAX_RUN), ("init_cycles", INIT_CYCLES)):
            self.counters[name] = await self.rd(addr)
        await self.wr(STATUS, STICKY_MASK)                   # full W1C


class BusyDoorbellSeq(CornerBaseSeq):
    """F-11 ERR_BUSY: doorbell a long run, then doorbell again while BUSY (rejected, sticky
    ERR_BUSY, run unaffected), W1C ERR_BUSY while still BUSY, let it finish DONE."""

    def __init__(self, name="busy", *, used_bytes, env=None):
        super().__init__(name)
        self.used_bytes = list(used_bytes)
        self.env = env

    async def body(self):
        await self.set_used(self.used_bytes)
        await self.set_limits()
        await self.wr(CTRL, 1)                               # doorbell
        st = await self.rd(STATUS)
        assert st & ST_BUSY, f"{self.get_name()}: expected BUSY after doorbell (0x{st:x})"
        await self.wr(CTRL, 1)                               # second doorbell while BUSY
        st = await self.rd(STATUS)
        assert st & ST_EBUSY, f"{self.get_name()}: ERR_BUSY not sticky (0x{st:x})"
        assert st & ST_BUSY, f"{self.get_name()}: run ended inside the busy window (0x{st:x})"
        await self.wr(STATUS, ST_EBUSY)                      # W1C while BUSY (allowed)
        for _ in range(8000):
            st = await self.rd(STATUS)
            if not (st & ST_BUSY):
                break
        assert st & ST_DONE, f"{self.get_name()}: no DONE after busy window (0x{st:x})"
        await self.wr(STATUS, STICKY_MASK)                   # full W1C


class AxiProbeSeq(CornerBaseSeq):
    """F-14 cg_axi: exercise SLVERR (unmapped word), RAZ (reserved reads 0) and WI (reserved
    write ignored, OKAY). CAPS read for cg_caps."""

    async def body(self):
        caps = await self.rd(CAPS)
        assert (caps & 0xFF) in (4, 8, 16), f"{self.get_name()}: CAPS.W {caps & 0xFF}"
        # SLVERR: an unmapped word (>= 0x220). cocotbext raises on a non-OKAY response, so catch.
        for addr in (0x400, 0x800):
            try:
                await self.rd(addr)
            except Exception:                                # SLVERR read
                cov("cg_axi", "rd_slverr")
            try:
                await self.wr(addr, 0xDEAD)
            except Exception:                                # SLVERR write
                cov("cg_axi", "wr_slverr")
        # RAZ/WI: a reserved-but-mapped word (0x018..0x03C region reads 0, writes ignored OKAY)
        raz = await self.rd(0x01C)
        assert raz == 0, f"{self.get_name()}: reserved RAZ read 0x{raz:x} != 0"
        cov("cg_axi", "raz")
        await self.wr(0x01C, 0x1234)                         # WI: ignored, OKAY
        raz2 = await self.rd(0x01C)
        assert raz2 == 0, f"{self.get_name()}: reserved not WI (read 0x{raz2:x})"
        cov("cg_axi", "wi")


class AbortSeq(CornerBaseSeq):
    """F-11 abort: doorbell an invocation, advance `pre_reads` STATUS polls into it, then write
    CTRL=ABORT. Require ABORTED sticky with BUSY dropped (<= 8 cycles), then W1C. The invocation's
    remaining queued symbols are abandoned, so the test resets after."""

    def __init__(self, name="abort", *, used_bytes, pre_reads=0):
        super().__init__(name)
        self.used_bytes = list(used_bytes)
        self.pre_reads = pre_reads

    async def body(self):
        await self.set_used(self.used_bytes)
        await self.set_limits()
        await self.wr(CTRL, 1)                               # doorbell
        for _ in range(self.pre_reads):
            await self.rd(STATUS)
        await self.wr(CTRL, 2)                               # abort
        st = await self.rd(STATUS)
        for _ in range(50):
            if not (st & ST_BUSY):
                break
            st = await self.rd(STATUS)
        assert st & ST_ABORTED, f"{self.get_name()}: no ABORTED after abort (STATUS=0x{st:x})"
        assert not (st & ST_BUSY), f"{self.get_name()}: still BUSY after abort (0x{st:x})"
        assert not (st & ST_DONE), f"{self.get_name()}: DONE set on an aborted run (0x{st:x})"
        await self.wr(STATUS, STICKY_MASK)                   # full W1C


class RegSweepSeq(CornerBaseSeq):
    """F-12/F-04/F-11 register access sweep: read every mapped register (VERSION, CTRL-reads-0,
    IRQ_EN, IRQ_STATUS, counters, SYMBOL_LIMIT, BYTES_LIMIT, CAPS, DBG_SEL, DBG_DATA), exercise the
    IRQ_EN and DBG_SEL writable-while-idle paths, and sweep DBG_SEL->DBG_DATA against the filled
    list (== sorted used bytes)."""

    async def body(self):
        for addr in (ID_REG, VERSION, CTRL, STATUS, IRQ_EN, IRQ_STATUS, CYCLES_LO, CYCLES_HI,
                     SYMBOLS_IN, BYTES_OUT, INIT_CYCLES, MAX_RUN, SYMBOL_LIMIT, BYTES_LIMIT,
                     CAPS, DBG_SEL, DBG_DATA):
            await self.rd(addr)
        await self.wr(IRQ_EN, 0x3F06)                        # enable all IRQ sources
        en = await self.rd(IRQ_EN)
        assert en == 0x3F06, f"{self.get_name()}: IRQ_EN read 0x{en:x} != 0x3F06"
        # DBG sweep: fill the list with a known used map, then DBG_DATA[sel] == sorted used bytes
        used = [65, 70, 90]
        await self.set_used(used)
        await self.set_limits()
        await self.wr(CTRL, 1)                               # doorbell (empty stream -> stays BUSY)
        st = await self.rd(STATUS)
        assert st & ST_BUSY, f"{self.get_name()}: expected BUSY for DBG sweep (0x{st:x})"
        for i, exp in enumerate(sorted(used)):
            await self.wr(DBG_SEL, i)
            got = await self.rd(DBG_DATA)
            assert got == exp, f"{self.get_name()}: DBG_DATA[{i}] 0x{got:x} != 0x{exp:x}"
        await self.wr(CTRL, 2)                               # abort the parked invocation
        for _ in range(50):
            st = await self.rd(STATUS)
            if not (st & ST_BUSY):
                break
        await self.wr(STATUS, STICKY_MASK)


class BusyConfigSeq(CornerBaseSeq):
    """F-11 ERR_BUSY on config writes: doorbell a long run, then write SYMBOL_LIMIT / BYTES_LIMIT /
    USED while BUSY (all ignored, each sets ERR_BUSY), W1C ERR_BUSY while BUSY, let it finish DONE.
    The scoreboard mirror models the discard, so a DUT that latched them would fail at DONE."""

    def __init__(self, name="busycfg", *, used_bytes):
        super().__init__(name)
        self.used_bytes = list(used_bytes)

    async def body(self):
        await self.set_used(self.used_bytes)
        await self.set_limits()
        await self.wr(CTRL, 1)                               # doorbell
        st = await self.rd(STATUS)
        assert st & ST_BUSY, f"{self.get_name()}: expected BUSY after doorbell (0x{st:x})"
        await self.wr(SYMBOL_LIMIT, 5)                       # config writes while BUSY -> ERR_BUSY
        await self.wr(BYTES_LIMIT, 7)
        await self.wr(USED_BASE, 0)
        st = await self.rd(STATUS)
        assert st & ST_EBUSY, f"{self.get_name()}: ERR_BUSY not sticky (0x{st:x})"
        assert st & ST_BUSY, f"{self.get_name()}: run ended inside the busy window (0x{st:x})"
        await self.wr(STATUS, ST_EBUSY)                      # W1C while BUSY
        for _ in range(8000):
            st = await self.rd(STATUS)
            if not (st & ST_BUSY):
                break
        assert st & ST_DONE, f"{self.get_name()}: no DONE after busy-config window (0x{st:x})"
        await self.wr(STATUS, STICKY_MASK)
