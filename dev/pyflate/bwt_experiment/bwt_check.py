"""Swap each Rust inverse-BWT variant into the pyflate pipeline; decode real
bz2 streams; compare with the original bytes and the Python path."""
import bz2, importlib.util, io, os, random, sys
d = sys.argv[1]; sys.argv = sys.argv[:1]
spec = importlib.util.spec_from_file_location("rb", os.path.join(d, "run_benchmark.py"))
rb = importlib.util.module_from_spec(spec); spec.loader.exec_module(rb)
import pyflate_rs as P
py_bwt, py_rle = rb.bwt_reverse, rb.rle4_expand

def decode(data):
    f = rb.RBitfield(io.BytesIO(data)); assert f.readbits(16) == 0x425a
    return rb.bzip2_main(f)

rng = random.Random(1)
text = open(os.path.join(d, "run_benchmark.py"), "rb").read()
tar = bz2.decompress(open(os.path.join(d, "data", "interpreter.tar.bz2"), "rb").read())
inputs = {"benchmark tarball": tar, "periodic X*1020": b"X" * 1020, "periodic ab*5000": b"ab" * 5000,
          "periodic abc*333 (odd)": b"abc" * 333, "one byte": b"a", "two bytes": b"ab",
          "source text": text, "random 400k": bytes(rng.getrandbits(8) for _ in range(400000)),
          "runs of 300": b"".join(bytes([rng.randrange(4)]) * 300 for _ in range(2000)),
          "3 blocks (2.2 MB)": (text * 40)[:2_200_000]}
fails = 0
for name, raw in inputs.items():
    comp = bz2.compress(raw, 9)
    res = []
    for label, bwt, rle in [("python", py_bwt, py_rle)] + \
            [("rust v%d" % v, (lambda L, e, v=v: P.bwt_reverse(L, e, v)), py_rle) for v in (1, 2, 3)] + \
            [("rust bwt+rle4", (lambda L, e: P.bwt_rle4(L, e)), (lambda nt: nt))]:
        rb.bwt_reverse, rb.rle4_expand = bwt, rle
        ok = decode(comp) == raw
        fails += not ok; res.append("%s %s" % (label, "ok" if ok else "FAIL"))
    print("%-24s n=%-8d %s" % (name, len(raw), " | ".join(res)))
print("ALL OK" if not fails else "%d FAILURES" % fails)
