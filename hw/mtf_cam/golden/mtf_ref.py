"""Golden model for mtf_cam: reuses the instrumented stock pyflate of huffman_engine (imported,
never copied) and captures what this module must reproduce for a bzip2 block:

  used      : the 256-entry boolean byte map (initial MTF list = sorted used bytes, pyflate
              `favourites`, dev/pyflate/t0_stock.py::decode_huffman_block)
  symbols   : the Huffman symbol stream that feeds the module (RUNA=0, RUNB=1, MTF index+1, EOB)
  l_vector  : the byte string handed to bwt_reverse (the module's output stream)
  mtf_out   : per MTF symbol, the byte pyflate emitted (favourites[r-1]) — the scoreboard's
              per-beat expectation for the MTF path

Frozen; cross-checked by calibrate.py against libbzip2 through the huffman_engine golden.
"""
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent.parent / "huffman_engine" / "golden"))
import pyflate_ref as G   # noqa: E402

S = G.S
BENCH_INPUT = G.BENCH_INPUT


class MtfTrace:
    def __init__(self):
        self.used = None
        self.symbols = []
        self.l_vector = b""
        self.mtf_out = []
        self.output = b""


def trace_stream(data: bytes) -> MtfTrace:
    mt = MtfTrace()
    orig_used = S.compute_used
    orig_bwt = S.bwt_reverse
    orig_mtf = S.move_to_front

    def compute_used(b):
        u = orig_used(b)
        mt.used = list(u)
        return u

    def bwt_reverse(L, end):
        mt.l_vector = bytes(L)
        return orig_bwt(L, end)

    def move_to_front(l, c):
        if l and isinstance(l[0], bytes):    # favourites holds bytes objects; the selector MTF holds ints
            mt.mtf_out.append(l[c][0] if isinstance(l[c], bytes) else l[c])   # favourites holds 1-byte bytes objects
        return orig_mtf(l, c)

    S.compute_used, S.bwt_reverse, S.move_to_front = compute_used, bwt_reverse, move_to_front
    try:
        tr = G.trace_stream(data)
    finally:
        S.compute_used, S.bwt_reverse, S.move_to_front = orig_used, orig_bwt, orig_mtf
    mt.symbols = [s for (_, _, s, _) in tr.symbols]
    mt.output = tr.output
    mt.alphabet = tr.blocks[0]["symbols_in_use"]
    return mt


def trace_benchmark() -> MtfTrace:
    return trace_stream(BENCH_INPUT.read_bytes())
