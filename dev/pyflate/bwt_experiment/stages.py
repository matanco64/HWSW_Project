"""Per-stage time of one pyflate decode. usage: stages.py <run_benchmark.py dir> [reps]"""
import collections, importlib.util, os, sys, time
d = sys.argv[1]; reps = int(sys.argv[2]) if len(sys.argv) > 2 else 15
sys.argv = [sys.argv[0]]
spec = importlib.util.spec_from_file_location("rb", os.path.join(d, "run_benchmark.py"))
rb = importlib.util.module_from_spec(spec); spec.loader.exec_module(rb)
acc = collections.defaultdict(list)
def wrap(name):
    f = getattr(rb, name)
    def g(*a, **k):
        t = time.perf_counter(); r = f(*a, **k); cur[name] += time.perf_counter() - t; return r
    setattr(rb, name, g)
names = [n for n in ("_decode_symbols_native", "_decode_symbols_python", "bwt_transform", "bwt_reverse", "rle4_expand") if hasattr(rb, n)]
for n in names: wrap(n)
fn = os.path.join(d, "data", "interpreter.tar.bz2")
print("backend:", "native" if rb.pyflate_rs else "python")
for _ in range(reps):
    cur = collections.defaultdict(float)
    t = time.perf_counter(); rb.bench_pyflake(1, fn); cur["TOTAL"] = time.perf_counter() - t
    for k, v in cur.items(): acc[k].append(v)
tot = min(acc["TOTAL"])
for k in sorted(acc, key=lambda k: -min(acc[k])):
    m = min(acc[k]); print("%-24s %8.2f ms  %5.1f%%" % (k, m * 1e3, 100 * m / tot))
