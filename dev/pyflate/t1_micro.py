"""T1 -- low-effort / mechanical tier.

Same algorithm as T0 (the linear-scan Huffman matcher is untouched) but:
  * whole input read once into `bytes`; the bit buffer is refilled 4 bytes at a
    time instead of one `f.read(1)` per byte;
  * `_mask()` inlined as `(1 << n) - 1`; `needbits` folded into snoop/read;
  * the move-to-front list is held in REVERSE order so `pop(-r)` + `append()`
    memmoves only `rank` slots instead of rewriting the whole 147-entry list;
  * the symbol buffer is a `bytearray` (no 90k one-byte `bytes` objects + join);
  * hot attributes bound to locals in the symbol loop.

Only the bzip2 path is implemented here (the shipped benchmark input is bzip2);
the landed benchmark keeps the gzip path intact.
"""

NAME = "T1 micro"


class RBitfield(object):
    """MSB-first bit reader over an in-memory bytes object."""

    __slots__ = ('data', 'pos', 'bitfield', 'bits')

    def __init__(self, x):
        self.data = x if isinstance(x, (bytes, bytearray)) else x.read()
        self.pos = 0
        self.bitfield = 0
        self.bits = 0

    def _fill(self, n):
        # refill in 4-byte chunks until at least n bits are buffered
        d = self.data
        p = self.pos
        bf = self.bitfield
        b = self.bits
        while b < n:
            chunk = d[p:p + 4]
            if not chunk:
                raise Exception("Length Error")
            k = len(chunk)
            bf = (bf << (k << 3)) | int.from_bytes(chunk, 'big')
            b += k << 3
            p += k
        self.pos = p
        self.bitfield = bf
        self.bits = b

    def snoopbits(self, n=8):
        if n > self.bits:
            self._fill(n)
        return (self.bitfield >> (self.bits - n)) & ((1 << n) - 1)

    def readbits(self, n=8):
        if n > self.bits:
            self._fill(n)
        b = self.bits - n
        bf = self.bitfield
        self.bits = b
        self.bitfield = bf & ((1 << b) - 1)
        return (bf >> b) & ((1 << n) - 1)

    def align(self):
        n = self.bits & 0x7
        if n:
            self.readbits(n)

    def tell(self):
        return self.pos - ((self.bits + 7) >> 3), 7 - ((self.bits - 1) & 0x7)


# ---------------------------------------------------------------- Huffman ---

class HuffmanLength(object):
    __slots__ = ('code', 'bits', 'symbol', 'reverse_symbol')

    def __init__(self, code, bits=0):
        self.code = code
        self.bits = bits
        self.symbol = None
        self.reverse_symbol = None

    @staticmethod
    def _sort_func(obj):
        return (obj.bits, obj.code)


def reverse_bits(v, n):
    a = 1 << 0
    b = 1 << (n - 1)
    z = 0
    for i in range(n - 1, -1, -2):
        z |= (v >> i) & a
        z |= (v << i) & b
        a <<= 1
        b >>= 1
    return z


class HuffmanTable(object):

    def __init__(self, bootstrap):
        l = []
        start, bits = bootstrap[0]
        for finish, endbits in bootstrap[1:]:
            if bits:
                for code in range(start, finish):
                    l.append(HuffmanLength(code, bits))
            start, bits = finish, endbits
            if endbits == -1:
                break
        l.sort(key=HuffmanLength._sort_func)
        self.table = l

    def populate_huffman_symbols(self):
        bits, symbol = -1, -1
        for x in self.table:
            symbol += 1
            if x.bits != bits:
                symbol <<= (x.bits - bits)
                bits = x.bits
            x.symbol = symbol
            x.reverse_symbol = reverse_bits(symbol, bits)

    def min_max_bits(self):
        self.min_bits, self.max_bits = 16, -1
        for x in self.table:
            if x.bits < self.min_bits:
                self.min_bits = x.bits
            if x.bits > self.max_bits:
                self.max_bits = x.bits

    def find_next_symbol(self, field, reversed=True):
        cached_length = -1
        cached = None
        for x in self.table:
            if cached_length != x.bits:
                cached = field.snoopbits(x.bits)
                cached_length = x.bits
            if (reversed and x.reverse_symbol == cached) or (not reversed and x.symbol == cached):
                field.readbits(x.bits)
                return x.code
        raise Exception("unfound symbol, even after end of table")


class OrderedHuffmanTable(HuffmanTable):

    def __init__(self, lengths):
        l = len(lengths)
        z = list(zip(range(l), lengths)) + [(l, -1)]
        HuffmanTable.__init__(self, z)


# -------------------------------------------------------------- bzip2 body --

def move_to_front(l, c):
    l[:] = l[c:c + 1] + l[0:c] + l[c + 1:]


def bwt_transform(L):
    F = bytes(sorted(L))
    base = []
    for i in range(256):
        base.append(F.find(bytes((i,))))
    pointers = [-1] * len(L)
    for i, symbol in enumerate(L):
        pointers[base[symbol]] = i
        base[symbol] += 1
    return pointers


def bwt_reverse(L, end):
    out = []
    if len(L):
        T = bwt_transform(L)
        append = out.append
        for _ in range(len(L)):
            end = T[end]
            append(L[end])
    return bytes(out)


def compute_used(b):
    huffman_used_map = b.readbits(16)
    map_mask = 1 << 15
    used = []
    while map_mask > 0:
        if huffman_used_map & map_mask:
            huffman_used_bitmap = b.readbits(16)
            bit_mask = 1 << 15
            while bit_mask > 0:
                used.append(bool(huffman_used_bitmap & bit_mask))
                bit_mask >>= 1
        else:
            used += [False] * 16
        map_mask >>= 1
    return used


def compute_selectors_list(b, huffman_groups):
    selectors_used = b.readbits(15)
    mtf = list(range(huffman_groups))
    selectors_list = []
    for i in range(selectors_used):
        c = 0
        while b.readbits(1):
            c += 1
            if c >= huffman_groups:
                raise Exception("selector greater than number of groups")
        if c >= 0:
            move_to_front(mtf, c)
        selectors_list.append(mtf[0])
    return selectors_list


def compute_tables(b, huffman_groups, symbols_in_use):
    groups_lengths = []
    for j in range(huffman_groups):
        length = b.readbits(5)
        lengths = []
        for i in range(symbols_in_use):
            if not 0 <= length <= 20:
                raise Exception("Bzip2 Huffman length code outside range 0..20")
            while b.readbits(1):
                length -= (b.readbits(1) * 2) - 1
            lengths.append(length)
        groups_lengths.append(lengths)

    tables = []
    for g in groups_lengths:
        codes = OrderedHuffmanTable(g)
        codes.populate_huffman_symbols()
        codes.min_max_bits()
        tables.append(codes)
    return tables


def decode_huffman_block(b, out):
    randomised = b.readbits(1)
    if randomised:
        raise Exception("Bzip2 randomised support not implemented")
    pointer = b.readbits(24)
    used = compute_used(b)

    huffman_groups = b.readbits(3)
    if not 2 <= huffman_groups <= 6:
        raise Exception("Bzip2: Number of Huffman groups not in range 2..6")

    selectors_list = compute_selectors_list(b, huffman_groups)
    symbols_in_use = sum(used) + 2
    tables = compute_tables(b, huffman_groups, symbols_in_use)

    # favourites held in REVERSE order: the front of the MTF list is fav[-1],
    # so rank r-1 lives at index -r and move-to-front is pop(-r) + append(),
    # which memmoves only `rank` slots instead of the whole list.
    fav = [i for i, x in enumerate(used) if x]
    fav.reverse()

    eob = symbols_in_use - 1
    selector_pointer = 0
    decoded = 0
    repeat = repeat_power = 0
    buffer = bytearray()
    buf_append = buffer.append
    buf_extend = buffer.extend
    fav_pop = fav.pop
    fav_append = fav.append
    nsel = len(selectors_list)
    find = None
    while True:
        decoded -= 1
        if decoded <= 0:
            decoded = 50
            if selector_pointer <= nsel:
                find = tables[selectors_list[selector_pointer]].find_next_symbol
                selector_pointer += 1

        r = find(b, False)
        if r <= 1:
            if repeat == 0:
                repeat_power = 1
            repeat += repeat_power << r
            repeat_power <<= 1
            continue
        elif repeat > 0:
            buf_extend(bytes((fav[-1],)) * repeat)
            repeat = 0
        if r == eob:
            break
        o = fav_pop(-r)
        fav_append(o)
        buf_append(o)

    nt = bwt_reverse(bytes(buffer), pointer)
    out.append(rle4_expand(nt))


def rle4_expand(nt):
    out = []
    i = 0
    n = len(nt)
    while i < n:
        if i < n - 4 and nt[i] == nt[i + 1] == nt[i + 2] == nt[i + 3]:
            out.append(nt[i:i + 1] * (nt[i + 4] + 4))
            i += 5
        else:
            out.append(nt[i:i + 1])
            i += 1
    return b"".join(out)


def bzip2_main(b):
    method = b.readbits(8)
    if method != 0x68:
        raise Exception("Unknown compression method")
    blocksize = b.readbits(8)
    if not (0x31 <= blocksize <= 0x39):
        raise Exception("Unknown Bzip2 blocksize")

    out = []
    while True:
        blocktype = b.readbits(48)
        b.readbits(32)
        if blocktype == 0x314159265359:
            decode_huffman_block(b, out)
        elif blocktype == 0x177245385090:
            b.align()
            break
        else:
            raise Exception("Illegal Bzip2 blocktype")
    return b''.join(out)


def decompress(filename):
    with open(filename, 'rb') as fp:
        data = fp.read()
    field = RBitfield(data)
    magic = field.readbits(16)
    if magic != 0x425a:
        raise Exception("not bzip2")
    return bzip2_main(field)
