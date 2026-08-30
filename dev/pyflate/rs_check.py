"""Correctness + speed check for the Rust/PyO3 `pyflate_rs` symbol-decode kernel.

Run inside WSL after `maturin build --release` and installing the wheel:

    /root/hwsw-env/py310/bin/python dev/pyflate/rs_check.py
    /root/hwsw-env/py310/bin/python dev/pyflate/rs_check.py --trace /tmp/block0.pft

The claim being tested is BYTE-EXACTNESS, at two levels:

  1. Kernel level.  For every block of the shipped `interpreter.tar.bz2`, the
     `L` vector (the BWT input) returned by `pyflate_rs.BlockDecoder.decode()`
     must be `==` to the `bytearray` the Python T3 symbol loop accumulates for
     the same block from the same starting bit offset, and the returned end bit
     position must be identical too.  A wrong end position would desynchronise
     the stream, so checking it is not redundant.

  2. Pipeline level.  Feeding the Rust `L` onward through the UNMODIFIED Python
     `bwt_reverse` + `rle4_expand` must reproduce all 399,360 output bytes
     exactly, checked against CPython's own `bz2.decompress` and against the
     benchmark's MD5 `afa004a630fe072901b1d9628b960974`.

Both are proven here rather than asserted in a docstring; the script prints
either result.  The speed section is deliberately reported twice -- once for
the kernel alone and once end to end -- because the end-to-end number is capped
by the inverse BWT and RLE4 that stay in Python, and the honest framing of this
crate is the Amdahl one.
"""
import argparse
import bz2
import gc
import hashlib
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import pyflate_rs                                            # noqa: E402
import t1_micro                                              # noqa: E402
import t3_table                                              # noqa: E402

try:
    import t0_stock                                          # noqa: E402
except Exception:                                            # pragma: no cover
    t0_stock = None

DATA = os.path.join(ROOT, "benchmarks", "bm_pyflate", "data",
                    "interpreter.tar.bz2")
MD5 = "afa004a630fe072901b1d9628b960974"
MASK = [(1 << i) - 1 for i in range(65)]
PAD = b"\x00" * 8


# --------------------------------------------------------------------------
# Bit-position helpers.  The kernel's contract is stated in absolute bits into
# the compressed buffer, so both sides need to convert to and from that.
# --------------------------------------------------------------------------

def bit_pos(field):
    """Absolute bit offset of the next unconsumed bit of an RBitfield."""
    return field.pos * 8 - field.bits


def seek_bits(field, bp):
    """Reposition an RBitfield at absolute bit offset `bp`.

    This is exactly the restore sequence documented on `BlockDecoder.decode`:
    drop the buffered window, jump to the containing byte, discard the sub-byte
    remainder.
    """
    field.pos = bp >> 3
    field.bits = 0
    field.bitfield = 0
    r = bp & 7
    if r:
        field.readbits(r)


# --------------------------------------------------------------------------
# Header parsing -- the part that STAYS in Python in both configurations.
# --------------------------------------------------------------------------

def read_code_lengths(b, huffman_groups, symbols_in_use):
    """The delta-coded code-length bit loop, returning the raw lengths.

    `t3_table.compute_tables` folds table construction into this loop and
    throws the lengths away; the Rust kernel wants the lengths themselves (it
    builds its own tables), so this returns them and the caller builds the
    Python tables separately.  Same bit consumption either way.
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


def parse_blocks(raw):
    """Walk the stream's block structure, collecting one descriptor per block.

    Everything here is header work that both the pure-Python tier and the
    hybrid tier run identically.  Advancing past a block's symbol data requires
    decoding it, so the Python symbol loop is used for that -- which also gives
    us the reference `L` and end position for free.
    """
    data = raw + PAD
    field = t1_micro.RBitfield(data)
    if field.readbits(16) != 0x425a:
        raise Exception("not bzip2")
    if field.readbits(8) != 0x68:
        raise Exception("unknown compression method")
    blocksize = field.readbits(8)
    if not (0x31 <= blocksize <= 0x39):
        raise Exception("unknown blocksize")

    blocks = []
    while True:
        blocktype = field.readbits(48)
        field.readbits(32)  # crc
        if blocktype == 0x314159265359:
            if field.readbits(1):
                raise Exception("randomised blocks not supported")
            pointer = field.readbits(24)
            used = t1_micro.compute_used(field)
            huffman_groups = field.readbits(3)
            if not 2 <= huffman_groups <= 6:
                raise Exception("Huffman groups not in 2..6")
            selectors = t1_micro.compute_selectors_list(field, huffman_groups)
            symbols_in_use = sum(used) + 2
            code_lengths = read_code_lengths(field, huffman_groups,
                                             symbols_in_use)
            favourites = [i for i, x in enumerate(used) if x]
            tables = [t3_table.build_table(l) for l in code_lengths]
            start = bit_pos(field)

            L, end = py_decode_symbols(data, start, tables, selectors,
                                       symbols_in_use, favourites)
            blocks.append(dict(pointer=pointer, selectors=selectors,
                               symbols_in_use=symbols_in_use,
                               code_lengths=code_lengths,
                               favourites=favourites, tables=tables,
                               start=start, end=end, L=L))
            seek_bits(field, end)
        elif blocktype == 0x177245385090:
            field.align()
            break
        else:
            raise Exception("illegal blocktype")
    return blocks


# --------------------------------------------------------------------------
# The Python side of the boundary: the T3 symbol loop with the BWT/RLE4 tail
# removed, so the two sides of the comparison span exactly the same work.
#
# The body below is `t3_table.decode_huffman_block`'s main loop verbatim; only
# the header parsing before it and the bwt/rle4 after it are lifted out.
# --------------------------------------------------------------------------

def py_decode_symbols(data, bitp, tables, selectors_list, symbols_in_use,
                      favourites):
    """-> (L, end_bit_pos).  Pure Python; the thing the Rust kernel replaces."""
    fav = list(favourites)
    fav.reverse()                       # front of the MTF list is fav[-1]
    fav_pop = fav.pop
    fav_append = fav.append

    eob = symbols_in_use - 1
    buffer = bytearray()
    buf_append = buffer.append
    buf_extend = buffer.extend
    mask = MASK

    # Prime the bit window at `bitp`.
    pos = bitp >> 3
    chunk = data[pos:pos + 4]
    acc = int.from_bytes(chunk, 'big')
    nbits = len(chunk) << 3
    pos += len(chunk)
    skip = bitp & 7
    nbits -= skip
    acc &= mask[nbits]

    selector_pointer = 0
    nsel = len(selectors_list)
    repeat = repeat_power = 0
    pb = pmask = 0
    tbl = limit = base = perm = None
    decoded = 0

    while True:
        decoded -= 1
        if decoded <= 0:
            decoded = 50
            if selector_pointer <= nsel:
                pb, pmask, tbl, _minLen, limit, base, perm = \
                    tables[selectors_list[selector_pointer]]
                selector_pointer += 1

        if nbits < 32:
            chunk = data[pos:pos + 4]
            acc = ((acc & mask[nbits]) << (len(chunk) << 3)) | int.from_bytes(chunk, 'big')
            nbits += len(chunk) << 3
            pos += len(chunk)

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

    return bytes(buffer), pos * 8 - nbits


# --------------------------------------------------------------------------
# Whole-file decompressors, so the end-to-end A/B is like for like.
# --------------------------------------------------------------------------

def py_decompress(raw):
    """Pure Python T3 (what the landed benchmark does), from a bytes buffer."""
    field = t3_table.RBitfield(raw + PAD)
    if field.readbits(16) != 0x425a:
        raise Exception("not bzip2")
    return t3_table.bzip2_main(field)


def hybrid_decompress(raw):
    """Rust symbol decode; every other stage still Python.

    Self-contained on purpose: the `BlockDecoder` is configured inside the
    timed region, so this measures exactly the same stages as `py_decompress`
    (which builds its six Python decode tables inside its own timed region).
    Hoisting the config out would hand the hybrid a ~1% freebie.
    """
    data = raw + PAD
    field = t1_micro.RBitfield(data)
    field.readbits(16)
    field.readbits(8)
    field.readbits(8)
    out = []
    while True:
        blocktype = field.readbits(48)
        field.readbits(32)
        if blocktype == 0x314159265359:
            field.readbits(1)
            pointer = field.readbits(24)
            used = t1_micro.compute_used(field)
            groups = field.readbits(3)
            selectors = t1_micro.compute_selectors_list(field, groups)
            symbols_in_use = sum(used) + 2
            code_lengths = read_code_lengths(field, groups, symbols_in_use)
            dec = pyflate_rs.BlockDecoder(
                raw, [bytes(l) for l in code_lengths], bytes(selectors),
                symbols_in_use, bytes(i for i, x in enumerate(used) if x))
            L, end = dec.decode(bit_pos(field))
            seek_bits(field, end)
            out.append(t3_table.rle4_expand(t3_table.bwt_reverse(L, pointer)))
        elif blocktype == 0x177245385090:
            field.align()
            break
        else:
            raise Exception("illegal blocktype")
    return b"".join(out)


# --------------------------------------------------------------------------

def interleave(cases, rounds):
    """Round-robin best-of-N over a dict of named callables.

    Interleaved rather than one-function-at-a-time on purpose: this dev box is
    a hybrid-core laptop under WSL2 and a plain sequential min-of-7 was
    observed to give the SAME function 42 ms in one script and 92 ms in
    another.  Running every case once per round makes frequency drift and
    scheduling noise hit all of them equally; the min then picks the
    least-disturbed round for each.
    """
    best = {k: float("inf") for k in cases}
    for _ in range(rounds):
        for k, fn in cases.items():
            gc.collect()
            gc.disable()
            t = time.perf_counter()
            fn()
            best[k] = min(best[k], time.perf_counter() - t)
            gc.enable()
    return best


def check_trace(path, blk, L):
    """Read back a golden trace and validate it against the block we know."""
    with open(path, "rb") as fp:
        buf = fp.read()
    magic = buf[:8]
    ver, n_sym, n_out, alpha = struct.unpack_from("<4I", buf, 8)
    bp0, bp1 = struct.unpack_from("<2Q", buf, 24)
    off = 40
    syms = struct.unpack_from("<%dH" % n_sym, buf, off)
    off += 2 * n_sym
    lens = buf[off:off + n_sym]
    off += n_sym
    grps = buf[off:off + n_sym]
    off += n_sym
    payload = buf[off:off + n_out]
    ok = (magic == b"PFTRACE1" and ver == 1 and payload == L
          and bp0 == blk["start"] and bp1 == blk["end"]
          and alpha == blk["symbols_in_use"]
          and syms[-1] == blk["symbols_in_use"] - 1
          and all(g == blk["selectors"][i // 50] for i, g in enumerate(grps))
          and sum(lens) == bp1 - bp0
          and off + n_out == len(buf))
    return ok, dict(n_sym=n_sym, n_out=n_out, bits=bp1 - bp0,
                    mean_len=sum(lens) / n_sym, size=len(buf))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int,
                    default=int(os.environ.get("PYFLATE_ROUNDS", "9")))
    ap.add_argument("--trace", metavar="PATH",
                    help="write the golden reference vector for block 0 here")
    args = ap.parse_args()

    with open(DATA, "rb") as fp:
        raw = fp.read()
    ref = bz2.decompress(raw)
    print("python %s | rounds=%d" % (sys.version.split()[0], args.rounds))
    print("input %d bytes -> %d bytes, md5 %s"
          % (len(raw), len(ref), hashlib.md5(ref).hexdigest()))

    blocks = parse_blocks(raw)
    print("blocks: %d" % len(blocks))

    # ---- correctness, kernel level ---------------------------------------
    print("\n--- kernel byte-exactness (Rust vs Python T3 symbol loop) ---")
    decoders = []
    all_ok = True
    for i, blk in enumerate(blocks):
        dec = pyflate_rs.BlockDecoder(raw, [bytes(l) for l in blk["code_lengths"]],
                                      bytes(blk["selectors"]),
                                      blk["symbols_in_use"],
                                      bytes(blk["favourites"]))
        decoders.append(dec)
        L, end = dec.decode(blk["start"])
        same = (L == blk["L"])
        endsame = (end == blk["end"])
        all_ok &= same and endsame
        print("  block %d: %s  L identical: %-5s (%d bytes)  end bit pos: %-5s "
              "(%d, %d bits of stream)"
              % (i, dec, same, len(L), endsame, end, end - blk["start"]))
        if not same:
            n = min(len(L), len(blk["L"]))
            first = next((k for k in range(n) if L[k] != blk["L"][k]), n)
            print("     FIRST DIFFERENCE at byte %d; lengths %d (rs) vs %d (py)"
                  % (first, len(L), len(blk["L"])))

    # ---- correctness, pipeline level -------------------------------------
    print("\n--- pipeline byte-exactness (Rust kernel + Python BWT/RLE4) ---")
    py_out = py_decompress(raw)
    hy_out = hybrid_decompress(raw)
    md5_hy = hashlib.md5(hy_out).hexdigest()
    print("  pure Python T3 == bz2.decompress : %s" % (py_out == ref,))
    print("  hybrid         == bz2.decompress : %s" % (hy_out == ref,))
    print("  hybrid         == pure Python T3 : %s" % (hy_out == py_out,))
    print("  hybrid md5 %s == benchmark md5 : %s" % (md5_hy, md5_hy == MD5))
    all_ok &= (hy_out == ref) and (md5_hy == MD5)
    print("\n  ALL CORRECTNESS CHECKS PASS: %s" % all_ok)

    # ---- golden trace ----------------------------------------------------
    if args.trace:
        blk = blocks[0]
        n_sym, n_out, end = decoders[0].trace(blk["start"], args.trace)
        ok, info = check_trace(args.trace, blk, blk["L"])
        print("\n--- golden trace ---")
        print("  wrote %s (%d bytes)" % (args.trace, info["size"]))
        print("  %d Huffman symbols (incl. EOB), %d output bytes, %d stream bits"
              % (info["n_sym"], info["n_out"], info["bits"]))
        print("  mean code length %.2f bits" % info["mean_len"])
        print("  self-check (magic, group schedule, bit accounting, payload): %s"
              % ok)
        all_ok &= ok

    # ---- speed -----------------------------------------------------------
    blk, dec = blocks[0], decoders[0]
    data = raw + PAD
    L = blk["L"]
    nt = t3_table.bwt_reverse(L, blk["pointer"])
    cl = [bytes(l) for l in blk["code_lengths"]]
    sel = bytes(blk["selectors"])
    fav = bytes(blk["favourites"])

    cases = {
        "sym_py": lambda: py_decode_symbols(data, blk["start"], blk["tables"],
                                            blk["selectors"],
                                            blk["symbols_in_use"],
                                            blk["favourites"]),
        "sym_rs": lambda: dec.decode(blk["start"]),
        "bwt": lambda: t3_table.bwt_reverse(L, blk["pointer"]),
        "rle4": lambda: t3_table.rle4_expand(nt),
        "header": lambda: parse_header_only(raw, blocks),
        "e2e_py": lambda: py_decompress(raw),
        "e2e_hy": lambda: hybrid_decompress(raw),
        "config": lambda: pyflate_rs.BlockDecoder(raw, cl, sel,
                                                  blk["symbols_in_use"], fav),
    }
    if t0_stock is not None:
        cases["e2e_t0"] = lambda: t0_stock.decompress(DATA)

    t = interleave(cases, args.rounds)

    print("\n--- symbol-decode kernel, min of %d interleaved rounds ---"
          % args.rounds)
    print("  Python T3 symbol loop : %8.3f ms" % (t["sym_py"] * 1e3))
    print("  Rust  pyflate_rs      : %8.3f ms" % (t["sym_rs"] * 1e3))
    print("  KERNEL SPEEDUP        : %8.1fx" % (t["sym_py"] / t["sym_rs"]))

    print("\n--- stages that stay in Python ---")
    print("  inverse BWT           : %8.3f ms" % (t["bwt"] * 1e3))
    print("  RLE4 expand           : %8.3f ms" % (t["rle4"] * 1e3))
    print("  header + table build  : %8.3f ms" % (t["header"] * 1e3))
    print("  (sum of the three)    : %8.3f ms"
          % ((t["bwt"] + t["rle4"] + t["header"]) * 1e3))

    print("\n--- end to end ---")
    print("  pure Python T3        : %8.3f ms" % (t["e2e_py"] * 1e3))
    print("  hybrid (Rust kernel)  : %8.3f ms" % (t["e2e_hy"] * 1e3))
    print("  END-TO-END SPEEDUP    : %8.2fx"
          % (t["e2e_py"] / t["e2e_hy"]))
    if "e2e_t0" in t:
        print("  T0 stock (context)    : %8.3f ms  -> T3 %.2fx, hybrid %.2fx"
              % (t["e2e_t0"] * 1e3, t["e2e_t0"] / t["e2e_py"],
                 t["e2e_t0"] / t["e2e_hy"]))

    # Amdahl.  The residual is taken from the MEASURED hybrid run minus the
    # measured kernel, not by subtracting one configuration's part from
    # another's total -- the two configurations allocate differently and mixing
    # them produces a cap the measurement can appear to beat.
    residual = t["e2e_hy"] - t["sym_rs"]
    print("\n  Amdahl:")
    print("    symbol loop is %.1f%% of the pure-Python decode"
          % (100.0 * t["sym_py"] / t["e2e_py"]))
    print("    Python left in the hybrid: %.3f ms (BWT %.0f%% + RLE4 %.0f%% + header/join)"
          % (residual * 1e3, 100.0 * t["bwt"] / residual,
             100.0 * t["rle4"] / residual))
    print("    CAP with an infinitely fast kernel: %.2fx"
          % (t["e2e_py"] / residual))
    print("    achieved: %.2fx  (%.0f%% of the cap)"
          % (t["e2e_py"] / t["e2e_hy"],
             100.0 * (t["e2e_py"] / t["e2e_hy"]) / (t["e2e_py"] / residual)))

    # ---- boundary cost ---------------------------------------------------
    n = 200000
    tt = time.perf_counter()
    for _ in range(n):
        dec.num_groups
    per = (time.perf_counter() - tt) / n
    print("\n  FFI crossing cost (attribute getter, %d calls): %.0f ns" % (n, per * 1e9))
    print("  -> %.2e of one decode() call" % (per / t["sym_rs"],))
    print("  config build BlockDecoder(...) : %.3f ms, i.e. %.1f%% of one decode"
          % (t["config"] * 1e3, 100.0 * t["config"] / t["sym_rs"]))

    return 0 if all_ok else 1


def parse_header_only(raw, blocks):
    """Header + selector + code-length + table-build work for the whole file.

    Uses the already-known end offsets so it does not decode symbols; this is
    the Python cost that neither tier can remove.
    """
    data = raw + PAD
    field = t1_micro.RBitfield(data)
    field.readbits(16)
    field.readbits(8)
    field.readbits(8)
    i = 0
    while True:
        blocktype = field.readbits(48)
        field.readbits(32)
        if blocktype == 0x314159265359:
            field.readbits(1)
            field.readbits(24)
            used = t1_micro.compute_used(field)
            groups = field.readbits(3)
            t1_micro.compute_selectors_list(field, groups)
            symbols_in_use = sum(used) + 2
            cl = read_code_lengths(field, groups, symbols_in_use)
            for l in cl:
                t3_table.build_table(l)
            seek_bits(field, blocks[i]["end"])
            i += 1
        elif blocktype == 0x177245385090:
            field.align()
            break
        else:
            raise Exception("illegal blocktype")


if __name__ == "__main__":
    sys.exit(main())
