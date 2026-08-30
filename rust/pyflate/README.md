# `pyflate_rs` — native symbol-decode kernel for the `pyflate` benchmark

**Status: BUILT, VERIFIED, MEASURED** on CPython 3.10.21 (WSL2), the closest
available stand-in for the course VM's CPython 3.10.12. The wheel tag is
`cp310-cp310-manylinux_2_34_x86_64`, which needs glibc >= 2.34; the VM is
Ubuntu 22.04 (glibc 2.35), so this wheel runs there unmodified.

| | |
|---|---|
| **kernel speedup** | **25x** (Python T3 symbol loop 43.4 ms → Rust 1.73 ms) |
| **end-to-end speedup** | **1.6–1.9x** over the pure-Python T3 tier — and that is **97–98% of the Amdahl cap**, every run |
| **vs. stock pyflate** | T3 is ~4.4x stock; the hybrid is **7.0–7.6x** stock |
| correctness | `L` **byte-identical** to Python T3 for the block; end bit position identical; output identical to `bz2.decompress` and to the benchmark MD5 |
| FFI crossing | ~27–44 ns, i.e. 2e-5 of one `decode()` call. One crossing per block. |

Reproduce with `dev/pyflate/rs_check.py`. Nothing in the project's >= 7%
speedup claim depends on this crate — see "Not wired in" below.

---

## Scope: the symbol-decode loop, and deliberately not one stage more

`bm_pyflate` decodes bzip2, not DEFLATE. Its per-block pipeline is

```
header ─▶ selectors ─▶ code lengths ─▶ [ SYMBOL DECODE ] ─▶ inverse BWT ─▶ RLE4 ─▶ md5
                                       ^^^^^^^^^^^^^^^^^
                                       this crate, and only this
```

**In scope** — exactly the loop `dev/pyflate/FINDINGS.md` §5 identified:

1. MSB-first bit reader over the compressed buffer (`u64` accumulator, 32-bit
   refills),
2. canonical Huffman decode — flat 2048-entry primary table with a
   `limit`/`base`/`perm` canonical fallback — including the **table swap every
   50 symbols** driven by the selector list,
3. move-to-front over the 147-entry favourites list,
4. RUNA/RUNB run-length expansion.

In: the compressed bytes, a start bit offset, the per-group code-length
vectors, the selector list, the initial MTF contents.
Out: the rank-mapped byte stream `L` (the BWT input) and the final bit
position.

**Out of scope, on purpose:**

* **`bwt_reverse` / the inverse-BWT chain walk.** It is an irreducibly serial
  data-dependent pointer chase over a 336 KB working set. FINDINGS §1d tried
  five formulations in Python and they land within ~20% of each other; the
  report's argument is precisely that *neither Python nor Rust nor a
  Huffman-decode engine fixes this*, which is what motivates the PIM discussion
  in the hardware chapter. Porting it here would replace a clean argument with
  a muddy one. The measurement below shows it is now 79% of the remaining
  Python time — i.e. the argument holds, quantified.
* **RLE4 expansion.** Already O(runs) in Python via one compiled regex (10 ms).
* **`bzip2_main` as a whole.** A native `bzip2_main` is benchmark deletion:
  `bm_pyflate` exists to time a *pure-Python decompressor*, and if the whole
  decompressor is native the remaining Python is an `open()` and a hash — which
  is `import bz2` with extra steps. The line drawn here is the line CPython
  itself draws with `_json` and `_pickle`: **a native kernel may replace an
  inner loop the profile identifies; it may not replace the program.**

Header parsing, `compute_used`, `compute_selectors_list`, the delta-coded
code-length bit loop, block orchestration, the inverse BWT, RLE4 and the MD5
check all stay in Python. Measured, that is 69 ms of the hybrid's 71 ms — the
Python is still doing most of the wall-clock work, which is the point.

## Why this boundary: one interface, three consumers

This is the same cut as the proposed hardware in `hw/`: `huffman_engine` (bit
aligner + canonical decode + the 50-symbol selector FSM) feeding `mtf_cam` (the
shift-register CAM) and the RUNA/RUNB expander. So the FFI signature is
simultaneously:

| consumer | reading of the interface |
|---|---|
| native software tier | `BlockDecoder(...)` then `decode(bit_pos)` |
| accelerator register map | `BlockDecoder(...)` **is** the config-region / DMA-descriptor write (buffer base, per-group code-length tables, selector list, initial MTF contents); `decode(bit_pos)` **is** the doorbell with a start-offset register; the returned `(bytes, end_bit_pos)` **is** the read-back window |
| RTL golden model | `trace()` emits the reference vector (below) |

That is the shape Intel's IAA uses for DEFLATE, where the Huffman tables live
in an AECS config region. `group_tables()` exposes the built
`limit`/`base`/`perm` arrays so the RTL's own table build can be diffed against
this one.

Drawing the software boundary anywhere else would mean maintaining a separate
hardware interface and the report would lose the claim that the three views are
one design.

## Correctness contract: byte-exactness, proven not asserted

`rust/nbody` has a floating-point contract. This crate has an integer one,
which is both stricter and easier: the symbol stream must be **equal**, not
close. `dev/pyflate/rs_check.py` proves it at two levels:

1. **Kernel.** `L` from Rust `==` the `bytearray` the Python T3 symbol loop
   accumulates from the same start offset, *and* the returned end bit position
   is identical. Checking the end position is not redundant — a wrong one
   desynchronises the stream for the next block.
2. **Pipeline.** Feeding the Rust `L` through the **unmodified** Python
   `bwt_reverse` + `rle4_expand` reproduces all 399,360 bytes, checked against
   CPython's own `bz2.decompress` **and** against the benchmark's MD5
   `afa004a630fe072901b1d9628b960974`.

Both pass. Two places where the Rust deliberately does not mirror the Python
literally, each documented at its call site in `src/lib.rs`:

* the selector-exhaustion guard is `<` where the Python writes `<=` (the Python
  form would raise `IndexError` rather than do anything useful; identical
  behaviour on every well-formed stream);
* the 8-byte tail padding is owned by the crate rather than pushed onto the
  caller, because a native kernel that reads out of bounds when handed a short
  buffer is a far worse bug than one 67 KB copy per block (~10 us).

## Measured, CPython 3.10.21 / WSL2, min of 15 interleaved rounds

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

Across seven runs (unpinned and `taskset`-pinned to single cores) the kernel
speedup ranged **24.4–27.4x**, end-to-end **1.59–1.93x**, and the achieved
fraction of the Amdahl cap was **97–98% every time**. This dev box is a hybrid-core
laptop under WSL2 and absolute times drift by ±20% between runs; the *ratios*
are stable, which is why `rs_check.py` interleaves the cases round-robin
instead of timing them one after another. (A sequential min-of-7 gave the same
Python function 42 ms in one script and 92 ms in another — that bug is why the
harness is written the way it is.)

### The honest Amdahl reading

**The kernel is ~25x faster; the benchmark is 1.6–1.9x faster. Both numbers are
real and the gap between them is the whole lesson.**

FINDINGS §3 predicted this: after the software ladder, `decode_huffman_block`
and `bwt_reverse` were *co-equal* hotspots. Removing one of two equal halves
caps you near 2x, and the measurement lands at 1.59–1.93x — i.e. **97–98% of
the theoretical cap on every run**, so there is no implementation slack left to
recover. The only way past it is to attack the inverse BWT, and the report's
position is that this is not a software problem: it is ~80% of the remaining
time, it is a serial pointer chase, and it is exactly the case for the PIM
closer in the hardware chapter.

FINDINGS §4 estimated "~1.8x over T3, i.e. ~5.5x over stock" for this kernel
alone, from a conservative 20x native factor. Measured: **1.6–1.9x over T3 and
7.0–7.6x over stock**. The T3-relative estimate was right; the stock-relative
one was pessimistic because the T3 tier itself measures better on CPython 3.10
than the provisional 3.12 numbers suggested, exactly as §2c predicted.

Note also that the cap moved *against* the kernel as the Python got better.
Against **stock** pyflate the same kernel looks far more impressive (7.0–7.6x);
it is the pure-Python T3 tier — itself ~4.0–4.5x stock — that makes the native
win look modest. T3 is the correct baseline and the one used above, because the
question this crate answers is "what does going native buy on top of a decent
Python implementation", not "what does going native buy over a bad one".

The residual 1.7 ms of kernel time is not FFI overhead (44 ns/crossing, one
crossing per block) nor table construction (0.06 ms, 3.5% of a decode). It is
148,271 genuinely serial Huffman decodes: each symbol's bit length must be
known before the next symbol's bits can be located. That serial dependence is
what the `huffman_engine`'s barrel-shifter-plus-comparator-cascade removes by
doing it in one cycle instead of ~35.

## Golden-trace mode (RTL reference vector)

`BlockDecoder.trace(bit_pos, path)` decodes and additionally writes a binary
reference vector for the `huffman_engine` / `mtf_cam` testbenches. Little-endian
throughout, 40-byte header:

```
 off  size        field
   0     8        magic  b"PFTRACE1"
   8     4  u32   version = 1
  12     4  u32   n_sym   Huffman symbols decoded, INCLUDING the final EOB
  16     4  u32   n_out   length of L in bytes
  20     4  u32   symbols_in_use  (alphabet size; EOB == this - 1)
  24     8  u64   bit_pos_start
  32     8  u64   bit_pos_end
  40   2*n_sym u16  sym[i]  raw Huffman symbol value, decode order
 ...     n_sym u8   len[i]  code length in bits consumed for sym[i]
 ...     n_sym u8   grp[i]  group index in effect (== selectors[i / 50])
 ...     n_out u8   L[j]    MTF + RUNA/RUNB decoded output byte
```

`sym`/`len`/`grp` are the `huffman_engine` reference stream — one record per
cycle of a 1-symbol/cycle engine, including the table swap the selector FSM
must perform every 50 symbols. `L` is the `mtf_cam` + run-expander reference
stream. `grp` is derivable from the index but is written explicitly so a
testbench need not reimplement the /50 rule in order to check it.

For this benchmark's single block the file is **929,308 bytes**: 148,271
symbols x 4 + 336,184 output bytes + 40. Write it with

```bash
python dev/pyflate/rs_check.py --trace /tmp/block0.pft
```

which also reads it back and self-checks the magic, the group schedule, the bit
accounting (`sum(len) == bit_pos_end - bit_pos_start`) and the payload against
the independently decoded `L`.

## Build

```bash
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"     # rustc 1.98, maturin 1.15
cd rust/pyflate
maturin build --release -i /path/to/python3.10
# -> target/wheels/pyflate_rs-0.1.0-cp310-cp310-manylinux_2_34_x86_64.whl
uv pip install --python /path/to/python3.10 --reinstall -q target/wheels/pyflate_rs-*.whl
python ../../dev/pyflate/rs_check.py
```

A prebuilt wheel is in `wheels/`. `manylinux_2_34` needs glibc >= 2.34 and the
course VM is Ubuntu 22.04 (glibc 2.35), so it loads there; rebuilding in-guest
also works and sidesteps the question entirely. Note that pyperf runs
benchmarks in **worker subprocesses**, so if this ever were wired in, the
extension would have to be pip-installed into the measured venv — `PYTHONPATH`
will not do.

## Not wired into `benchmarks/bm_pyflate/run_benchmark.py`

Deliberately, and for the same reason as `rust/nbody`:

* The pure-Python tier already clears the bar by a factor of ~50 in
  improvement terms: the requirement is a 7% speedup (1.07x) and T3 measures
  ~4.4x against stock on this interpreter. Nothing needs this crate.
* An optional `try: import pyflate_rs / except ImportError: <python fallback>`
  makes the measured configuration ambiguous — a reader of the results cannot
  tell which path ran. Two named tiers with two reported numbers is honest;
  one file that silently switches is not.
* FINDINGS §5 ranks a native kernel as the one item in the ladder that is a
  "gray zone by construction". The right way to present a gray-zone
  optimization is *beside* a defensible one that already clears the bar, with
  its own measurement, not folded into the headline number.

So it stands as an additional tier and as the behavioural specification for the
`huffman_engine` + `mtf_cam` accelerator.
