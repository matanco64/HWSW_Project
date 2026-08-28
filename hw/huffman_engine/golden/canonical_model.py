"""Emulation model for huffman_engine: the hardware's exact algorithm, written independently of
pyflate (the pyuvm predictor). Comparator-cascade canonical Huffman decode, 1 symbol per step:

  build(lengths):  count[len], first_code[len] (canonical: codes assigned by increasing length,
                   then by symbol index), base[len] = index of first symbol of that length in the
                   symbol table sorted by (len, symbol);  symtab = symbols sorted by (len, symbol).
  decode(peek):    for every len in 1..MAXLEN in parallel, code = peek >> (MAXLEN - len);
                   match if first_code[len] <= code < first_code[len] + count[len];
                   the shortest matching len wins;  sym = symtab[base[len] + code - first_code[len]].

Bit order: bzip2 = MSB-first; DEFLATE = LSB-first stream with each code's bits reversed, so the
aligner reverses the peeked window and the same comparator cascade applies.
Cycle model (PRD K1/K2), assumptions to be confirmed at uArch: build = ALPHABET + MAXLEN + ALPHABET
steps per table, all tables built serially after the doorbell; decode = 1 step per symbol; selector
switch = 1 step (0 if six register sets are kept, research §2); aligner refill = 0 steps (the
64-bit window always holds >= MAXLEN spare bits); extra-bit reads = 0 steps (same window).
After the end of the input buffer the window is padded with zeros (PRD-F4).
"""
MAXLEN_BZ2 = 20
MAXLEN_DEFLATE = 15


class Table:
    def __init__(self, lengths, maxlen):
        self.maxlen = maxlen
        n = len(lengths)
        count = [0] * (maxlen + 1)
        for l in lengths:
            if l:
                if l > maxlen:
                    raise ValueError("ERR_TABLE: code length %d > MAXLEN %d" % (l, maxlen))
                count[l] += 1
        # PRD-F9 ERR_TABLE = over-subscribed only (Kraft sum > 1); incomplete and empty tables are
        # legal (RFC 1951 3.2.7: a single distance code, or no distance codes at all).
        if sum(c << (maxlen - l) for l, c in enumerate(count) if l) > (1 << maxlen):
            raise ValueError("ERR_TABLE: over-subscribed code")
        first_code = [0] * (maxlen + 2)
        base = [0] * (maxlen + 2)
        code = 0
        idx = 0
        for l in range(1, maxlen + 1):
            first_code[l] = code
            base[l] = idx
            code = (code + count[l]) << 1
            idx += count[l]
        symtab = [s for l in range(1, maxlen + 1) for s in range(n) if lengths[s] == l]
        self.count, self.first_code, self.base, self.symtab = count, first_code, base, symtab
        self.build_steps = n + maxlen + n   # count pass + prefix pass + assign pass

    def decode(self, peek):
        """peek: the next MAXLEN bits, MSB-first, as an int. Returns (symbol, length)."""
        for l in range(1, self.maxlen + 1):
            if self.count[l] == 0:
                continue
            code = peek >> (self.maxlen - l)
            if self.first_code[l] <= code < self.first_code[l] + self.count[l]:
                return self.symtab[self.base[l] + code - self.first_code[l]], l
        raise ValueError("ERR_NOCODE: no code matches within MAXLEN bits (peek=%#x)" % peek)


class BitReader:
    """Aligner model: peek/consume on a byte buffer. msb_first=True for bzip2, False for DEFLATE."""

    def __init__(self, data, bit_pos=0, msb_first=True):
        self.data, self.pos, self.msb = data, bit_pos, msb_first

    def _bit(self, p):
        byte = self.data[p >> 3] if (p >> 3) < len(self.data) else 0
        return (byte >> (7 - (p & 7))) & 1 if self.msb else (byte >> (p & 7)) & 1

    def peek(self, n):
        """n bits in code order (MSB-first int). For DEFLATE this is the reversed LSB-first window."""
        v = 0
        for i in range(n):
            v = (v << 1) | self._bit(self.pos + i)
        return v

    def raw(self, n):
        """DEFLATE extra bits: LSB-first integer of the next n bits, consumed."""
        v = 0
        for i in range(n):
            v |= self._bit(self.pos + i) << i
        self.pos += n
        return v

    def consume(self, n):
        self.pos += n


def decode_bzip2_symbols(data, bit_pos, lengths_per_table, selectors, symbols_in_use):
    """Returns (symbols, end_bit_pos, cycles). Stops after EOB (= symbols_in_use - 1)."""
    tables = [Table(l, MAXLEN_BZ2) for l in lengths_per_table]
    rd = BitReader(data, bit_pos, msb_first=True)
    cycles = sum(t.build_steps for t in tables)
    out = []
    eob = symbols_in_use - 1
    sel_i = 0
    group_left = 0
    while True:
        if group_left == 0:
            if sel_i >= len(selectors):
                raise ValueError("selector list exhausted")
            t = tables[selectors[sel_i]]
            sel_i += 1
            group_left = 50
            cycles += 1
        sym, l = t.decode(rd.peek(MAXLEN_BZ2))
        rd.consume(l)
        cycles += 1
        group_left -= 1
        out.append(sym)
        if sym == eob:
            break
    return out, rd.pos, cycles


# DEFLATE (RFC 1951) constants
_LEN_BASE = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99,
             115, 131, 163, 195, 227, 258]
_LEN_EXTRA = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0]
_DIST_BASE = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025,
              1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577]
_DIST_EXTRA = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12,
               12, 13, 13]


def decode_deflate_symbols(data, bit_pos, lit_lengths, dist_lengths):
    """One DEFLATE Huffman block body (after the header/tables are parsed by software).
    Returns (events, end_bit_pos, cycles): events are ('lit', byte) | ('copy', length, distance)
    | ('eob',)."""
    lit, dist = Table(lit_lengths, MAXLEN_DEFLATE), Table(dist_lengths, MAXLEN_DEFLATE)
    rd = BitReader(data, bit_pos, msb_first=False)
    cycles = lit.build_steps + dist.build_steps
    ev = []
    while True:
        s, l = lit.decode(rd.peek(MAXLEN_DEFLATE))
        rd.consume(l)
        cycles += 1
        if s < 256:
            ev.append(("lit", s))
        elif s == 256:
            ev.append(("eob",))
            break
        elif s >= 286:
            raise ValueError("ERR_SYMBOL: literal/length code %d" % s)     # RFC 1951: 286/287 never occur
        else:
            i = s - 257
            length = _LEN_BASE[i] + rd.raw(_LEN_EXTRA[i])                  # 284 + extra 31 = 258 (pyflate does the same)
            d, dl = dist.decode(rd.peek(MAXLEN_DEFLATE))
            rd.consume(dl)
            cycles += 1
            if d >= 30:
                raise ValueError("ERR_SYMBOL: distance code %d" % d)       # RFC 1951: 30/31 never occur
            distance = _DIST_BASE[d] + rd.raw(_DIST_EXTRA[d])              # 1..32768 -> 16-bit field (PRD-F5)
            ev.append(("copy", length, distance))
    return ev, rd.pos, cycles
