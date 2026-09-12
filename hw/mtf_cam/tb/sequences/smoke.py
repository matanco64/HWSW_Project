"""Symbol-programming sequences (testplan §5). All register traffic goes through the AXI agent;
the s_sym symbol stream is queued on the cocotbext source by the test before the sequence starts
(it waits on tready = 0 until the doorbell's INIT completes). The scoreboard checks the L-vector,
the counters and the sticky STATUS from the monitor streams."""
from axi_lite_agent import AxiLiteSeqItem
from pyuvm import uvm_sequence

from env import (BYTES_LIMIT, CAPS, CTRL, DBG_DATA, DBG_SEL, ID_REG, INIT_CYCLES, MAX_RUN,
                 STATUS, ST_BUSY, ST_DONE, SYMBOL_LIMIT, SYMBOLS_IN, BYTES_OUT, USED_BASE)


class MtfBaseSeq(uvm_sequence):
    async def wr(self, addr, data):
        item = AxiLiteSeqItem("wr", kind="write", addr=addr, data=data)
        await self.start_item(item)
        await self.finish_item(item)
        return item

    async def rd(self, addr):
        item = AxiLiteSeqItem("rd", kind="read", addr=addr)
        await self.start_item(item)
        await self.finish_item(item)
        return item.data

    async def program_used(self, used_bytes, *, symbol_limit=1 << 20, bytes_limit=1 << 20):
        """Program the used map (USED[0..7]) and the limits. `used_bytes` is an iterable of
        byte values present in the block."""
        words = [0] * 8
        for b in used_bytes:
            words[b >> 5] |= 1 << (b & 31)
        for w in range(8):
            await self.wr(USED_BASE + 4 * w, words[w])
        await self.wr(SYMBOL_LIMIT, symbol_limit)
        await self.wr(BYTES_LIMIT, bytes_limit)

    async def run_to_done(self, max_polls=2000, outcome_mask=ST_DONE):
        """Doorbell, then poll STATUS until !BUSY with the outcome bit set. Requires BUSY
        observed first (huffman S1/B6 discipline)."""
        before = await self.rd(STATUS)
        await self.wr(CTRL, 1)                              # doorbell
        busy_seen = False
        status = before
        for _ in range(max_polls):
            status = await self.rd(STATUS)
            if status & ST_BUSY:
                busy_seen = True
                continue
            if busy_seen and (status & outcome_mask):
                return status, busy_seen
            if not busy_seen and (status & outcome_mask) and not (before & outcome_mask):
                return status, busy_seen                    # completed between polls
        raise AssertionError(
            f"outcome 0x{outcome_mask:x} not seen within {max_polls} polls "
            f"(busy_seen={busy_seen}, last STATUS 0x{status:x})")


class SmokeSeq(MtfBaseSeq):
    """test_smoke: used map {65,66,67,68} (N_USED=4, alphabet 6); the stream {RUNA,RUNA,MTF2,
    MTF3,MTF2,EOB} is queued by the test. Doorbell, poll to DONE (require BUSY seen), W1C,
    read the counters. Expected L-vector = 65,65,65,66,67,66 (6 B), one full-partial beat."""

    async def body(self):
        ident = await self.rd(ID_REG)
        assert ident == 0x4D544631, f"ID reg 0x{ident:08x} != 'MTF1'"
        caps = await self.rd(CAPS)
        assert (caps & 0xFF) in (4, 8, 16), f"CAPS.W {caps & 0xFF} unexpected"
        await self.program_used([65, 66, 67, 68])
        status, busy_seen = await self.run_to_done()
        assert busy_seen, "BUSY was never observed before DONE"
        await self.wr(STATUS, ST_DONE)                      # W1C
        await self.rd(STATUS)
        await self.rd(SYMBOLS_IN)
        await self.rd(BYTES_OUT)
        await self.rd(MAX_RUN)
        await self.rd(INIT_CYCLES)


class BenchSeq(MtfBaseSeq):
    """test_full_benchmark: program the benchmark used map + limits, doorbell, poll to DONE,
    read every counter. The used map and symbol stream come from mtf_ref.trace_benchmark();
    the scoreboard reconstructs and checks the 336,184-byte L-vector against list_model.expand."""

    def __init__(self, name="bench", used_bytes=None):
        super().__init__(name)
        self.used_bytes = used_bytes
        self.counters = {}

    async def body(self):
        await self.program_used(self.used_bytes)
        await self.run_to_done(max_polls=60000)
        for name, addr in (("cycles_lo", 0x040), ("symbols_in", SYMBOLS_IN),
                           ("bytes_out", BYTES_OUT), ("init_cycles", INIT_CYCLES),
                           ("max_run", MAX_RUN)):
            self.counters[name] = await self.rd(addr)
        # 64-bit CYCLES: read HI too (LO already latched-read above for the model)
        self.counters["cycles_hi"] = await self.rd(0x044)
        await self.wr(STATUS, ST_DONE)                      # W1C
