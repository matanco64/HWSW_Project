"""Dump the benchmark bzip2 block's vectors (testplan §3): stream bytes, per-table code
lengths, selector list, alphabet, start_bit — from the frozen golden tracer, once.

Run from the module dir (golden/ on sys.path):
    python3 tb/vectors/dump_bench.py
Writes tb/vectors/bench_block.json + tb/vectors/bench_stream.bin.
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "golden"))

import canonical_model                                            # noqa: E402
import pyflate_ref                                                # noqa: E402


def main():
    trace = pyflate_ref.trace_benchmark()
    blk = trace.blocks[0]
    data = pyflate_ref.BENCH_INPUT.read_bytes()
    start_bit = blk["sym_start_bit"]
    lengths = blk["lengths"]
    selectors = blk["selectors"]
    alphabet = blk["symbols_in_use"]

    syms, end_bit, _ = canonical_model.decode_bzip2_symbols(
        data, start_bit, lengths, selectors, alphabet)
    assert syms[-1] == alphabet - 1, "block must end at EOB"

    # Tail after end_bit must stay under the 128-bit accepted-unconsumed cap (64b buffer +
    # 2x32b FIFO), or the TLAST beat is never accepted and the test silently loses the
    # TLAST-accepted regime (review B3). 10 spare bytes -> tail <= 87 bits here.
    keep = (end_bit + 7) // 8 + 10
    assert keep * 8 - end_bit <= 128, "tail exceeds the acceptance window"
    (HERE / "bench_stream.bin").write_bytes(data[:keep])
    (HERE / "bench_block.json").write_text(json.dumps({
        "start_bit": start_bit,
        "alphabet": alphabet,
        "n_tables": len(lengths),
        "lengths": lengths,
        "selectors": selectors,
        "n_symbols": len(syms),
        "end_bit": end_bit,
        "stream_bytes": keep,
    }, indent=1))
    print(f"block 0: start_bit={start_bit} alphabet={alphabet} tables={len(lengths)} "
          f"selectors={len(selectors)} symbols={len(syms)} bits={end_bit - start_bit} "
          f"stream={keep}B")


if __name__ == "__main__":
    main()
