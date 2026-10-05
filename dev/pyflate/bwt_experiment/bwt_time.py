import bz2, importlib.util, io, os, sys, time
# Capture L by hooking the Python bwt_reverse, so force the Python path.
os.environ["HWSW_BWT"] = "python"
d = sys.argv[1]; sys.argv = sys.argv[:1]
spec = importlib.util.spec_from_file_location("rb", os.path.join(d, "run_benchmark.py"))
rb = importlib.util.module_from_spec(spec); spec.loader.exec_module(rb)
import pyflate_rs as P
cap = []
orig = rb.bwt_reverse
rb.bwt_reverse = lambda L, e: (cap.append((L, e)), orig(L, e))[1]
def decode(data):
    f = rb.RBitfield(io.BytesIO(data)); f.readbits(16); return rb.bzip2_main(f)
bench = open(os.path.join(d, "data", "interpreter.tar.bz2"), "rb").read()
decode(bench); Lb, eb = cap[-1]
text = open(os.path.join(d, "run_benchmark.py"), "rb").read()
big = bz2.compress((text * 30)[:880000], 9); cap.clear(); decode(big); Lbig, ebig = cap[0]
rb.bwt_reverse = orig

def best(f, reps):
    m = 1e9
    for _ in range(reps):
        t = time.perf_counter(); f(); m = min(m, time.perf_counter() - t)
    return m * 1e3
for name, (L, e) in {"benchmark block": (Lb, eb), "max-size block": (Lbig, ebig)}.items():
    print("== %s: n = %d" % (name, len(L)))
    py = best(lambda: orig(L, e), 7)
    print("  %-34s %8.3f ms" % ("Python bwt_reverse (shipped)", py))
    nt = orig(L, e)
    print("  %-34s %8.3f ms" % ("Python rle4_expand (shipped)", best(lambda: rb.rle4_expand(nt), 7)))
    for v, lab in ((1, "Rust v1 port"), (2, "Rust v2 packed"), (3, "Rust v3 two chains")):
        k = P.bwt_bench(L, e, v, 200) / 1e6
        print("  %-34s %8.3f ms   (%.0fx vs Python)" % (lab, k, py / k))
    print("  %-34s %8.3f ms" % ("Rust rle4 alone", P.bwt_bench(L, e, 0, 200) / 1e6))
    print("  %-34s %8.3f ms" % ("bwt_rle4() call from Python, v3", best(lambda: P.bwt_rle4(L, e, 3), 200)))
