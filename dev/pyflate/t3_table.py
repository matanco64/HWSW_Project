"""T3 -- table-driven Huffman decode + counting-sort inverse BWT + regex RLE4.

Deltas versus T2:

 1. Huffman: a flat primary lookup table indexed by the next PRIMARY_BITS bits
    gives (symbol, length) in ONE list index -- O(1) per symbol instead of
    O(len - minLen) canonical steps.  Codes longer than PRIMARY_BITS (0.4% of
    symbols in this input) fall back to the T2 canonical stepping loop, which
    is exactly the two-level table structure zlib's inflate uses, with the
    secondary tables replaced by the (already-built) canonical arrays.
    Because bzip2 codes are MSB-first canonical, the table entries for the
    symbols in canonical order are CONTIGUOUS runs, so the table is built with
    ~147 C-level `list.__iadd__` span fills, not 2**PRIMARY_BITS per-slot
    writes -- build cost is ~0.15 ms for all 6 tables (measured), i.e. 0.1% of
    the block, so it amortises trivially over 148k symbol decodes.

 2. Inverse BWT: replaces `bytes(sorted(L))` + 256 x `F.find()` -- an
    O(n log n) sort used only to recover 256 bucket offsets -- with an O(n+256)
    counting sort (`collections.Counter` + prefix sum).  The chain walk writes
    into a preallocated `bytearray` instead of appending ints to a list and
    converting at the end.

 3. RLE4: the per-byte `while` loop that slices one byte at a time
    (336k iterations, 336k one-byte `bytes` objects) is replaced by a regex
    span copy -- `(?s)(.)\1{3}(?=.)` finds the next 4-byte run at C speed and
    the literal stretch between runs is copied with a single slice.  Python
    iterations drop from 336k to (number of runs).

Fusing decision (measured, see micro.py): fusing RLE4 INTO the BWT chain walk
was rejected -- the regex pass costs 10.7 ms while adding a run-detect compare
to all 336k walk iterations costs more than that.  Fusing Huffman -> MTF -> RLE
IS done: they share one loop and write straight into a single `bytearray`.
"""

import collections
import re

from t1_micro import RBitfield, compute_used, compute_selectors_list  # noqa: F401
from t2_canonical import build_canonical                              # noqa: F401

NAME = "T3 table"

MASK = [(1 << i) - 1 for i in range(65)]

# 11 bits covers 99.6% of the symbols in this input while keeping the primary
# table at 2048 entries (16 KB of pointers -- comfortably L1/L2 resident).
PRIMARY_BITS = 11

RUN4 = re.compile(rb'(?s)(.)\1{3}(?=.)')


def build_table(lengths, primary_bits=None):
    """Return (pb, pmask, tbl, minLen, limit, base, perm).

    tbl[peek(pb)] = (symbol << 5) | code_length, or 0 when the code is longer
    than `pb` bits (then the canonical limit/base/perm arrays are used).
    """
    if primary_bits is None:
        primary_bits = PRIMARY_BITS
    minLen, maxLen, limit, base, perm = build_canonical(lengths)
    pb = min(primary_bits, maxLen)

    tbl = []
    for s in perm:
        l = lengths[s]
        if l > pb:
            break
        tbl += [(s << 5) | l] * (1 << (pb - l))
    tbl += [0] * ((1 << pb) - len(tbl))
    return pb, (1 << pb) - 1, tbl, minLen, limit, base, perm


def compute_tables(b, huffman_groups, symbols_in_use):
    tables = []
    for j in range(huffman_groups):
        length = b.readbits(5)
        lengths = []
        for i in range(symbols_in_use):
            if not 0 <= length <= 20:
                raise Exception("Bzip2 Huffman length code outside range 0..20")
            while b.readbits(1):
                length -= (b.readbits(1) * 2) - 1
            lengths.append(length)
        tables.append(build_table(lengths))
    return tables


def bwt_reverse(L, end):
    """Inverse BWT with an O(n + 256) counting sort instead of an O(n log n)
    sort, writing the chain walk straight into a bytearray."""
    n = len(L)
    if not n:
        return b''

    cnt = collections.Counter(L)
    base = [0] * 256
    t = 0
    for s in range(256):
        base[s] = t
        t += cnt.get(s, 0)

    T = [0] * n
    for i, sym in enumerate(L):
        b = base[sym]
        T[b] = i
        base[sym] = b + 1

    out = bytearray(n)
    for i in range(n):
        end = T[end]
        out[i] = L[end]
    return bytes(out)


def rle4_expand(nt):
    res = []
    ap = res.append
    search = RUN4.search
    i = 0
    while True:
        m = search(nt, i)
        if m is None:
            break
        s = m.start()
        if s > i:
            ap(nt[i:s])
        ap(nt[s:s + 1] * (nt[s + 4] + 4))
        i = s + 5
    ap(nt[i:])
    return b"".join(res)


def decode_huffman_block(b, out):
    if b.readbits(1):
        raise Exception("Bzip2 randomised support not implemented")
    pointer = b.readbits(24)
    used = compute_used(b)

    huffman_groups = b.readbits(3)
    if not 2 <= huffman_groups <= 6:
        raise Exception("Bzip2: Number of Huffman groups not in range 2..6")

    selectors_list = compute_selectors_list(b, huffman_groups)
    symbols_in_use = sum(used) + 2
    tables = compute_tables(b, huffman_groups, symbols_in_use)

    fav = [i for i, x in enumerate(used) if x]
    fav.reverse()                       # front of the MTF list is fav[-1]
    fav_pop = fav.pop
    fav_append = fav.append

    eob = symbols_in_use - 1
    buffer = bytearray()
    buf_append = buffer.append
    buf_extend = buffer.extend

    data = b.data
    pos = b.pos
    acc = b.bitfield
    nbits = b.bits
    mask = MASK

    selector_pointer = 0
    nsel = len(selectors_list)
    repeat = repeat_power = 0
    pb = pmask = 0
    tbl = limit = base = perm = None
    minLen = 0
    decoded = 0

    while True:
        decoded -= 1
        if decoded <= 0:
            decoded = 50
            if selector_pointer <= nsel:
                pb, pmask, tbl, minLen, limit, base, perm = \
                    tables[selectors_list[selector_pointer]]
                selector_pointer += 1

        if nbits < 32:
            chunk = data[pos:pos + 4]
            acc = ((acc & mask[nbits]) << (len(chunk) << 3)) | int.from_bytes(chunk, 'big')
            nbits += len(chunk) << 3
            pos += len(chunk)

        # ---- one array index resolves 99.6% of the symbols --------------
        zvec = (acc >> (nbits - pb)) & pmask
        v = tbl[zvec]
        if v:
            nbits -= v & 31
            r = v >> 5
        else:
            zn = pb
            while zvec > limit[zn]:
                zn += 1
                zvec = (zvec << 1) | ((acc >> (nbits - zn)) & 1)
            nbits -= zn
            r = perm[zvec - base[zn]]

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

    b.pos = pos
    b.bitfield = acc & mask[nbits]
    b.bits = nbits

    out.append(rle4_expand(bwt_reverse(bytes(buffer), pointer)))


def bzip2_main(b):
    if b.readbits(8) != 0x68:
        raise Exception("Unknown compression method")
    if not (0x31 <= b.readbits(8) <= 0x39):
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
        # 8 zero bytes of tail padding so the fixed-width 32-bit refill and the
        # PRIMARY_BITS-wide peek never run off the end of the buffer on the
        # final symbol of the stream.  Padding is never part of any decoded
        # symbol (the stream ends at the end-of-stream magic).
        data = fp.read() + b'\x00' * 8
    field = RBitfield(data)
    if field.readbits(16) != 0x425a:
        raise Exception("not bzip2")
    return bzip2_main(field)
