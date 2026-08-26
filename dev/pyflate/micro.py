"""Micro-benchmarks for the individual candidate primitives, run on the REAL
intermediate data taken from the benchmark's own block (not synthetic input).

  * BWT histogram: sorted() (stock) vs Counter vs 256x bytes.count
  * BWT T-vector fill: plain vs packed (T[i]<<8 | L[T[i]]) one-lookup walk
  * BWT chain walk: list.append+bytes vs preallocated bytearray vs packed
  * RLE4 expansion: per-byte slicing (stock) vs regex span copy
  * MTF: stock 3-slice vs insert(0,pop(c)) vs reversed pop(-r)/append

Usage: <python> dev/pyflate/micro.py
"""
import collections
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import t1_micro as T1                                        # noqa: E402

DATA = os.path.normpath(os.path.join(
    HERE, '..', '..', 'benchmarks', 'bm_pyflate', 'data', 'interpreter.tar.bz2'))


def capture():
    """Run the decoder once, capturing the real BWT input L / pointer and the
    real post-BWT byte string that the RLE4 stage sees."""
    box = {}
    orig = T1.bwt_reverse

    def spy(L, end):
        box['L'] = L
        box['end'] = end
        nt = orig(L, end)
        box['nt'] = nt
        return nt
    T1.bwt_reverse = spy
    T1.decompress(DATA)
    T1.bwt_reverse = orig
    return box


def timeit(label, fn, n=7):
    ts = []
    r = None
    for _ in range(n):
        t = time.perf_counter()
        r = fn()
        ts.append(time.perf_counter() - t)
    print("   %-46s %8.2f ms" % (label, min(ts) * 1000))
    return r


def main():
    box = capture()
    L, end, nt = box['L'], box['end'], box['nt']
    n = len(L)
    print("BWT input L: %d bytes, pointer %d ; post-BWT nt: %d bytes"
          % (n, end, len(nt)))

    print("\n-- histogram of L (256 bins) --")
    a = timeit("stock: bytes(sorted(L)) + 256 x F.find()", lambda: stock_base(L))
    b = timeit("collections.Counter(L)", lambda: counter_base(L))
    c = timeit("[L.count(i) for i in range(256)]", lambda: count_base(L))
    assert a == b == c, (a[:8], b[:8], c[:8])

    print("\n-- T-vector fill (400k iterations) --")
    base0 = count_base(L)
    T = timeit("plain  T[b] = i", lambda: fill_plain(L, list(base0)))
    C = timeit("packed C[b] = (i<<8)|sym", lambda: fill_packed(L, list(base0)))

    print("\n-- inverse-BWT chain walk --")
    w1 = timeit("stock: list.append(L[end]) + bytes()", lambda: walk_list(L, T, end))
    w2 = timeit("bytearray slot assign", lambda: walk_ba(L, T, end))
    w3 = timeit("packed single-lookup walk", lambda: walk_packed(C, end))
    assert w1 == w2 == w3

    print("\n-- RLE4 expansion --")
    r1 = timeit("stock: per-byte slice + join", lambda: T1.rle4_expand(nt))
    r2 = timeit("regex span copy", lambda: rle4_re(nt))
    assert r1 == r2, (len(r1), len(r2))

    print("\n-- move-to-front, 89837 calls, real rank distribution --")
    ranks = capture_ranks()
    print("   (mean rank %.2f, p50 %d, list length 147)"
          % (sum(ranks) / len(ranks), sorted(ranks)[len(ranks) // 2]))
    timeit("stock 3-slice l[:] = l[c:c+1]+l[:c]+l[c+1:]", lambda: mtf_stock(ranks))
    timeit("l.insert(0, l.pop(c))", lambda: mtf_popinsert(ranks))
    timeit("reversed list: l.append(l.pop(-1-c))", lambda: mtf_rev(ranks))


# ---------------------------------------------------------------- helpers --

def stock_base(L):
    F = bytes(sorted(L))
    return [F.find(bytes((i,))) for i in range(256)]


def counter_base(L):
    cnt = collections.Counter(L)
    base = []
    t = 0
    for i in range(256):
        c = cnt.get(i, 0)
        base.append(t if c else -1)
        t += c
    return base


def count_base(L):
    base = []
    t = 0
    for i in range(256):
        c = L.count(i)
        base.append(t if c else -1)
        t += c
    return base


def _pos(base):
    # turn the "-1 for absent" convention back into plain prefix sums
    out = []
    t = 0
    for v in base:
        out.append(t if v < 0 else v)
        t = (t if v < 0 else v)
    return out


def fill_plain(L, base):
    base = [b if b >= 0 else 0 for b in base]
    T = [0] * len(L)
    for i, sym in enumerate(L):
        b = base[sym]
        T[b] = i
        base[sym] = b + 1
    return T


def fill_packed(L, base):
    base = [b if b >= 0 else 0 for b in base]
    C = [0] * len(L)
    for i, sym in enumerate(L):
        b = base[sym]
        C[b] = (i << 8) | sym
        base[sym] = b + 1
    return C


def walk_list(L, T, end):
    out = []
    ap = out.append
    for _ in range(len(L)):
        end = T[end]
        ap(L[end])
    return bytes(out)


def walk_ba(L, T, end):
    n = len(L)
    out = bytearray(n)
    for i in range(n):
        end = T[end]
        out[i] = L[end]
    return bytes(out)


def walk_packed(C, end):
    out = []
    ap = out.append
    for _ in range(len(C)):
        v = C[end]
        ap(v & 255)
        end = v >> 8
    return bytes(out)


RUN4 = re.compile(rb'(?s)(.)\1{3}(?=.)')


def rle4_re(nt):
    res = []
    ap = res.append
    i = 0
    search = RUN4.search
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


def capture_ranks():
    ranks = []
    orig = T1.decode_huffman_block
    # re-run the decoder capturing the fav_pop indices via a shim on list.pop
    # (cheapest: instrument by re-deriving from the stock path)
    import t0_stock as S
    rec = []
    om = S.move_to_front

    def spy(l, c):
        if len(l) > 6:
            rec.append(c)
        om(l, c)
    S.move_to_front = spy
    S.decompress(DATA)
    S.move_to_front = om
    return rec


def mtf_stock(ranks):
    l = list(range(147))
    for c in ranks:
        l[:] = l[c:c + 1] + l[0:c] + l[c + 1:]
    return l


def mtf_popinsert(ranks):
    l = list(range(147))
    ins = l.insert
    pop = l.pop
    for c in ranks:
        ins(0, pop(c))
    return l


def mtf_rev(ranks):
    l = list(range(147))
    ap = l.append
    pop = l.pop
    for c in ranks:
        ap(pop(-1 - c))
    return l


if __name__ == '__main__':
    main()
