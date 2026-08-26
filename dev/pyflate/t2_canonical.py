"""T2 -- canonical-Huffman decode (the zlib / libbzip2 `hbCreateDecodeTables`
scheme) replacing the linear scan over the 258-entry HuffmanLength list.

Everything else is inherited from T1, so the T1 -> T2 delta isolates the
Huffman decode strategy.

Per table we precompute, for each code length l in [minLen, maxLen]:
    limit[l] : the largest l-bit canonical code that is actually assigned
    base[l]  : offset such that  perm[code - base[l]]  is the symbol
    perm[]   : symbols in canonical order (sorted by (length, symbol))

Decode: read minLen bits, then extend ONE bit at a time while the value is
greater than limit[l].  That is O(len - minLen) integer compares -- with the
measured mean code length of 3.59 bits and minLen 2, ~2.6 iterations per
symbol -- versus the stock scan's mean of 5.0 object-attribute iterations plus
2.3 bound-method `snoopbits` calls.

The bit reader is also inlined into the symbol loop here: the canonical decode
is only worth anything if fetching one more bit is an integer shift rather than
a bound-method call.  (`ablate.py` measures the two halves separately.)
"""

from t1_micro import (RBitfield, compute_used, compute_selectors_list,   # noqa: F401
                      bwt_reverse, bwt_transform, rle4_expand, move_to_front)

NAME = "T2 canonical"

MASK = [(1 << i) - 1 for i in range(65)]


def build_canonical(lengths):
    """lengths[sym] -> code length.  Returns (minLen, maxLen, limit, base, perm).

    Identical code assignment to the stock `populate_huffman_symbols`:
    codes are handed out in increasing (length, symbol) order starting at 0,
    shifting left by the length increment at each new length.
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
        # first code of length l is (vec - count[l]) and it maps to perm[cum]
        base[l] = (vec - count[l]) - cum
        cum += count[l]
        vec <<= 1
    return minLen, maxLen, limit, base, perm


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
        tables.append(build_canonical(lengths))
    return tables


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

    # --- pull the bit reader into locals --------------------------------
    data = b.data
    pos = b.pos
    acc = b.bitfield
    nbits = b.bits
    ln = len(data)
    mask = MASK

    selector_pointer = 0
    nsel = len(selectors_list)
    repeat = repeat_power = 0
    minLen = maxLen = 0
    limit = base = perm = None
    decoded = 0

    while True:
        decoded -= 1
        if decoded <= 0:
            decoded = 50
            if selector_pointer <= nsel:
                minLen, maxLen, limit, base, perm = \
                    tables[selectors_list[selector_pointer]]
                selector_pointer += 1

        # ---- refill: keep >= 32 bits buffered (max code length is 20) ---
        if nbits < 32:
            chunk = data[pos:pos + 4]
            k = len(chunk)
            if k:
                acc = ((acc & mask[nbits]) << (k << 3)) | int.from_bytes(chunk, 'big')
                nbits += k << 3
                pos += k
            elif nbits <= 0:
                raise Exception("Length Error")

        # ---- canonical Huffman decode -----------------------------------
        zn = minLen
        zvec = (acc >> (nbits - zn)) & mask[zn]
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

    # --- write the bit reader state back --------------------------------
    b.pos = pos
    b.bitfield = acc & mask[nbits]
    b.bits = nbits

    nt = bwt_reverse(bytes(buffer), pointer)
    out.append(rle4_expand(nt))


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
        data = fp.read()
    field = RBitfield(data)
    if field.readbits(16) != 0x425a:
        raise Exception("not bzip2")
    return bzip2_main(field)
