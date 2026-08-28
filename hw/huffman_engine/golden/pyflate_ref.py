"""Golden model for huffman_engine: wraps the stock pyflate decoder, never re-implements it.

Imports dev/pyflate/t0_stock.py (the pyperformance 1.14.0 algorithm verbatim, harness stripped)
and instruments it by monkey-patching:
  * HuffmanTable.find_next_symbol -> records (table_key, code_len, symbol, bit_pos) per decode
  * compute_tables               -> records the 6 code-length vectors per bzip2 block
  * compute_selectors_list       -> records the (already inverse-MTF'd) selector list
  * Bitfield.readbits / RBitfield.readbits -> consumed-bit counter (stock tellbits() is unreliable:
                                    the copy-constructor bug `self.count = x.bitfield` drops the
                                    16 magic bits) and raw-bit read log (DEFLATE extra bits)
  * gzip_main                    -> the stock function with its one Python-3 bug patched
                                    ('"".join(out)' -> 'b"".join(out)') so DEFLATE runs at all
Frozen: acceptance reference for the accelerator (PRD-F2/F3). Cross-checked against the
`bz2` / `zlib` C libraries by calibrate.py.
"""
import importlib.util
import inspect
import io
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
_SRC = _REPO / "dev" / "pyflate" / "t0_stock.py"
BENCH_INPUT = _REPO / "benchmarks" / "bm_pyflate" / "data" / "interpreter.tar.bz2"

_spec = importlib.util.spec_from_file_location("pyflate_stock", _SRC)
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)

# --- patched gzip_main (bug fix only: bytes join) -------------------------------------------
_src = inspect.getsource(S.gzip_main)
assert _src.count('return "".join(out)') == 1
exec(_src.replace('return "".join(out)', 'return b"".join(out)'), S.__dict__)


class Trace:
    """Everything the hardware must reproduce for one decode."""

    def __init__(self):
        self.bit_pos = 0         # bits consumed so far (all readers)
        self.symbols = []        # (table_key, code_len, symbol, bit_pos_before)
        self.raw_reads = []      # (n_bits, value, bit_pos_before, symbol_index_at_read)
        self.table_lengths = {}  # ("t", n) creation-order key -> code-length list (every HuffmanTable)
        self.blocks = []         # per bzip2 block: dict(lengths, selectors, symbols_in_use, orig_ptr, sym_start_bit)
        self.output = b""


def _install(trace: Trace, keyed_tables: dict):
    orig_find = S.HuffmanTable.find_next_symbol
    orig_tables = S.compute_tables
    orig_sel = S.compute_selectors_list
    orig_block = S.decode_huffman_block
    orig_readbits = S.Bitfield.readbits
    orig_rreadbits = S.RBitfield.readbits
    orig_ht_init = S.HuffmanTable.__init__

    def ht_init(self, bootstrap):
        orig_ht_init(self, bootstrap)
        n = max(x.code for x in self.table) + 1 if self.table else 0
        lengths = [0] * n
        for x in self.table:
            lengths[x.code] = x.bits
        self._tkey = ("t", len(trace.table_lengths))   # creation-order key: id() gets recycled
        trace.table_lengths[self._tkey] = lengths

    def find_next_symbol(self, field, reversed=True):
        pos = trace.bit_pos
        r = orig_find(self, field, reversed)
        key = keyed_tables.get(id(self), getattr(self, "_tkey", id(self)))
        trace.symbols.append((key, trace.bit_pos - pos, r, pos))
        return r

    def compute_tables(b, groups, symbols_in_use):
        tables = orig_tables(b, groups, symbols_in_use)
        for j, t in enumerate(tables):
            keyed_tables[id(t)] = j
        trace.blocks[-1]["lengths"] = [[x.bits for x in sorted(t.table, key=lambda h: h.code)]
                                       for t in tables]
        trace.blocks[-1]["symbols_in_use"] = symbols_in_use
        trace.blocks[-1]["sym_start_bit"] = trace.bit_pos
        return tables

    def compute_selectors_list(b, groups):
        sel = orig_sel(b, groups)
        trace.blocks[-1]["selectors"] = list(sel)
        return sel

    def decode_huffman_block(b, out):
        trace.blocks.append({"orig_ptr": None, "block_start_bit": trace.bit_pos})
        return orig_block(b, out)

    def readbits(self, n=8):            # Bitfield (DEFLATE, LSB-first)
        pos = trace.bit_pos
        v = orig_readbits(self, n)
        trace.bit_pos += n
        trace.raw_reads.append((n, v, pos, len(trace.symbols)))
        return v

    def rreadbits(self, n=8):           # RBitfield (bzip2, MSB-first)
        v = orig_rreadbits(self, n)
        trace.bit_pos += n
        return v

    S.HuffmanTable.find_next_symbol = find_next_symbol
    S.HuffmanTable.__init__ = ht_init
    S.RBitfield.readbits = rreadbits
    S.compute_tables = compute_tables
    S.compute_selectors_list = compute_selectors_list
    S.decode_huffman_block = decode_huffman_block
    S.Bitfield.readbits = readbits
    return (orig_find, orig_tables, orig_sel, orig_block, orig_readbits, orig_rreadbits, orig_ht_init)


def _uninstall(saved):
    (S.HuffmanTable.find_next_symbol, S.compute_tables, S.compute_selectors_list,
     S.decode_huffman_block, S.Bitfield.readbits, S.RBitfield.readbits, S.HuffmanTable.__init__) = saved


def trace_stream(data: bytes) -> Trace:
    """Decode a complete bzip2 or gzip stream with the stock algorithm and return the trace."""
    trace, keyed = Trace(), {}
    saved = _install(trace, keyed)
    try:
        field = S.RBitfield(io.BytesIO(data))
        magic = field.readbits(16)
        if magic == 0x1f8b:
            trace.output = S.gzip_main(field)
        elif magic == 0x425a:
            trace.output = S.bzip2_main(field)
        else:
            raise ValueError("unknown magic %x" % magic)
    finally:
        _uninstall(saved)
    return trace


def trace_benchmark() -> Trace:
    return trace_stream(BENCH_INPUT.read_bytes())
