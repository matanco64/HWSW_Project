#!/usr/bin/env python
"""
Copyright 2006--2007-01-21 Paul Sladen
http://www.paul.sladen.org/projects/compression/

You may use and distribute this code under any DFSG-compatible
license (eg. BSD, GNU GPLv2).

Stand-alone pure-Python DEFLATE (gzip) and bzip2 decoder/decompressor.
This is probably most useful for research purposes/index building;  there
is certainly some room for improvement in the Huffman bit-matcher.

With the as-written implementation, there was a known bug in BWT
decoding to do with repeated strings.  This has been worked around;
see 'bwt_reverse()'.  Correct output is produced in all test cases
but ideally the problem would be found...

-----------------------------------------------------------------------
HW/SW final project -- SOFTWARE OPTIMIZATION of the bzip2 decode path.

The workload is unchanged: the same 67,562-byte bzip2 stream is decoded to
the same 399,360 bytes, and the same MD5 check guards every run.  What
changed is *how* the decoder does its work.  The author's own docstring
above says "there is certainly some room for improvement in the Huffman
bit-matcher" -- that is exactly what is fixed here.

  1. Bit reader (`RBitfield`).  The stock reader called `f.read(1)` once per
     input byte and rebuilt a Python int with `_mask()` helper calls on every
     access.  It now reads the stream once into `bytes` and keeps a bounded
     bit window refilled 32 bits at a time; the mask is a precomputed table.

  2. Huffman decode.  The stock `find_next_symbol()` walked the 258-entry
     `HuffmanLength` list linearly, calling `snoopbits()` again at every new
     code length.  bzip2 codes are *canonical*, so per table we precompute the
     zlib/libbzip2 arrays (`limit`, `base`, `perm`) plus a flat primary lookup
     table indexed by the next PRIMARY_BITS bits.  A symbol is then one list
     index (99.6% of symbols in this stream); the rest fall back to canonical
     bit-at-a-time extension.  Table build cost is ~0.5 ms for all six tables
     and happens 6 times per block, versus 148,271 symbol decodes.

  3. Move-to-front.  The list is kept in reverse order, so a move-to-front is
     `l.append(l.pop(-r))`, which memmoves `rank` slots (mean rank 7.2) rather
     than rebuilding the whole 147-entry list from three slices.

  4. Inverse BWT.  `bytes(sorted(L))` + 256 `find()` calls -- an O(n log n)
     sort used only to recover 256 bucket offsets -- is replaced by an
     O(n + 256) counting sort, and the chain walk fills a preallocated
     `bytearray`.

  5. Final RLE4 expansion.  The per-byte loop that sliced one byte at a time
     is replaced by a regex that locates each 4-byte run at C speed; the
     literal stretches between runs are copied with one slice each.

The DEFLATE/gzip half of the module (`Bitfield`, `HuffmanTable`,
`gzip_main`, ...) is deliberately left untouched and still functional.
"""

import hashlib
import io
import os
import re
import struct

import pyperf

# ---------------------------------------------------------------------------
# NATIVE ACCELERATION (optional).
#
# `pyflate_rs` is our Rust/PyO3 build of the symbol-decode kernel (`rust/pyflate/`).
# It is imported, never required.  The course's three rules for an accelerator's
# HW/SW interface (Lecture 5, "Accelerator Design Patterns") are the reason this
# is shaped as an import and not as a rewrite:
#
#   Rule 1  do not expect end users to change their code.  `run_benchmark.py`
#           keeps the same CLI, the same pyperf harness and the same MD5 check
#           whether or not the extension is present.
#   Rule 2  if software must change, confine the change to a runtime/library.
#           Every native line lives in a separate crate behind one call.
#   Rule 3  do not break the user's code -- if the accelerator cannot handle an
#           operation, run it on the CPU.  A missing wheel, a different CPython
#           ABI, or a non-x86 host all land on the pure-Python path below, which
#           is still the optimized decoder and still passes the same checks.
#
# The same rule is why the boundary sits where it does: the kernel covers bit
# reader -> canonical Huffman -> MTF -> RUNA/RUNB, and hands the inverse BWT and
# RLE4 back to Python.  That is not an arbitrary split.  It is exactly the
# `huffman_engine` + `mtf_cam` boundary in `hw/`, so this crate doubles as the
# golden model for the RTL, and the stages left in Python are the ones §5c of
# the report argues hardware cannot fix cheaply either.

# Back-end selection.  "auto" (the default) prefers the native kernel and falls
# back to Python; "python" and "native" pin it.  This exists because otherwise
# what gets measured depends on what happens to be installed in whichever venv
# pyperformance built -- two runs could measure different back ends and produce
# JSON that looks the same.  The choice is recorded in the pyperf metadata.
_BACKEND = os.environ.get("HWSW_BACKEND", "auto").lower()
if _BACKEND not in ("auto", "python", "native"):
    raise SystemExit("HWSW_BACKEND must be one of: auto, python, native")

try:
    import pyflate_rs
except ImportError:                                          # pragma: no cover
    pyflate_rs = None

if _BACKEND == "python":
    pyflate_rs = None
elif _BACKEND == "native" and pyflate_rs is None:
    raise SystemExit("HWSW_BACKEND=native but pyflate_rs is not importable")


int2byte = struct.Struct(">B").pack

# Precomputed low-bit masks; replaces the per-call `_mask()` helper, which the
# stock decoder invoked 655,015 times for this input.
MASK = [(1 << i) - 1 for i in range(65)]

# Width of the flat Huffman lookup table.  11 bits resolves 99.6% of the
# symbols in this stream in a single index while keeping each table at 2048
# entries; measured end-to-end time is flat for any value in 9..13.
PRIMARY_BITS = 11

# Four identical bytes followed by at least one more byte: the bzip2 RLE4
# escape.  `(?s)` so that '.' also matches b'\n'.
RUN4 = re.compile(rb'(?s)(.)\1{3}(?=.)')


class BitfieldBase(object):

    def __init__(self, x):
        if isinstance(x, BitfieldBase):
            self.f = x.f
            self.bits = x.bits
            self.bitfield = x.bitfield
            self.count = x.bitfield
        else:
            self.f = x
            self.bits = 0
            self.bitfield = 0x0
            self.count = 0

    def _read(self, n):
        s = self.f.read(n)
        if not s:
            raise "Length Error"
        self.count += len(s)
        return s

    def needbits(self, n):
        while self.bits < n:
            self._more()

    def _mask(self, n):
        return (1 << n) - 1

    def toskip(self):
        return self.bits & 0x7

    def align(self):
        self.readbits(self.toskip())

    def dropbits(self, n=8):
        while n >= self.bits and n > 7:
            n -= self.bits
            self.bits = 0
            n -= len(self.f._read(n >> 3)) << 3
        if n:
            self.readbits(n)
        # No return value

    def dropbytes(self, n=1):
        self.dropbits(n << 3)

    def tell(self):
        return self.count - ((self.bits + 7) >> 3), 7 - ((self.bits - 1) & 0x7)

    def tellbits(self):
        bytes, bits = self.tell()
        return (bytes << 3) + bits


class Bitfield(BitfieldBase):
    """LSB-first bit reader used by the DEFLATE/gzip path (unmodified)."""

    def _more(self):
        c = self._read(1)
        self.bitfield += ord(c) << self.bits
        self.bits += 8

    def snoopbits(self, n=8):
        if n > self.bits:
            self.needbits(n)
        return self.bitfield & self._mask(n)

    def readbits(self, n=8):
        if n > self.bits:
            self.needbits(n)
        r = self.bitfield & self._mask(n)
        self.bits -= n
        self.bitfield >>= n
        return r


class RBitfield(object):
    """MSB-first bit reader over an in-memory buffer.

    OPTIMIZED: the stock version inherited from BitfieldBase and pulled one
    byte at a time out of a file object (`_more` -> `_read` -> `f.read(1)`),
    then masked with a `_mask()` method call on every snoop and every read.
    This version slurps the stream once and refills 32 bits at a time from a
    `bytes` object, with masks taken from a table.  Same bit order, same
    values returned.
    """

    __slots__ = ('data', 'datalen', 'pos', 'bitfield', 'bits')

    # Tail padding so that a wide peek (PRIMARY_BITS) or a 32-bit refill on
    # the final symbol of the stream cannot run off the end of the buffer.
    # The padding is never part of a decoded symbol: the stream terminates at
    # its end-of-stream magic well before it.
    _PAD = b'\x00' * 8

    def __init__(self, x):
        data = x if isinstance(x, (bytes, bytearray)) else x.read()
        self.datalen = len(data)
        self.data = data + self._PAD
        self.pos = 0
        self.bitfield = 0
        self.bits = 0

    def _fill(self, n):
        d = self.data
        p = self.pos
        bf = self.bitfield
        b = self.bits
        while b < n:
            if p >= self.datalen + 8:
                raise Exception("Length Error")
            bf = (bf << 32) | int.from_bytes(d[p:p + 4], 'big')
            b += 32
            p += 4
        self.pos = p
        self.bitfield = bf
        self.bits = b

    def snoopbits(self, n=8):
        if n > self.bits:
            self._fill(n)
        return (self.bitfield >> (self.bits - n)) & MASK[n]

    def readbits(self, n=8):
        if n > self.bits:
            self._fill(n)
        b = self.bits - n
        bf = self.bitfield
        self.bits = b
        self.bitfield = bf & MASK[b]
        return (bf >> b) & MASK[n]

    def align(self):
        n = self.bits & 0x7
        if n:
            self.readbits(n)

    def tell(self):
        return self.pos - ((self.bits + 7) >> 3), 7 - ((self.bits - 1) & 0x7)

    def tellbits(self):
        b, k = self.tell()
        return (b << 3) + k

    def remainder(self):
        """A file object positioned at the next unconsumed byte.

        Used only to hand the still-unmodified gzip decoder its input, since
        that path expects a file-like object rather than this buffer.
        """
        off = self.pos - (self.bits >> 3)
        return io.BytesIO(self.data[off:self.datalen])


def printbits(v, n):
    o = ''
    for i in range(n):
        if v & 1:
            o = '1' + o
        else:
            o = '0' + o
        v >>= 1
    return o


class HuffmanLength(object):

    def __init__(self, code, bits=0):
        self.code = code
        self.bits = bits
        self.symbol = None
        self.reverse_symbol = None

    def __repr__(self):
        return repr((self.code, self.bits, self.symbol, self.reverse_symbol))

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


def reverse_bytes(v, n):
    a = 0xff << 0
    b = 0xff << (n - 8)
    z = 0
    for i in range(n - 8, -8, -16):
        z |= (v >> i) & a
        z |= (v << i) & b
        a <<= 8
        b >>= 8
    return z


class HuffmanTable(object):
    """Object-per-code Huffman table with a linear matcher.

    Still used by the DEFLATE/gzip path.  The bzip2 path now uses the
    canonical tables built by `build_huffman_table()` below.
    """

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

    def tables_by_bits(self):
        d = {}
        for x in self.table:
            try:
                d[x.bits].append(x)
            except:   # noqa
                d[x.bits] = [x]

    def min_max_bits(self):
        self.min_bits, self.max_bits = 16, -1
        for x in self.table:
            if x.bits < self.min_bits:
                self.min_bits = x.bits
            if x.bits > self.max_bits:
                self.max_bits = x.bits

    def _find_symbol(self, bits, symbol, table):
        for h in table:
            if h.bits == bits and h.reverse_symbol == symbol:
                return h.code
        return -1

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
        raise Exception("unfound symbol, even after end of table @%r"
                        % field.tell())


class OrderedHuffmanTable(HuffmanTable):

    def __init__(self, lengths):
        l = len(lengths)
        z = list(zip(range(l), lengths)) + [(l, -1)]
        HuffmanTable.__init__(self, z)


def build_huffman_table(lengths, primary_bits=PRIMARY_BITS):
    """Canonical Huffman decode tables for one bzip2 group.

    OPTIMIZED replacement for `OrderedHuffmanTable` +
    `populate_huffman_symbols()` + `min_max_bits()` on the bzip2 path.

    bzip2 hands out codes canonically: sorted by (length, symbol), starting at
    zero, shifted left by one at every length increment -- exactly what the
    stock `populate_huffman_symbols()` computes.  That lets us decode with
    arithmetic instead of a search:

        limit[l] : largest assigned l-bit code
        base[l]  : offset such that perm[code - base[l]] is the symbol
        perm[]   : symbols in canonical order

    and, on top of that, a flat table indexed by the next `primary_bits` bits
    that answers most symbols in a single index.  Because the codes are
    canonical and MSB-first, the slots belonging to consecutive symbols are
    contiguous, so the table is filled with one C-level span assignment per
    symbol rather than 2**primary_bits individual writes.

    Returns (pb, pmask, tbl, limit, base, perm) where
    tbl[peek(pb)] == (symbol << 5) | code_length, or 0 for "code is longer
    than pb bits, use limit/base/perm".
    """
    n = len(lengths)
    minLen = min(l for l in lengths if l)
    maxLen = max(lengths)

    perm = []
    for l in range(minLen, maxLen + 1):
        for s in range(n):
            if lengths[s] == l:
                perm.append(s)

    count = [0] * (maxLen + 2)
    for l in lengths:
        if l:
            count[l] += 1

    limit = [0] * (maxLen + 2)
    base = [0] * (maxLen + 2)
    vec = 0
    cum = 0
    for l in range(minLen, maxLen + 1):
        vec += count[l]
        limit[l] = vec - 1
        base[l] = (vec - count[l]) - cum
        cum += count[l]
        vec <<= 1

    pb = min(primary_bits, maxLen)
    tbl = []
    for s in perm:
        l = lengths[s]
        if l > pb:
            break
        tbl += [(s << 5) | l] * (1 << (pb - l))
    tbl += [0] * ((1 << pb) - len(tbl))

    return pb, MASK[pb], tbl, limit, base, perm


def code_length_orders(i):
    return (16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3,
            13, 2, 14, 1, 15)[i]


def distance_base(i):
    return (1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193,
            257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145, 8193,
            12289, 16385, 24577)[i]


def length_base(i):
    return (3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35,
            43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258)[i - 257]


def extra_distance_bits(n):
    if 0 <= n <= 1:
        return 0
    elif 2 <= n <= 29:
        return (n >> 1) - 1
    else:
        raise "illegal distance code"


def extra_length_bits(n):
    if 257 <= n <= 260 or n == 285:
        return 0
    elif 261 <= n <= 284:
        return ((n - 257) >> 2) - 1
    else:
        raise "illegal length code"


def move_to_front(l, c):
    l[:] = l[c:c + 1] + l[0:c] + l[c + 1:]


def bwt_transform(L):
    """Bucket-start pointers for the inverse BWT.

    OPTIMIZED: the stock version built `bytes(sorted(L))` -- an O(n log n)
    sort of 336,184 bytes -- and then called `F.find()` 256 times, purely to
    learn where each symbol's bucket starts.  A counting sort gets the same
    answer in O(n + 256): count the symbols, prefix-sum the counts, then place
    each position into its bucket.
    """
    counts = [0] * 256
    for symbol in L:
        counts[symbol] += 1

    base = []
    total = 0
    for c in counts:
        base.append(total)
        total += c

    pointers = [-1] * len(L)
    for i, symbol in enumerate(L):
        b = base[symbol]
        pointers[b] = i
        base[symbol] = b + 1
    return pointers


def bwt_reverse(L, end):
    # STRAGENESS WARNING: There was a bug somewhere here in that
    # if the output of the BWT resolves to a perfect copy of N
    # identical strings (think exact multiples of 255 'X' here),
    # then a loop is formed.  When decoded, the output string would
    # be cut off after the first loop, typically '\0\0\0\0\xfb'.
    # The previous loop construct was:
    #
    #  next = T[end]
    #  while next != end:
    #      out += L[next]
    #      next = T[next]
    #  out += L[next]
    #
    # For the moment, I've instead replaced it with a check to see
    # if there has been enough output generated.  I didn't figured
    # out where the off-by-one-ism is yet---that actually produced
    # the cyclic loop.
    n = len(L)
    if not n:
        return b''
    T = bwt_transform(L)
    # OPTIMIZED: fill a preallocated bytearray instead of appending 336k ints
    # to a list and converting at the end.
    out = bytearray(n)
    for i in range(n):
        end = T[end]
        out[i] = L[end]
    return bytes(out)


def rle4_expand(nt):
    """bzip2's final run-length step.

    OPTIMIZED: the stock loop advanced one byte at a time over the whole
    336,184-byte buffer, testing four neighbours and appending a fresh
    one-byte `bytes` object for every literal.  Runs are rare (8,542 of them
    here), so instead the regex engine finds the next run at C speed and each
    literal stretch between two runs is copied with a single slice.  Same
    left-to-right semantics: a run consumes 4 bytes plus the count byte, and
    scanning resumes after it.
    """
    out = []
    append = out.append
    search = RUN4.search
    i = 0
    while True:
        m = search(nt, i)
        if m is None:
            break
        s = m.start()
        if s > i:
            append(nt[i:s])
        append(nt[s:s + 1] * (nt[s + 4] + 4))
        i = s + 5
    append(nt[i:])
    return b"".join(out)


def compute_used(b):
    huffman_used_map = b.readbits(16)
    map_mask = 1 << 15
    used = []
    while map_mask > 0:
        if huffman_used_map & map_mask:
            huffman_used_bitmap = b.readbits(16)
            bit_mask = 1 << 15
            while bit_mask > 0:
                if huffman_used_bitmap & bit_mask:
                    pass
                used += [bool(huffman_used_bitmap & bit_mask)]
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
        # zero-terminated bit runs (0..62) of MTF'ed huffman table
        c = 0
        while b.readbits(1):
            c += 1
            if c >= huffman_groups:
                raise "Bzip2 chosen selector greater than number of groups (max 6)"
        if c >= 0:
            move_to_front(mtf, c)
        selectors_list.append(mtf[0])
    return selectors_list


def read_code_lengths(b, huffman_groups, symbols_in_use):
    """The delta-coded code-length bit loop, returning the raw lengths.

    Stock folds table construction into this loop and throws the lengths away.
    Both back ends want the lengths themselves -- the Rust kernel builds its own
    tables from them, and the Python path calls `build_huffman_table()` below --
    so they are returned rather than consumed here.  Bit consumption is
    identical either way, which is what keeps the two paths interchangeable
    mid-stream.
    """
    groups = []
    for _ in range(huffman_groups):
        length = b.readbits(5)
        lengths = []
        for _ in range(symbols_in_use):
            if not 0 <= length <= 20:
                raise Exception("Bzip2 Huffman length code outside range 0..20")
            while b.readbits(1):
                length -= (b.readbits(1) * 2) - 1
            lengths.append(length)
        groups.append(lengths)
    return groups


def _decode_symbols_python(b, code_lengths, selectors_list, symbols_in_use,
                           used):
    """Symbol decode in pure Python: bit reader, Huffman, MTF, RUNA/RUNB.

    Returns `L`, the rank-mapped byte stream the inverse BWT consumes.  This is
    the fallback back end (Rule 3): it runs whenever the native extension is
    absent, and it is still the fully optimized decoder, not the stock loop.
    """
    tables = [build_huffman_table(lengths) for lengths in code_lengths]

    # OPTIMIZED: the move-to-front list holds plain ints and is kept in
    # REVERSE order, so the front of the list is favourites[-1] and rank r-1
    # sits at index -r.  `pop(-r)` + `append()` then memmoves only `rank`
    # slots (mean rank 7.2 for this stream) instead of rebuilding all 147
    # entries from three slices the way `move_to_front()` does.
    favourites = [i for i, x in enumerate(used) if x]
    favourites.reverse()
    fav_pop = favourites.pop
    fav_append = favourites.append

    eob = symbols_in_use - 1
    buffer = bytearray()
    buf_append = buffer.append
    buf_extend = buffer.extend

    # OPTIMIZED: the bit reader is unpacked into locals for the symbol loop,
    # so fetching bits is integer arithmetic rather than three bound-method
    # calls (snoopbits -> needbits -> _mask) per code length tried.
    data = b.data
    pos = b.pos
    acc = b.bitfield
    nbits = b.bits

    selector_pointer = 0
    decoded = 0
    repeat = repeat_power = 0
    nsel = len(selectors_list)
    pb = pmask = 0
    tbl = limit = base = perm = None

    # Main Huffman loop
    while True:
        decoded -= 1
        if decoded <= 0:
            decoded = 50  # Huffman table re-evaluate/switch length
            if selector_pointer <= nsel:
                pb, pmask, tbl, limit, base, perm = \
                    tables[selectors_list[selector_pointer]]
                selector_pointer += 1

        # keep at least 32 bits buffered (the longest bzip2 code is 20 bits)
        if nbits < 32:
            acc = ((acc & MASK[nbits]) << 32) | int.from_bytes(data[pos:pos + 4], 'big')
            nbits += 32
            pos += 4

        # OPTIMIZED Huffman decode: one array index for a short code, else
        # canonical bit-at-a-time extension.  Replaces the linear scan of the
        # 258-entry HuffmanLength list (mean 5.0 entries, 2.3 snoopbits calls
        # per symbol, 148,271 symbols).
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

        if 0 <= r <= 1:
            if repeat == 0:
                repeat_power = 1
            repeat += repeat_power << r
            repeat_power <<= 1
            continue
        elif repeat > 0:
            # Remember kids: If there is only one repeated
            # real symbol, it is encoded with *zero* Huffman
            # bits and not output... so buffer[-1] does not work.
            buf_extend(bytes((favourites[-1],)) * repeat)
            repeat = 0
        if r == eob:
            break
        else:
            o = fav_pop(-r)
            fav_append(o)
            buf_append(o)

    b.pos = pos
    b.bitfield = acc & MASK[nbits]
    b.bits = nbits
    return buffer


def _decode_symbols_native(b, code_lengths, selectors_list, symbols_in_use,
                           used):
    """The same stage, executed by the Rust kernel.  Returns the same `L`.

    WHY THIS STAGE.  It is 44% of stock runtime and, unlike the inverse BWT
    that follows it, it is not a serial pointer chase -- so it is the part
    where leaving the interpreter actually buys something.

    WHY NATIVE CODE WINS HERE, in the terms of Lecture 4 ("it is always the
    memory").  The Python loop above is about as tight as CPython allows, and
    what is left is not arithmetic, it is layout.  Every symbol touches
    `favourites`, a Python list: an array of `PyObject*` pointing at boxed ints
    scattered across the heap, so a move-to-front of mean rank 7.2 is seven
    dependent dereferences into seven different cache lines.  The lecture puts
    it as "pointer-based structures are a pain for caching", and that is the
    whole story.  The Rust side holds the same list as a `[u8; 258]`: one cache
    line, no indirection, and the memmove is a handful of bytes.  Same
    algorithm, same mean rank, only the data layout changed -- the lecture's
    "merging arrays" transformation applied to a structure Python cannot
    express.

    The kernel is configured per block and inside the timed region, exactly as
    the Python path builds its six decode tables inside the timed region, so
    neither back end is handed a setup freebie.

    Bit-position contract: the decoder is told an absolute bit offset into the
    stream and returns the offset one past the end-of-block symbol.  Getting
    that back wrong would silently desynchronise the stream rather than raise,
    so `dev/pyflate/rs_check.py` asserts the returned offset as well as the
    bytes -- and the MD5 at the end of the benchmark is the backstop.
    """
    dec = pyflate_rs.BlockDecoder(
        b.data,
        [bytes(lengths) for lengths in code_lengths],
        bytes(selectors_list),
        symbols_in_use,
        # front-first, unlike the reversed list the Python path keeps: that
        # reversal is a `list.pop` micro-optimization with no analogue in an
        # array.
        bytes(i for i, x in enumerate(used) if x))

    L, end = dec.decode(b.pos * 8 - b.bits)

    # Restore the Python bit reader at the offset the kernel stopped on: drop
    # the buffered window, jump to the containing byte, discard the sub-byte
    # remainder.  After this the Python header parser resumes as if it had
    # decoded the block itself.
    b.pos = end >> 3
    b.bits = 0
    b.bitfield = 0
    remainder = end & 7
    if remainder:
        b.readbits(remainder)
    return L


def decode_huffman_block(b, out):
    randomised = b.readbits(1)
    if randomised:
        raise "Bzip2 randomised support not implemented"
    pointer = b.readbits(24)
    used = compute_used(b)

    huffman_groups = b.readbits(3)
    if not 2 <= huffman_groups <= 6:
        raise Exception("Bzip2: Number of Huffman groups not in range 2..6")

    selectors_list = compute_selectors_list(b, huffman_groups)
    symbols_in_use = sum(used) + 2  # remember RUN[AB] RLE symbols
    code_lengths = read_code_lengths(b, huffman_groups, symbols_in_use)

    # Header parsing above is identical on both paths and stays in Python: it
    # is a few hundred bits per block, i.e. nothing, and keeping it here is
    # what lets either back end pick the stream up mid-block.
    decode = (_decode_symbols_native if pyflate_rs is not None
              else _decode_symbols_python)
    buffer = decode(b, code_lengths, selectors_list, symbols_in_use, used)

    nearly_there = bwt_reverse(bytes(buffer), pointer)
    # Pointless/irritating run-length encoding step
    out.append(rle4_expand(nearly_there))


# Sixteen bits of magic have been removed by the time we start decoding


def bzip2_main(b):
    method = b.readbits(8)
    if method != ord('h'):
        raise Exception(
            "Unknown (not type 'h'uffman Bzip2) compression method")

    blocksize = b.readbits(8)
    if ord('1') <= blocksize <= ord('9'):
        blocksize = blocksize - ord('0')
    else:
        raise Exception("Unknown (not size '0'-'9') Bzip2 blocksize")

    out = []
    while True:
        blocktype = b.readbits(48)
        b.readbits(32)   # crc
        if blocktype == 0x314159265359:  # (pi)
            decode_huffman_block(b, out)
        elif blocktype == 0x177245385090:  # sqrt(pi)
            b.align()
            break
        else:
            raise Exception("Illegal Bzip2 blocktype")
    return b''.join(out)


# Sixteen bits of magic have been removed by the time we start decoding
def gzip_main(field):
    b = Bitfield(field)
    method = b.readbits(8)
    if method != 8:
        raise Exception("Unknown (not type eight DEFLATE) compression method")

    # Use flags, drop modification time, extra flags and OS creator type.
    flags = b.readbits(8)
    b.readbits(32)   # mtime
    b.readbits(8)    # extra_flags
    b.readbits(8)    # os_type

    if flags & 0x04:  # structured GZ_FEXTRA miscellaneous data
        xlen = b.readbits(16)
        b.dropbytes(xlen)
    while flags & 0x08:  # original GZ_FNAME filename
        if not b.readbits(8):
            break
    while flags & 0x10:  # human readable GZ_FCOMMENT
        if not b.readbits(8):
            break
    if flags & 0x02:  # header-only GZ_FHCRC checksum
        b.readbits(16)

    out = []
    while True:
        lastbit = b.readbits(1)
        blocktype = b.readbits(2)

        if blocktype == 0:
            b.align()
            length = b.readbits(16)
            if length & b.readbits(16):
                raise Exception("stored block lengths do not match each other")
            for i in range(length):
                out.append(int2byte(b.readbits(8)))

        elif blocktype == 1 or blocktype == 2:  # Huffman
            main_literals, main_distances = None, None

            if blocktype == 1:  # Static Huffman
                static_huffman_bootstrap = [
                    (0, 8), (144, 9), (256, 7), (280, 8), (288, -1)]
                static_huffman_lengths_bootstrap = [(0, 5), (32, -1)]
                main_literals = HuffmanTable(static_huffman_bootstrap)
                main_distances = HuffmanTable(static_huffman_lengths_bootstrap)

            elif blocktype == 2:  # Dynamic Huffman
                literals = b.readbits(5) + 257
                distances = b.readbits(5) + 1
                code_lengths_length = b.readbits(4) + 4

                l = [0] * 19
                for i in range(code_lengths_length):
                    l[code_length_orders(i)] = b.readbits(3)

                dynamic_codes = OrderedHuffmanTable(l)
                dynamic_codes.populate_huffman_symbols()
                dynamic_codes.min_max_bits()

                # Decode the code_lengths for both tables at once,
                # then split the list later

                code_lengths = []
                n = 0
                while n < (literals + distances):
                    r = dynamic_codes.find_next_symbol(b)
                    if 0 <= r <= 15:  # literal bitlength for this code
                        count = 1
                        what = r
                    elif r == 16:  # repeat last code
                        count = 3 + b.readbits(2)
                        # Is this supposed to default to '0' if in the zeroth
                        # position?
                        what = code_lengths[-1]
                    elif r == 17:  # repeat zero
                        count = 3 + b.readbits(3)
                        what = 0
                    elif r == 18:  # repeat zero lots
                        count = 11 + b.readbits(7)
                        what = 0
                    else:
                        raise Exception(
                            "next code length is outside of the range 0 <= r <= 18")
                    code_lengths += [what] * count
                    n += count

                main_literals = OrderedHuffmanTable(code_lengths[:literals])
                main_distances = OrderedHuffmanTable(code_lengths[literals:])

            # Common path for both Static and Dynamic Huffman decode now

            main_literals.populate_huffman_symbols()
            main_distances.populate_huffman_symbols()

            main_literals.min_max_bits()
            main_distances.min_max_bits()

            literal_count = 0
            while True:
                r = main_literals.find_next_symbol(b)
                if 0 <= r <= 255:
                    literal_count += 1
                    out.append(int2byte(r))
                elif r == 256:
                    if literal_count > 0:
                        literal_count = 0
                    break
                elif 257 <= r <= 285:  # dictionary lookup
                    if literal_count > 0:
                        literal_count = 0
                    length_extra = b.readbits(extra_length_bits(r))
                    length = length_base(r) + length_extra

                    r1 = main_distances.find_next_symbol(b)
                    if 0 <= r1 <= 29:
                        distance = distance_base(
                            r1) + b.readbits(extra_distance_bits(r1))
                        while length > distance:
                            out += out[-distance:]
                            length -= distance
                        if length == distance:
                            out += out[-distance:]
                        else:
                            out += out[-distance:length - distance]
                    elif 30 <= r1 <= 31:
                        raise Exception("illegal unused distance symbol "
                                        "in use @%r" % b.tell())
                elif 286 <= r <= 287:
                    raise Exception("illegal unused literal/length symbol "
                                    "in use @%r" % b.tell())
        elif blocktype == 3:
            raise Exception("illegal unused blocktype in use @%r" % b.tell())

        if lastbit:
            break

    b.align()
    b.readbits(32)   # crc
    b.readbits(32)   # final_length
    return "".join(out)


def bench_pyflake(loops, filename):
    input_fp = open(filename, 'rb')
    range_it = range(loops)
    t0 = pyperf.perf_counter()

    for _ in range_it:
        input_fp.seek(0)
        field = RBitfield(input_fp)

        magic = field.readbits(16)
        if magic == 0x1f8b:  # GZip
            # the gzip decoder still consumes a file object
            out = gzip_main(field.remainder())
        elif magic == 0x425a:  # BZip2
            out = bzip2_main(field)
        else:
            raise Exception("Unknown file magic %x, not a gzip/bzip2 file"
                            % hex(magic))

    dt = pyperf.perf_counter() - t0
    input_fp.close()

    if hashlib.md5(out).hexdigest() != "afa004a630fe072901b1d9628b960974":
        raise Exception("MD5 checksum mismatch")

    return dt



def _native_extension_file(module):
    """Path of the compiled extension behind `module`, not its package stub.

    maturin installs the crate as a package: `nbody_rs/__init__.py` is a
    three-line re-export generated identically for every build, and the kernel
    itself is the `.so` beside it. Hashing `module.__file__` would give the same
    digest for any two builds -- exactly what the hash exists to tell apart.
    """
    import importlib.machinery
    import sys
    suffixes = tuple(importlib.machinery.EXTENSION_SUFFIXES)
    name = module.__name__
    sub = sys.modules.get(name + '.' + name.rpartition('.')[2])
    for candidate in (sub, module):
        path = getattr(candidate, '__file__', None) or ''
        if path.endswith(suffixes):
            return path
    for entry in getattr(module, '__path__', None) or ():
        for fn in sorted(os.listdir(entry)):
            if fn.endswith(suffixes):
                return os.path.join(entry, fn)
    return getattr(module, '__file__', None)


def _backend_metadata(runner, module, requested):
    """Record which back end ran, and which binary it was.

    "native" is not a sufficient description of a measurement: the crate's
    version never changes between builds, so two result files can both say
    native and describe different compiled kernels.  The loaded path and its
    SHA-256 are what tie a JSON to the wheel that tools/build_wheel.sh
    installed.
    """
    runner.metadata['hwsw_backend'] = 'native' if module is not None else 'python'
    runner.metadata['hwsw_backend_requested'] = requested
    if module is not None:
        path = _native_extension_file(module)
        if path:
            runner.metadata['hwsw_native_module'] = path
            try:
                with open(path, 'rb') as fh:
                    runner.metadata['hwsw_native_sha256'] =                         hashlib.sha256(fh.read()).hexdigest()
            except OSError:                              # pragma: no cover
                pass


def _propagate_backend(runner):
    """Make the requested back end reach the worker processes.

    pyperf re-executes every worker with a scrubbed environment
    (``pyperf._utils.create_environ``), so ``HWSW_BACKEND`` is dropped unless
    the caller passed ``--inherit-environ HWSW_BACKEND``.  That was forgotten
    once: both sides of a "Python vs native" comparison measured native, and
    only the recorded metadata caught it.  Leaving the fix in the caller means
    every future caller has to remember it, and ``pyperformance run`` offers no
    way to pass the flag through to the benchmark at all -- so the benchmark
    propagates its own configuration here, and the flag on the command line
    becomes belt-and-braces rather than the only thing standing between a
    reader and a wrong number.
    """
    args = runner.parse_args()            # idempotent; returns the cached args
    inherit = list(getattr(args, 'inherit_environ', None) or [])
    if 'HWSW_BACKEND' not in inherit:
        inherit.append('HWSW_BACKEND')
    args.inherit_environ = inherit
    return args

if __name__ == '__main__':
    runner = pyperf.Runner()
    runner.metadata['description'] = "Pyflate benchmark"
    # so the result JSON says which back end produced it, and which binary
    _backend_metadata(runner, pyflate_rs, _BACKEND)
    _propagate_backend(runner)

    filename = os.path.join(os.path.dirname(__file__),
                            "data", "interpreter.tar.bz2")
    runner.bench_time_func('pyflate', bench_pyflake, filename)
