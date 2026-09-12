"""Per-phase CPI stack for pyflate: run one pipeline stage under `perf stat`.

The report claims `bwt_reverse` is "a 399 KB data-dependent pointer chase" and
builds the whole processing-in-memory argument of section 5c on it. Until now
that was read off the source (`end = T[end]` in a loop), never measured -- we
believed the guest PMU could not sample. It can (see the appendix report), so
the claim is now testable, and Lecture 4 is explicit that this is the half a
flame graph cannot give you: the graph says *where*, the counters say *why*.

Each phase runs in its own process so `perf stat` attributes cleanly. Setup is
done once and the phase is repeated `--repeat` times so it dominates.

Usage (4 events is the guest's general-purpose counter budget -- ask for more
in one pass and the vPMU returns 0 for the losers rather than multiplexing):

    perf stat -e cycles:u,instructions:u,cache-references,cache-misses -- \\
        python3 phase_cpi.py --phase bwt --repeat 20

Phases:
    decode  bit reader + canonical Huffman + MTF + RUNA/RUNB  (native if built)
    bwt     the inverse Burrows-Wheeler transform, whole
    chase   ONLY the `end = T[end]` dependent-load loop, with the T table
            built beforehand -- this is the one the report's claim is about
    rle4    the final run-length expansion
"""
import argparse
import importlib.util
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BM = os.path.join(ROOT, "benchmarks", "bm_pyflate", "run_benchmark.py")
DATA = os.path.join(ROOT, "benchmarks", "bm_pyflate", "data",
                    "interpreter.tar.bz2")


def load_benchmark():
    spec = importlib.util.spec_from_file_location("bm_pyflate", BM)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def first_block(m, raw):
    """Header-parse up to the symbol data and return the decode inputs.

    Mirrors `bzip2_main` exactly, but stops at the block payload so each phase
    can be driven on its own.
    """
    field = m.RBitfield(raw)
    if field.readbits(16) != 0x425A:
        raise SystemExit("not a bzip2 stream")
    if field.readbits(8) != ord("h"):
        raise SystemExit("unknown compression method")
    blocksize = field.readbits(8)
    if not 0x31 <= blocksize <= 0x39:
        raise SystemExit("unknown blocksize")

    blocktype = field.readbits(48)
    field.readbits(32)                     # crc
    if blocktype != 0x314159265359:
        raise SystemExit("expected a data block first")
    if field.readbits(1):
        raise SystemExit("randomised blocks not supported")

    pointer = field.readbits(24)
    used = m.compute_used(field)
    groups = field.readbits(3)
    selectors = m.compute_selectors_list(field, groups)
    symbols_in_use = sum(used) + 2
    code_lengths = m.read_code_lengths(field, groups, symbols_in_use)
    return field, pointer, used, groups, selectors, symbols_in_use, code_lengths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True,
                    choices=("decode", "bwt", "chase", "rle4"))
    ap.add_argument("--repeat", type=int, default=20)
    args = ap.parse_args()

    m = load_benchmark()
    raw = open(DATA, "rb").read()
    field, pointer, used, groups, sel, siu, lengths = first_block(m, raw)

    # Capture each phase's input once, outside the repeat loop.
    bit_start = field.pos * 8 - field.bits
    decode = (m._decode_symbols_native if m.pyflate_rs is not None
              else m._decode_symbols_python)

    def fresh_field():
        f = m.RBitfield(raw)
        f.pos, f.bits, f.bitfield = bit_start >> 3, 0, 0
        r = bit_start & 7
        if r:
            f.readbits(r)
        return f

    L = bytes(decode(fresh_field(), lengths, sel, siu, used))
    # Only materialise the RLE4 input when that is the phase under test: the
    # inverse BWT costs ~140 ms, which would otherwise land inside perf stat
    # and swamp the 3 ms decode phase it is supposed to be compared against.
    nearly = m.bwt_reverse(L, pointer) if args.phase == "rle4" else None

    if args.phase == "decode":
        work = lambda: decode(fresh_field(), lengths, sel, siu, used)
        size = len(L)
    elif args.phase == "bwt":
        work = lambda: m.bwt_reverse(L, pointer)
        size = len(L)
    elif args.phase == "chase":
        # bwt_reverse is bwt_transform() + the chase. The transform is an O(n)
        # counting sort: sequential, allocation-heavy, and nothing like a
        # pointer chase, so leaving it in dilutes exactly the thing under test.
        # Hoist it out and time only the dependent-load loop.
        T = m.bwt_transform(L)
        n = len(L)

        def _chase(T=T, L=L, n=n, start=pointer):
            end = start
            out = bytearray(n)
            for i in range(n):
                end = T[end]
                out[i] = L[end]
            return out
        work = _chase
        size = len(L)
    else:
        work = lambda: m.rle4_expand(nearly)
        size = len(nearly)

    sys.stderr.write("phase=%s backend=%s repeat=%d working set=%d bytes\n"
                     % (args.phase,
                        "native" if m.pyflate_rs is not None else "python",
                        args.repeat, size))
    t0 = time.perf_counter()
    for _ in range(args.repeat):
        work()
    dt = time.perf_counter() - t0
    sys.stderr.write("phase wall time: %.4f s total, %.4f s per iteration\n"
                     % (dt, dt / args.repeat))


if __name__ == "__main__":
    main()
