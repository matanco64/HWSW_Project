"""mtf_cam software driver model (stage 10, hw-integrate).

Register offsets/fields are generated one-for-one from the MAS register map
(`hw/mtf_cam/docs/mas.md` §4) — `check_regmap.py` verifies this driver against
that table AND against the `rtl/mtf_regs.sv` word decode (0 differences
required). The driver API matches the contract in MAS §6.

Transport (MAS §1/§5): control is memory-mapped over a 4 KB AXI4-Lite window;
the symbol input (`s_sym`) and the L-vector output (`m_l`) are AXI4-Stream
channels moved by DMA (or, on chip, chained from `huffman_engine.m_sym`). The
driver therefore programs registers over MMIO and lets the streams flow by DMA;
it never copies the L-vector word-by-word.

Async by design
---------------
Every register access is a coroutine (`await bus.read32/write32`). That single
API runs against two backends:

* `ModelBus` — a standalone functional + cycle model of the register block
  (no RTL, no simulator). It honours the invocation protocol (doorbell → BUSY →
  DONE, W1C, ERR_PARAM/ERR_BUSY), and for an accepted block it computes the
  L-vector and counters through the FROZEN golden predictor
  `golden/list_model.py` (MAS §9 F15) and `CYCLES` from its signed-off cycle
  model. It lets the driver + speedup model run with `asyncio`, no Verilator.
* `SimBackend` — the RTL-cosim adapter: it drives the same register constants
  through the pyuvm `axi_lite_agent` sequencer (`hw/common/tb/axi_lite_agent.py`)
  so the identical driver runs against the DUT in cocotb. The symbols are
  queued on the `s_sym` cocotbext source by the test; the L-vector is captured
  on the `m_l` sink and checked by the scoreboard.
"""
from __future__ import annotations

# --- Register map (byte offsets), generated from MAS §4 -------------------
ID           = 0x000   # RO  ASCII 'MTF1'
VERSION      = 0x004   # RO  git short SHA
CTRL         = 0x008   # WP  bit0 DOORBELL, bit1 ABORT
STATUS       = 0x00C   # RO/W1C
IRQ_EN       = 0x010   # RW  mask over the sticky bits {13:8, 2:1}
IRQ_STATUS   = 0x014   # RO  STATUS & IRQ_EN
CYCLES_LO    = 0x040   # RO  busy cycles low word
CYCLES_HI    = 0x044   # RO  busy cycles high word
SYMBOLS_IN   = 0x048   # RO  s_sym beats accepted (incl. EOB)
BYTES_OUT    = 0x04C   # RO  L-vector bytes handshaken on m_l
INIT_CYCLES  = 0x050   # RO  list-init fill cycles of the last invocation
MAX_RUN      = 0x054   # RO  largest run item (bytes) enqueued this invocation
SYMBOL_LIMIT = 0x100   # RW  1..2^27 (driver default 2^20)
BYTES_LIMIT  = 0x104   # RW  1..2^30 (driver default 2^20)
CAPS         = 0x108   # RO  {N_LIST, D, W} build parameters
DBG_SEL      = 0x10C   # RW  rank whose current list byte DBG_DATA returns
DBG_DATA     = 0x110   # RO  list byte at rank DBG_SEL
USED_BASE    = 0x200   # RW  USED[w] window, stride 0x04, w = 0..7
USED_STRIDE  = 0x004

ID_VALUE = 0x4D544631  # ASCII 'MTF1'

# CTRL bit positions (WP)
CTRL_DOORBELL = 1 << 0
CTRL_ABORT    = 1 << 1

# STATUS bit positions (MAS §4)
ST_BUSY      = 1 << 0
ST_DONE      = 1 << 1
ST_ABORTED   = 1 << 2
ST_ERR_BUSY  = 1 << 8
ST_ERR_PARAM = 1 << 9
ST_ERR_RANK  = 1 << 10
ST_ERR_RUN   = 1 << 11
ST_ERR_LIMIT = 1 << 12
ST_ERR_UNDER = 1 << 13
ST_STICKY_MASK = 0x3F06            # DONE|ABORTED + err bits 13:8 (W1C set); bit0 = live BUSY
ST_ERR_MASK    = 0x3F00            # all six error bits (8..13)

# doorbell-time / run limits (mirror mtf_regs.sv + mtf_run)
SYM_MAX = 1 << 27                  # SYMBOL_LIMIT ceiling
BYT_MAX = 1 << 30                  # BYTES_LIMIT  ceiling
RUN_MAX = 1 << 20                  # run overflow threshold
DEFAULT_SYMBOL_LIMIT = 1 << 20
DEFAULT_BYTES_LIMIT  = 1 << 20


def used_words(used_map):
    """Turn a used-map spec into the 8 USED[w] register words.

    `used_map` may be 256 bools/ints, a 32-byte bitmap, or an iterable of the
    byte VALUES present in the block. Returns [word0..word7]; N_USED = popcount.
    """
    present = _used_present(used_map)
    words = [0] * 8
    for b in range(256):
        if present[b]:
            words[b >> 5] |= 1 << (b & 31)
    return words


def _used_present(used_map):
    present = [False] * 256
    seq = list(used_map)
    if len(seq) == 256 and all(v in (0, 1, True, False) for v in seq):
        for b, v in enumerate(seq):
            present[b] = bool(v)
    elif len(seq) == 32 and all(isinstance(v, int) and 0 <= v <= 255 for v in seq):
        for w, byte in enumerate(seq):       # 32-byte little-endian bitmap
            for bit in range(8):
                if byte & (1 << bit):
                    present[8 * w + bit] = True
    else:                                    # iterable of present byte values
        for v in seq:
            present[int(v) & 0xFF] = True
    return present


def n_used_of(used_map):
    return sum(_used_present(used_map))


class MMIO:
    """Abstract 32-bit MMIO bus (async). Backends implement read32/write32."""
    async def read32(self, addr: int) -> int:                 # pragma: no cover
        raise NotImplementedError

    async def write32(self, addr: int, value: int) -> None:   # pragma: no cover
        raise NotImplementedError

    def load_symbols(self, symbols, used_map, alphabet) -> None:
        """Side channel for the s_sym stream. The RTL/sim backend ignores it
        (the symbols are queued on the cocotbext source); the ModelBus records
        them so it can compute the invocation outcome at the doorbell."""
        return None


class AccelDriver:
    """Shared control-plane base (ADR-0005). `bus` provides async read32/write32."""

    def __init__(self, bus: MMIO, base: int = 0):
        self.bus = bus
        self.base = base

    async def _rd(self, off: int) -> int:
        return await self.bus.read32(self.base + off)

    async def _wr(self, off: int, val: int) -> None:
        await self.bus.write32(self.base + off, val & 0xFFFFFFFF)

    async def status(self) -> int:
        return await self._rd(STATUS)

    async def start(self) -> bool:
        """Doorbell (CTRL.DOORBELL). Clears the sticky bits first (a doorbell
        clears none in HW, MAS §8) so a subsequent DONE is unambiguous. Returns
        False if the doorbell was rejected with ERR_PARAM (F9)."""
        await self._wr(STATUS, ST_STICKY_MASK)              # W1C stale DONE/errors
        await self._wr(CTRL, CTRL_DOORBELL)
        s = await self.status()
        if s & ST_ERR_PARAM:
            return False
        return True

    async def abort(self) -> None:
        await self._wr(CTRL, CTRL_ABORT)

    async def wait_done(self, max_polls: int) -> int:
        """Poll STATUS until the invocation completes (DONE/ABORTED with BUSY
        low). Raises on a runtime/param/busy error or on timeout; ABORTED
        returns normally. `start()` clears the sticky bits first, so a DONE seen
        here is this invocation's (it may complete between polls for a tiny
        block, so BUSY-seen is not required — the pre-doorbell W1C guards against
        a stale DONE)."""
        s = 0
        for _ in range(max_polls):
            s = await self.status()
            if s & ST_BUSY:
                continue
            if s & ST_ERR_MASK:
                raise RuntimeError(f"invocation error: STATUS=0x{s:04x}")
            if s & (ST_DONE | ST_ABORTED):
                return s
        raise TimeoutError(f"wait_done: no DONE after {max_polls} polls (STATUS=0x{s:04x})")

    async def clear(self, bits: int = ST_STICKY_MASK) -> None:
        await self._wr(STATUS, bits)

    async def read_counters(self) -> dict:
        lo, hi = await self._rd(CYCLES_LO), await self._rd(CYCLES_HI)
        return {
            "cycles": (hi << 32) | lo,
            "symbols_in": await self._rd(SYMBOLS_IN),
            "bytes_out": await self._rd(BYTES_OUT),
            "init_cycles": await self._rd(INIT_CYCLES),
            "max_run": await self._rd(MAX_RUN),
        }


class MtfDriver(AccelDriver):
    """mtf_cam driver (MAS §6)."""

    async def caps(self) -> dict:
        c = await self._rd(CAPS)
        return {"W": c & 0xFF, "D": (c >> 8) & 0xFF, "N_LIST": (c >> 16) & 0x1FF}

    async def configure(self, used_map, symbol_limit: int = DEFAULT_SYMBOL_LIMIT,
                        bytes_limit: int = DEFAULT_BYTES_LIMIT) -> None:
        """Write the used map (USED[0..7]) and the limits. Validates N_USED >= 1
        client-side (the doorbell would otherwise reject with ERR_PARAM)."""
        if n_used_of(used_map) < 1:
            raise ValueError("configure: N_USED must be >= 1 (F9 ERR_PARAM otherwise)")
        for w, word in enumerate(used_words(used_map)):
            await self._wr(USED_BASE + w * USED_STRIDE, word)
        await self._wr(SYMBOL_LIMIT, symbol_limit)
        await self._wr(BYTES_LIMIT, bytes_limit)

    async def read_list(self, n_used: int) -> list:
        """Debug read-back of the list (ranks 0..n_used-1) via DBG_SEL/DBG_DATA."""
        out = []
        for r in range(n_used):
            await self._wr(DBG_SEL, r)
            out.append(await self._rd(DBG_DATA) & 0xFF)
        return out

    async def load_used_map(self, used_map) -> None:
        for w, word in enumerate(used_words(used_map)):
            await self._wr(USED_BASE + w * USED_STRIDE, word)

    async def expand_block(self, symbols, used_map,
                          symbol_limit: int = DEFAULT_SYMBOL_LIMIT,
                          bytes_limit: int = DEFAULT_BYTES_LIMIT,
                          max_polls: int = 400000) -> dict:
        """Standalone one-block invocation: configure, present the symbol stream,
        doorbell, wait for DONE, read the counters, W1C. `symbols` are raw values
        (0/1 runs, 2..N_USED MTF, N_USED+1 EOB); the ModelBus/replay source turns
        them into ADR-0006 beats. Returns {l_bytes, bytes_out, symbols_in,
        max_run, cycles, ...}. Raises on ERR_PARAM/ERR_*; ABORTED returns."""
        alphabet = n_used_of(used_map) + 2
        await self.configure(used_map, symbol_limit, bytes_limit)
        self.bus.load_symbols(list(symbols), used_map, alphabet)
        if not await self.start():
            raise RuntimeError("doorbell rejected (ERR_PARAM)")
        s = await self.wait_done(max_polls)
        c = await self.read_counters()
        c["status"] = s
        c["l_bytes"] = getattr(self.bus, "last_l_bytes", None)
        await self.clear()
        return c


# =============================================================================
# ModelBus — standalone functional + cycle model of the register block.
# =============================================================================
class ModelBus(MMIO):
    """No RTL, no simulator. Honours the MAS §5 invocation protocol (doorbell →
    BUSY → DONE, W1C, ERR_PARAM/ERR_BUSY) and computes the L-vector, counters
    and CYCLES for an accepted block through the frozen golden predictor
    `golden/list_model.py`. Runtime errors (ERR_RANK/RUN/LIMIT/UNDERRUN) are the
    RTL + scoreboard's oracle (test_full_benchmark / test_random); like grape's
    ModelBus this model covers the clean-completion and ERR_PARAM/ERR_BUSY paths.
    """

    def __init__(self, W: int = 8, D: int = 8, N_LIST: int = 256):
        self.mem = {}
        self.busy = False
        self.sticky = 0                    # bits per ST_* (13:1)
        self.cycles = 0
        self.symbols_in = 0
        self.bytes_out = 0
        self.init_cycles = 0
        self.max_run = 0
        self.W, self.D, self.N_LIST = W, D, N_LIST
        self._pending = None               # (symbols, used_map, alphabet)
        self.last_l_bytes = None
        self._predictor = None
        self._busy_polls = 0               # STATUS reads that report BUSY before completing
        self._term = 0                     # terminal sticky bits latched at completion (DONE)

    def _predict(self):
        if self._predictor is None:
            import list_model            # golden/list_model.py (on sys.path)
            self._predictor = list_model
        return self._predictor

    def load_symbols(self, symbols, used_map, alphabet):
        self._pending = (list(symbols), used_map, alphabet)

    def _word(self, addr):
        return self.mem.get(addr, 0)

    async def read32(self, addr: int) -> int:
        if addr == ID:
            return ID_VALUE
        if addr == CAPS:
            return (self.N_LIST << 16) | (self.D << 8) | self.W
        if addr == STATUS:
            val = (self.sticky & ST_STICKY_MASK) | (1 if self.busy else 0)
            if self.busy:                                # model a short BUSY window, then complete
                self._busy_polls -= 1
                if self._busy_polls <= 0:
                    self.busy = False
                    self.sticky |= self._term
            return val
        if addr == IRQ_STATUS:
            return self.sticky & self._word(IRQ_EN)
        if addr == CYCLES_LO:
            return self.cycles & 0xFFFFFFFF
        if addr == CYCLES_HI:
            return (self.cycles >> 32) & 0xFFFFFFFF
        if addr == SYMBOLS_IN:
            return self.symbols_in
        if addr == BYTES_OUT:
            return self.bytes_out
        if addr == INIT_CYCLES:
            return self.init_cycles
        if addr == MAX_RUN:
            return self.max_run
        return self._word(addr)

    async def write32(self, addr: int, value: int) -> None:
        value &= 0xFFFFFFFF
        if addr == CTRL:
            if value & CTRL_ABORT:                       # ABORT wins over DOORBELL
                if self.busy:
                    self.sticky |= ST_ABORTED
                    self.busy = False
                return
            if value & CTRL_DOORBELL:
                if self.busy:
                    self.sticky |= ST_ERR_BUSY           # F11
                else:
                    self._doorbell()
            return
        if addr == STATUS:                               # W1C
            self.sticky &= ~(value & ST_STICKY_MASK)
            return
        if addr in (IRQ_EN, DBG_SEL):                    # writable while BUSY
            self.mem[addr] = value
            return
        if self.busy:                                    # config write while BUSY -> ERR_BUSY
            self.sticky |= ST_ERR_BUSY
            return
        self.mem[addr] = value

    def _used_present(self):
        present = [False] * 256
        for w in range(8):
            word = self._word(USED_BASE + w * USED_STRIDE)
            for b in range(32):
                if word & (1 << b):
                    present[32 * w + b] = True
        return present

    def _doorbell(self):
        present = self._used_present()
        n_used = sum(present)
        sym_lim = self._word(SYMBOL_LIMIT)
        byt_lim = self._word(BYTES_LIMIT)
        if (n_used == 0 or n_used > self.N_LIST
                or sym_lim == 0 or sym_lim > SYM_MAX
                or byt_lim == 0 or byt_lim > BYT_MAX):
            self.sticky |= ST_ERR_PARAM                  # F9, no BUSY, no invocation
            return
        # accepted: compute the outcome through the frozen golden predictor
        symbols, used_map, alphabet = (self._pending or ([], present, n_used + 2))
        used = present
        pred = self._predict()
        l_bytes, events = pred.expand(symbols, used, alphabet)
        self.last_l_bytes = bytes(l_bytes)
        self.bytes_out = len(l_bytes)
        self.symbols_in = len(symbols)
        self.max_run = max((ev[1] for ev in events if ev[0] == "run"), default=0)
        self.init_cycles = n_used
        self.cycles = pred.cycles(symbols, used, alphabet, W=self.W, D=self.D)
        # open the invocation: report BUSY for a couple of STATUS polls, then latch DONE
        self.busy = True
        self._busy_polls = 2
        self._term = ST_DONE


# =============================================================================
# SimBackend — RTL-cosim adapter over the pyuvm axi_lite_agent (cocotb only).
# =============================================================================
class SimBackend(MMIO):
    """Drives the identical register constants through the DUT in cocotb.

    Construct with a running `uvm_sequence` (an `MtfBaseSeq`, or anything with
    async `wr(addr, data)` / `rd(addr)` that go through the AXI-Lite agent's
    sequencer). The symbol stream is queued on the cocotbext `s_sym` source by
    the test before the driver rings the doorbell; the L-vector is captured on
    the `m_l` sink and checked by the scoreboard, so `expand_block` returns
    BYTES_OUT while the byte-exactness is asserted by the env scoreboard.
    """

    def __init__(self, seq):
        self.seq = seq                     # provides async wr(addr, data) / rd(addr)
        self.last_l_bytes = None

    async def read32(self, addr: int) -> int:
        return await self.seq.rd(addr)

    async def write32(self, addr: int, value: int) -> None:
        await self.seq.wr(addr, value & 0xFFFFFFFF)
