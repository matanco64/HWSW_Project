# Inverse BWT in Rust: a post-submission experiment

> **Not part of the submission.** This work was done after the code freeze, on
> the branch `experiment/bwt-rust`. The submitted code, wheels and numbers are
> unchanged. It is reported separately so the gain can be discussed without
> blurring what was submitted.

## Summary

In the submitted pyflate, the Huffman and move-to-front stage runs in Rust,
but the inverse BWT and the final run-length step (RLE4) still run in Python.
On the course VM they take **78%** and **15%** of a decode. Moving both to Rust
and changing how the inverse-BWT chain is walked makes the whole benchmark
**11.06x faster** (pyperf, 161 ms → 14.6 ms). The output is byte-identical on
every input tested.

| Course VM, CPython 3.10.12, `taskset -c 0` | Submitted | Experiment | |
|---|---|---|---|
| Whole benchmark (pyperf mean ± std) | 161 ms ± 1 | 14.6 ms ± 0.1 | **11.06x** |
| Inverse BWT (best of 7 / 200) | 124.5 ms | 3.9 ms | 32x |
| RLE4 (best of 7 / 200) | 23.3 ms | 0.74 ms | 31x |

Source: `results/bwt_rust_20261005/` (`rest2.log` for pyperf, `rest.log` for
the kernels, `run.log` for the checks and the stage split).

## Where the time was

Per-stage time of one decode on the VM, best of 20 (`run.log`):

| Stage | Submitted | Share |
|---|---|---|
| Whole decode | 159.5 ms | 100% |
| Inverse BWT (`bwt_reverse`) | 124.8 ms | 78% |
| ↳ bucket pointers (`bwt_transform`) | 73.3 ms | 46% |
| RLE4 (`rle4_expand`) | 23.7 ms | 15% |
| Huffman + move-to-front (Rust) | 3.1 ms | 2% |

With the experiment the whole decode is 16.6 ms, and the Rust Huffman stage
(3.1 ms) becomes the largest named piece; the rest is Python header parsing
and glue.

## Why the walk is slow, and what changes it

The inverse BWT emits one byte per step: `end = T[end]; out[i] = L[end]`.
Each step needs the previous step's result, so the 336,184 loads form a single
dependency chain and the CPU cannot overlap them. The deck calls this "the
wall": in Python, the best rewrite of this loop saved about 10%.

Four ideas were measured in Rust (VM, benchmark block, best of 200,
`rest.log` and `rest2.log`):

| Version | Inverse BWT | vs Python |
|---|---|---|
| Python (submitted) | 124.5 ms | 1x |
| Straight Rust port: build `T`, walk it | 6.07 ms | 21x |
| + packed entries: one `u32` holds next position and byte | 5.04 ms | 25x |
| + two chains meeting in the middle (+ 4-way histogram) | 3.91 ms | 32x |
| Two steps per lookup | slower, dropped | |

**Packed entries** are bzip2's own trick: `(next << 8) | byte` in one word, so
each step does one random load instead of two. They cost nothing extra to
build.

**Two chains meeting in the middle.** Walking `T` forward from `end` produces
the output front to back. The inverse permutation of `T` (the LF mapping) is
built in the same pass at almost no cost, and walking it from the same `end`
produces the output back to front: `out[n-1-k] = L[LF^k(end)]`. The loop runs
both walks interleaved, each half as long, and the CPU overlaps their loads.
It stays exact when `T` is several cycles (periodic data, the bug the original
pyflate comment describes), because every cycle length of a BWT permutation
divides `n`, so `T^n` is the identity.

**4-way histogram.** bzip2's `L` is full of runs, so with a single count array
every repeated byte waits for the previous increment of the same counter. Four
arrays used in rotation cut the histogram from 0.54 ms to 0.24 ms on the VM.

**Two steps per lookup** (a table holding the position two steps ahead plus
both bytes, the idea of Kärkkäinen, Kempa and Puglisi) shortens the walk to
1.90 ms, but building the table costs 1.36 ms, so the total is worse than two
chains (3.25 ms vs 2.64 ms). It loses at the maximum block size too
(12.3 ms vs 11.5 ms).

Phase split for the final version on the VM (`rest2.log`): histogram 0.24 ms,
table build 0.84 ms, walk 2.64 ms.

## Correctness

`dev/pyflate/bwt_experiment/bwt_check.py` swaps each Rust variant into the
full pyflate pipeline and decodes real bz2 streams, comparing with the
original bytes. All 10 inputs pass for every variant, on the VM and on a
laptop (`run.log`):

- the benchmark tarball
- periodic blocks: `'X' * 1020`, `'ab' * 5000`, `'abc' * 333` (odd length)
- a 1-byte and a 2-byte block
- source text, 400 KB of random bytes, long runs of 300 equal bytes
- a 1.5 MB stream that spans two blocks (the script labels it "3 blocks (2.2 MB)"; the input is shorter than intended)

The benchmark's own MD5 check also passes in every pyperf run.

## What changed (branch `experiment/bwt-rust`)

- `rust/pyflate/src/bwt.rs`: the three inverse-BWT variants and RLE4.
- `rust/pyflate/src/bindings.rs`: `bwt_reverse(L, end, variant=3)`,
  `bwt_rle4(L, end, variant=3)` and `bwt_bench(...)` (timing inside Rust).
- `benchmarks/bm_pyflate/run_benchmark.py`: uses `bwt_rle4` when the installed
  `pyflate_rs` has it, unless `HWSW_BWT=python`. With the submitted wheel the
  code path is unchanged.
- `dev/pyflate/bwt_experiment/`: the check, timing and phase scripts.

## Caveats

- The submitted pyperf mean measured here, 161 ms, is lower than the 170 ms in
  the submitted results. That is another session on a shared host; the 11.06x
  compares two runs made back to back in the same session.
- Kernel and stage times are best-of-N inside one process; only the
  whole-benchmark number uses pyperf.
- The VM's system `pyflate_rs` (the submitted wheel) was not modified: the
  experimental build was loaded through `PYTHONPATH`, and the pyperf metadata
  records which module was used (`hwsw_native_module`, `hwsw_native_sha256`).
- On an Apple M4 Max (Python 3.10.20) the same change gives 71.4 → 8.54 ms
  (8.36x). The kernel ranking is the same, but packing gains nothing there.

## Reproduce

On the VM, from a clean copy of the branch: `results/bwt_rust_20261005/run_vm.sh`.
It builds the wheel with maturin into `/tmp/bwt_exp`, unpacks it into a private
directory and runs everything with `taskset -c 0`.
