# `pyflate_rs`: native bzip2 symbol decoder

The Rust extension is **already integrated** into
`benchmarks/bm_pyflate/run_benchmark.py`. It replaces Huffman symbol decoding,
move-to-front (MTF), and RUNA/RUNB expansion. Header parsing, inverse BWT, final
RLE4 expansion, and output validation remain in Python.

## Benchmark integration

`HWSW_BACKEND` selects the implementation:

| Value | Behavior |
|---|---|
| `python` | Always use the Python symbol loop. |
| `native` | Require `pyflate_rs`; fail if it cannot be imported. |
| `auto` (default) | Use Rust when importable; otherwise use Python. |

For comparable results, select the backend explicitly. From the repository
root, `bash script_pyflate.sh native` runs the named Python-fallback and native
tiers and passes the selection to pyperf workers with
`--inherit-environ HWSW_BACKEND`. The regular optimized software tier runs
through pyperformance's separate Python environment and remains the
pure-Python comparison. Install the extension into the interpreter/environment
being measured; an installation elsewhere does not make it available to workers.

The optional native tier is separate from the course's pure-Python speedup
claim. It also supplies the symbol stream and trace interface for the proposed
Huffman/MTF accelerator; this is a functional boundary, not a claim of completed
RTL integration.

## Source layout

| File | Responsibility |
|---|---|
| `src/lib.rs` | Crate scope and module declarations. |
| `src/bindings.rs` | PyO3 API, Python exceptions, GIL release, file handling. |
| `src/bit_reader.rs` | MSB-first 32-bit refills and absolute bit offsets. |
| `src/huffman.rs` | Canonical tables, primary lookup, long-code fallback. |
| `src/decoder.rs` | Block configuration, 50-symbol selector schedule, MTF and run expansion. |
| `src/trace.rs` | Python-independent PFTRACE1 serialization. |

The refactor retains the existing algorithm, Python signatures, selector
schedule, and binary trace format. The core has no PyO3 dependency. Two bounded
validation improvements reject oversubscribed Huffman lengths before table
construction can panic and reject out-of-range bit offsets before narrowing
or indexing. This is a benchmark kernel, not a hardened general-purpose
decompressor: the existing selector-exhaustion fallback and zero tail padding
are retained, and malformed streams can still request large output allocations.

Each full 11-bit primary table occupies 8 KiB; whether several tables fit in
L1 depends on the CPU and other live data. The MTF state is a contiguous byte
vector; a rank-r move shifts r bytes, not r Python object references. Inverse
BWT's dependency chain remains outside this kernel. That does not prove a
native BWT implementation could not improve performance.

## API and correctness contract

```python
decoder = pyflate_rs.BlockDecoder(
    data, code_lengths, selectors, symbols_in_use, favourites
)
L, end_bit_pos = decoder.decode(start_bit_pos)
# Equivalent one-shot call:
L, end_bit_pos = pyflate_rs.decode_block(
    data, start_bit_pos, code_lengths, selectors, symbols_in_use, favourites
)
```

`data` is the whole compressed stream; `code_lengths` contains one vector
per Huffman group; `selectors` names a group per 50 symbols; `favourites` is
the initial **front-first** MTF list; `symbols_in_use = len(favourites) + 2`.
The constructor owns a padded copy of the input. Each call resets decode state,
so a configured decoder is reusable.

Both `L` and the end bit offset must exactly match the Python T3 symbol loop.
The unmodified Python inverse BWT and RLE4 must then reproduce `bz2.decompress`.
For the course input this means 399,360 output bytes and MD5
`afa004a630fe072901b1d9628b960974`.

Other API members are unchanged: `num_groups`, `primary_bits`,
`group_tables()`, `trace(start_bit_pos, path)`, and the module constant
`PRIMARY_BITS`. The trace method returns
`(number_of_symbols, output_length, end_bit_pos)`.

### Golden trace

PFTRACE1 uses little-endian integers and a 40-byte header:

| Offset | Field |
|---|---|
| 0 | Eight-byte magic `PFTRACE1` |
| 8 | u32 version (1) |
| 12 | u32 symbol count, including EOB |
| 16 | u32 output byte count |
| 20 | u32 alphabet size |
| 24 | u64 start bit position |
| 32 | u64 end bit position |
| 40 onward | u16 symbols, u8 code lengths, u8 group indices, then output bytes |

Tracing is a const-generic specialization, so trace collection is absent from
normal decoding. `dev/pyflate/rs_check.py --trace /tmp/block0.pft` checks the
format, group schedule, bit accounting, and payload against Python.

## Build and test

Run in Linux/WSL with Rust, Python development support, and maturin available:

```bash
cd rust/pyflate
cargo fmt --all --check
cargo test --locked --test kernel
cargo check --locked
cargo build --locked --release
cd ../..
python3 rust/pyflate/tests/python_api.py rust/pyflate/target/release/libpyflate_rs.so
```

The API test loads the named build directly: it does **not** install or replace
a wheel. Ten Rust tests cover bit offsets/refills, primary and long Huffman
codes, invalid tables/configuration, selector changes, MTF/run expansion,
repeatability, and trace bytes. The Python suite checks the course input plus
four deterministic fixtures, including a three-block stream, against both
Python T3 and `bz2`; it checks both decode APIs, traces, and exact end offsets.
These checks passed after the refactor on WSL CPython 3.12.3.

`Cargo.lock` is tracked to make dependency resolution reproducible. To build
a wheel for the measured interpreter:

```bash
cd rust/pyflate
maturin build --locked --release -i /path/to/python3.10
/path/to/python3.10 -m pip install --force-reinstall target/wheels/<built-wheel>.whl
/path/to/python3.10 ../../dev/pyflate/rs_check.py
```

The existing wheel in `wheels/` and the installed course-VM wheel predate this
refactor; neither was replaced. The report's VM timing/counter measurements
therefore describe that earlier binary, not the new WSL test build.

## Historical performance: CPython 3.10.21, WSL2

The following pre-refactor run used minima from 15 interleaved rounds. It is
retained as development evidence, not a matched course-VM result or a
post-refactor performance claim.

```
--- kernel byte-exactness (Rust vs Python T3 symbol loop) ---
  block 0: BlockDecoder(groups=6, selectors=2966, alphabet=147, primary_bits=11)
           L identical: True (336184 bytes)   end bit pos: True (540415)

--- pipeline byte-exactness (Rust kernel + Python BWT/RLE4) ---
  hybrid == bz2.decompress : True
  hybrid md5 afa004a630fe072901b1d9628b960974 == benchmark md5 : True

--- symbol-decode kernel ---
  Python T3 symbol loop :   43.409 ms
  Rust  pyflate_rs      :    1.730 ms
  KERNEL SPEEDUP        :     25.1x

--- stages that stay in Python ---
  inverse BWT           :   51.516 ms
  RLE4 expand           :    9.517 ms
  header + table build  :    3.228 ms

--- end to end ---
  pure Python T3        :  111.282 ms
  hybrid (Rust kernel)  :   66.084 ms
  END-TO-END SPEEDUP    :     1.68x
  T0 stock (context)    :  495.088 ms  -> T3 4.45x, hybrid 7.49x

  Amdahl:
    symbol loop is 39.0% of the pure-Python decode
    Python left in the hybrid: 64.354 ms (BWT 80% + RLE4 15% + header/join)
    CAP with an infinitely fast kernel: 1.73x
    achieved: 1.68x  (97% of the cap)

  FFI crossing cost: 27 ns  ->  1.5e-05 of one decode() call
  config build BlockDecoder(...): 0.060 ms, i.e. 3.4% of one decode
```


The kernel speedup is larger than the end-to-end speedup because the Python
tail remains. The displayed cap is an estimate from separately timed stages
on this WSL run; it is not a universal limit, and it does not establish that
inverse BWT has no further software optimization opportunities.
