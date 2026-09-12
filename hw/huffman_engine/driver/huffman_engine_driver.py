"""huffman_engine software driver model (stage 10, hw-integrate).

Register offsets/fields are generated one-for-one from the MAS register map
(`hw/huffman_engine/docs/mas.md` §4) — `check_regmap.py` verifies this driver
against that table (0 differences required). The driver API matches the
contract in MAS §6.

Backends
--------
`MMIO` is the abstract 32-bit bus: `read32(addr)` / `write32(addr, v)`.
`ModelBus` is a standalone functional + cycle model of the register block (no
RTL): it honours the invocation protocol (doorbell → BUSY → DONE, W1C,
ERR_PARAM/ERR_BUSY) and reports CYCLES/SYMBOLS/BITS from the signed-off
cycle model of `docs/decode_model.py` (uArch §7, ADR-0008) — the same K1 =
1.0068 measured at sign-off. The bit-exact symbol values live in the frozen
golden model (`golden/canonical_model.py`, MAS §9 F15) + RTL; wiring this
driver to the pyuvm `axi_lite_agent` + `AxiStream` source/sink (SimBackend) is
the RTL-cosim extension and reuses the identical register constants below.

The `cycle_model()` here is a self-contained copy of `docs/decode_model.py`
`simulate()`; `test_driver.py` asserts the two agree bit-for-bit on a sample so
the copy can never drift from the signed-off source of truth.
"""
from __future__ import annotations

# --- Register map (byte offsets), generated from MAS §4 -------------------
ID           = 0x000   # RO  ASCII 'HUF1'
VERSION      = 0x004   # RO  git short SHA
CTRL         = 0x008   # WP  bit0 DOORBELL, bit1 ABORT
STATUS       = 0x00C   # RO/W1C
IRQ_EN       = 0x010   # RW  mask over STATUS 15:1
IRQ_STATUS   = 0x014   # RO  STATUS & IRQ_EN
CYCLES_LO    = 0x040   # RO  busy cycles low word
CYCLES_HI    = 0x044   # RO  busy cycles high word
SYMBOLS      = 0x048   # RO  m_sym beats handshaken (live)
BITS         = 0x04C   # RO  bits consumed since START_BIT (live)
BUILD_CYCLES = 0x050   # RO  longest single table build (K2)
OVERFETCH    = 0x054   # RO  s_bits beats beyond last consumed bit
MODE         = 0x100   # RW  0 = bzip2, 1 = DEFLATE
START_BIT    = 0x104   # RW  first code bit within the s_bits buffer
ALPHABET     = 0x108   # RW  symbols per table
N_TABLES     = 0x10C   # RW  bzip2 1..6; DEFLATE must be 2
SYMBOL_LIMIT = 0x110   # RW  1..2^27
DBG_SEL      = 0x114   # RW  table/kind/index selector
DBG_DATA     = 0x118   # RO  selected built-table entry
LEN_BASE     = 0x400   # RW  length window, word w at LEN_BASE + 4*w
LEN_STRIDE   = 0x004
LEN_TABLE_STRIDE = 48  # words per table (MAS amendment 2026-09-08): table t at 48*t

ID_VALUE = 0x48554631  # 'HUF1'

# Architectural parameters (MAS §2)
ALPHABET_MAX = 288
MAXLEN       = 20
N_TABLES_MAX = 6
SYMBOL_LIMIT_MAX = 1 << 27
SYMBOL_LIMIT_DEFAULT = 1 << 20   # PRD default (MAS 0x110)

# CTRL bit positions (WP)
CTRL_DOORBELL = 1 << 0
CTRL_ABORT    = 1 << 1

# STATUS bit positions (MAS §4 0x00C)
ST_BUSY         = 1 << 0
ST_DONE         = 1 << 1
ST_ABORTED      = 1 << 2
ST_ERR_BUSY     = 1 << 8
ST_ERR_PARAM    = 1 << 9
ST_ERR_TABLE    = 1 << 10
ST_ERR_NOCODE   = 1 << 11
ST_ERR_SELECTOR = 1 << 12
ST_ERR_SYMBOL   = 1 << 13
ST_ERR_LIMIT    = 1 << 14
ST_ERR_UNDERRUN = 1 << 15
ST_ERR_MASK     = 0xFF00        # bits 15:8 (all sticky error/status W1C bits)
ST_STICKY_MASK  = 0xFFFE        # bits 15:1 (W1C set; clear() default, MAS §6)


# --- signed-off cycle model (copy of docs/decode_model.py::simulate) ------
def cycle_model(lengths, alphabet, n_tables, start_bit=0,
                beat_every=1, out_stall_every=0):
    """Cycle-accurate decode model (uArch §7, ADR-0008). Copy of
    docs/decode_model.py::simulate; test_driver.py asserts equivalence.
    Returns {cycles, build, skip, refill_stall, out_stall, symbols}."""
    BUF_BITS, FIFO_BEATS, REFILL = 64, 2, 32
    build = n_tables * (alphabet + MAXLEN)
    skip = start_bit // 32
    cycles = max(build, skip * beat_every)
    occ = 0
    fifo = 0
    next_beat = skip * beat_every + 1
    refill_stall = 0
    out_stall = 0
    total_bits = sum(lengths)
    consumed = 0

    def tick(k):
        nonlocal fifo, next_beat
        while next_beat <= k and fifo < FIFO_BEATS:
            fifo += 1
            next_beat += beat_every

    def refill():
        nonlocal occ, fifo
        if fifo > 0 and occ <= BUF_BITS - REFILL:
            occ = min(BUF_BITS, occ + REFILL)
            fifo -= 1

    for n, ln in enumerate(lengths):
        if out_stall_every and n % out_stall_every == 0:
            cycles += 1
            out_stall += 1
            tick(cycles)
            refill()
        tail = (total_bits - consumed) <= occ and (total_bits - consumed) < MAXLEN
        while occ < MAXLEN and not tail:
            cycles += 1
            refill_stall += 1
            tick(cycles)
            refill()
            tail = (total_bits - consumed) <= occ and (total_bits - consumed) < MAXLEN
        occ -= ln
        consumed += ln
        cycles += 1
        tick(cycles)
        refill()
    cycles += 2  # backend drain + EOB TLAST beat
    return {"cycles": cycles, "build": build, "skip": skip,
            "refill_stall": refill_stall, "out_stall": out_stall,
            "symbols": len(lengths)}


class MMIO:
    """Abstract 32-bit MMIO bus."""
    def read32(self, addr: int) -> int:                # pragma: no cover
        raise NotImplementedError
    def write32(self, addr: int, value: int) -> None:  # pragma: no cover
        raise NotImplementedError


class AccelDriver:
    """Shared base (ADR-0005 / grape MAS §6). `bus` provides read32/write32."""
    def __init__(self, bus: MMIO, base: int = 0):
        self.bus = bus
        self.base = base

    def _rd(self, off: int) -> int:
        return self.bus.read32(self.base + off)

    def _wr(self, off: int, val: int) -> None:
        self.bus.write32(self.base + off, val & 0xFFFFFFFF)

    def status(self) -> int:
        return self._rd(STATUS)

    def start(self) -> bool:
        """Doorbell. Returns False if rejected at the doorbell (ERR_PARAM/ERR_TABLE)."""
        self._wr(CTRL, CTRL_DOORBELL)
        s = self.status()
        return not (s & (ST_ERR_PARAM | ST_ERR_TABLE))

    def abort(self) -> None:
        self._wr(CTRL, CTRL_ABORT)

    def clear(self, bits: int = ST_STICKY_MASK) -> None:
        self._wr(STATUS, bits)

    def counters(self) -> dict:
        lo, hi = self._rd(CYCLES_LO), self._rd(CYCLES_HI)
        return {"cycles": (hi << 32) | lo,
                "symbols": self._rd(SYMBOLS), "bits": self._rd(BITS),
                "build_cycles": self._rd(BUILD_CYCLES),
                "overfetch": self._rd(OVERFETCH)}


class HuffmanDriver(AccelDriver):
    """MAS §6 API. Length window packs 6 x 5-bit fields per word, per-table
    48-word stride (MAS amendment 2026-09-08)."""
    MODE_BZIP2, MODE_DEFLATE = 0, 1

    def configure(self, mode, start_bit, alphabet, n_tables,
                  symbol_limit=SYMBOL_LIMIT_DEFAULT) -> None:
        self._mode, self._alphabet, self._n_tables = mode, alphabet, n_tables
        self._start_bit = start_bit
        self._wr(MODE, mode)
        self._wr(START_BIT, start_bit)
        self._wr(ALPHABET, alphabet)
        self._wr(N_TABLES, n_tables)
        self._wr(SYMBOL_LIMIT, symbol_limit)

    def load_lengths(self, tables, validate=True) -> None:
        """tables: list[list[int]] per-table symbol code lengths. Packs 6 per
        word, per-table 48-word stride; trailing fields (>= ALPHABET) zeroed on
        shrink (MAS §3.2 driver-zeroing contract). validate=True checks
        0..MAXLEN of the mode (corner tests pass validate=False to inject
        ERR_TABLE)."""
        if not hasattr(self, "_alphabet"):
            raise RuntimeError("load_lengths before configure()")
        maxlen = 15 if self._mode == self.MODE_DEFLATE else MAXLEN
        for t, lengths in enumerate(tables):
            if validate:
                for s, ln in enumerate(lengths):
                    if not (0 <= ln <= maxlen):
                        raise ValueError(f"table {t} symbol {s}: length {ln} > MAXLEN {maxlen}")
            # 48 words per table, 6 fields per word -> 288 symbol slots
            for wi in range(LEN_TABLE_STRIDE):
                word = 0
                for f in range(6):
                    s = wi * 6 + f
                    ln = lengths[s] if s < len(lengths) else 0
                    word |= (ln & 0x1F) << (5 * f)
                self._wr(LEN_BASE + (t * LEN_TABLE_STRIDE + wi) * LEN_STRIDE, word)

    def wait_done(self, max_polls: int, raise_errors: bool = True) -> int:
        """Return STATUS when BUSY = 0. Raises on ERR_PARAM/ERR_BUSY and, unless
        raise_errors=False, on the run-time ERR_* / ERR_TABLE (MAS §6)."""
        for _ in range(max_polls):
            s = self.status()
            if s & (ST_ERR_PARAM | ST_ERR_BUSY):
                raise RuntimeError(f"invocation error: STATUS=0x{s:04x}")
            if not (s & ST_BUSY):
                if raise_errors and (s & (ST_ERR_MASK & ~ST_ERR_BUSY & ~ST_ERR_PARAM)):
                    raise RuntimeError(f"run-time error: STATUS=0x{s:04x}")
                return s
        raise TimeoutError(f"wait_done: still BUSY after {max_polls} polls")

    def read_table(self, t: int) -> dict:
        """DBG_SEL/DBG_DATA read of a built table (MAS §4 0x114/0x118)."""
        out = {"count": [], "first_code": [], "base": [], "symtab": []}
        for kind, key, n in ((0, "count", MAXLEN), (1, "first_code", MAXLEN),
                             (2, "base", MAXLEN), (3, "symtab", ALPHABET_MAX)):
            for idx in range(1 if kind < 3 else 0, n + (1 if kind < 3 else 0)):
                self._wr(DBG_SEL, (t & 0x7) | (kind << 4) | (idx << 8))
                out[key].append(self._rd(DBG_DATA))
        return out

    def decode_block(self, data, start_bit, tables, selectors,
                     mode=MODE_BZIP2) -> tuple[list[int], int]:
        """configure + load_lengths, program the platform DMA model with
        data / selectors / a sink buffer, doorbell, wait_done, collect the sink;
        return (symbol beats as ints, bits consumed). The backend owns the
        symbol values (golden model on ModelBus, RTL on SimBackend)."""
        alphabet = (tables and len(tables[0])) or 0
        self.configure(mode, start_bit, alphabet, len(tables))
        self.load_lengths(tables)
        if hasattr(self.bus, "program_dma"):
            self.bus.program_dma(data, start_bit, tables, selectors, mode)
        if not self.start():
            raise RuntimeError(f"doorbell rejected: STATUS=0x{self.status():04x}")
        self.wait_done(max_polls=SYMBOL_LIMIT_MAX)
        c = self.counters()
        sink = getattr(self.bus, "sink", [])
        self.clear()
        return sink, c["bits"]


class ModelBus(MMIO):
    """Standalone functional + cycle model of the register block (no RTL).

    Honours the MAS §5 invocation protocol so the driver and the speedup model
    run without a simulator. Symbol values come from the frozen golden model
    (`golden/canonical_model.py`) when a bitstream is programmed via
    `program_dma`; the cycle count comes from `cycle_model()` (docs/decode_model
    .py). Parameter validation mirrors MAS §8 doorbell checks (ERR_PARAM)."""
    def __init__(self):
        self.mem = {}
        self.busy = False
        self.sticky = 0
        self.cycles = 0
        self.symbols = 0
        self.bits = 0
        self.build_cycles = 0
        self.overfetch = 0
        self.sink = []
        self._dma = None  # (data, start_bit, tables, selectors, mode)

    def _word(self, addr):
        return self.mem.get(addr, 0)

    def program_dma(self, data, start_bit, tables, selectors, mode):
        self._dma = (data, start_bit, tables, selectors, mode)

    def read32(self, addr: int) -> int:
        if addr == ID:
            return ID_VALUE
        if addr == STATUS:
            return (self.sticky & self.STICKY_HW) | (1 if self.busy else 0)
        if addr == IRQ_STATUS:
            return self.sticky & self._word(IRQ_EN)
        if addr == CYCLES_LO:
            return self.cycles & 0xFFFFFFFF
        if addr == CYCLES_HI:
            return (self.cycles >> 32) & 0xFFFFFFFF
        if addr == SYMBOLS:
            return self.symbols
        if addr == BITS:
            return self.bits
        if addr == BUILD_CYCLES:
            return self.build_cycles & 0xFFFF
        if addr == OVERFETCH:
            return self.overfetch & 0xFF
        return self._word(addr)

    STICKY_HW = 0xFFFE  # STATUS bits 15:1

    def write32(self, addr: int, value: int) -> None:
        value &= 0xFFFFFFFF
        if addr == CTRL:
            if self.busy:
                self.sticky |= ST_ERR_BUSY
                return
            if value & CTRL_DOORBELL:
                self._doorbell()
            return
        if addr == STATUS:            # W1C
            self.sticky &= ~(value & self.STICKY_HW)
            return
        if self.busy and addr in (MODE, START_BIT, ALPHABET, N_TABLES,
                                  SYMBOL_LIMIT) or (self.busy and LEN_BASE <= addr):
            self.sticky |= ST_ERR_BUSY
            return
        self.mem[addr] = value

    def _doorbell(self):
        mode = self._word(MODE)
        alphabet = self._word(ALPHABET) & 0x1FF
        n_tables = self._word(N_TABLES) & 0x7
        start_bit = self._word(START_BIT)
        limit = self._word(SYMBOL_LIMIT)
        # MAS §8 doorbell parameter checks -> ERR_PARAM
        if not (1 <= limit <= SYMBOL_LIMIT_MAX):
            self.sticky |= ST_ERR_PARAM
            return
        if mode == HuffmanDriver.MODE_DEFLATE:
            if n_tables != 2 or not (257 <= alphabet <= ALPHABET_MAX):
                self.sticky |= ST_ERR_PARAM
                return
        else:
            if not (1 <= n_tables <= N_TABLES_MAX) or not (3 <= alphabet <= ALPHABET_MAX):
                self.sticky |= ST_ERR_PARAM
                return
        # functional decode via the frozen golden model (MAS §9 F15)
        lengths = None
        if self._dma is not None:
            data, sbit, tables, selectors, dmode = self._dma
            import canonical_model as CM  # golden/ on PYTHONPATH
            if dmode == HuffmanDriver.MODE_DEFLATE:
                events, end_pos, _gc = CM.decode_deflate_symbols(data, sbit, tables[0], tables[1])
                # ADR-0006: one m_sym beat per event (lit/copy/eob)
                beats = [e[1] if e[0] == "lit" else 256 for e in events]
            else:
                beats, end_pos, _gc = CM.decode_bzip2_symbols(data, sbit, tables, selectors, alphabet)
            self.sink = list(beats)
            self.symbols = len(self.sink)
            lengths = self._per_symbol_lengths(tables, selectors, self.sink, alphabet, dmode)
        # cycle count from the signed-off model (docs/decode_model.py)
        if lengths is not None:
            r = cycle_model(lengths, alphabet, n_tables, start_bit)
            self.cycles = r["cycles"]
            self.bits = sum(lengths)
            self.build_cycles = alphabet + MAXLEN
        else:
            # no bitstream programmed: pure protocol probe
            self.cycles = max(n_tables * (alphabet + MAXLEN), start_bit // 32) + 2
        self.overfetch = 0
        self.sticky |= ST_DONE
        self.busy = False

    @staticmethod
    def _per_symbol_lengths(tables, selectors, beats, alphabet, mode):
        """Reconstruct per-symbol code lengths from the decoded beats and the
        table lengths (for the aligner cycle model). bzip2: selector switches
        the table every 50 symbols."""
        lens = []
        if mode == HuffmanDriver.MODE_DEFLATE:
            litlen = tables[0]
            for b in beats:
                sym = b & 0x1FF
                lens.append(litlen[sym] if sym < len(litlen) and litlen[sym] else 1)
            return lens
        sel_idx = 0
        for n, b in enumerate(beats):
            if n % 50 == 0:
                t = selectors[sel_idx] if sel_idx < len(selectors) else 0
                sel_idx += 1
                cur = tables[t] if t < len(tables) else tables[0]
            sym = b & 0x1FF
            lens.append(cur[sym] if sym < len(cur) and cur[sym] else 1)
        return lens
