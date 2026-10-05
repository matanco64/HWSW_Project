import bz2, importlib.util, io, os, sys
# Capture L by hooking the Python bwt_reverse, so force the Python path.
os.environ["HWSW_BWT"] = "python"
d = sys.argv[1]; out = sys.argv[2]; sys.argv = sys.argv[:1]
spec = importlib.util.spec_from_file_location("rb", os.path.join(d, "run_benchmark.py"))
rb = importlib.util.module_from_spec(spec); spec.loader.exec_module(rb)
cap = []; orig = rb.bwt_reverse
rb.bwt_reverse = lambda L, e: (cap.append((L, e)), orig(L, e))[1]
def decode(data):
    f = rb.RBitfield(io.BytesIO(data)); f.readbits(16); return rb.bzip2_main(f)
decode(open(os.path.join(d, "data", "interpreter.tar.bz2"), "rb").read())
text = open(os.path.join(d, "run_benchmark.py"), "rb").read()
decode(bz2.compress((text * 30)[:880000], 9))
for k, (L, e) in zip(("bench", "big"), (cap[0], cap[1])):
    open(os.path.join(out, k + ".L"), "wb").write(L); print(k, e)
