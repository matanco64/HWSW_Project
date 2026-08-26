# pyflate — software optimization findings

**Status:** measurements below are **provisional**. All timings so far were taken on
Windows/CPython 3.12.6 on a noisy hybrid-core laptop (Intel Core Ultra 7 155H,
6 P-cores + 8 E-cores + 2 LP-E-cores). The final rigorous A/B is to be re-run
serially on a quiet machine by the coordinator, and re-confirmed on the course
VM (Ubuntu 22.04 / CPython 3.10.12) when the Technion servers come back.

**Interpretation rule that applies to every number here:** CPython 3.12 and 3.14
have adaptive specialization (PEP 659) that 3.10 does **not**. Every optimization
in this ladder removes interpreter dispatch, bound-method calls, and attribute
loads — precisely the work specialization already partially hides. So the 3.12
numbers are a **conservative lower bound** for what the VM's 3.10 will show.
The purely algorithmic changes (counting sort, regex RLE4, MTF rank-cost) are
roughly version-neutral.

---

## 0. What the workload actually is

Despite the name, `bm_pyflate` decodes **bzip2**, not DEFLATE: the shipped
`data/interpreter.tar.bz2` starts with magic `0x425a`, so `bzip2_main()` runs and
`gzip_main()` is dead code. (`gzip_main` is in fact *unrunnable* on Python 3 at
all — it ends in `"".join(out)` over a list of `bytes`, which raises `TypeError`.
Verified against unmodified stock. This matters for the risk assessment in §5:
nothing done to the gzip path can regress a path that never executed.)

One loop = 67,562 compressed bytes -> 399,360 bytes, MD5-checked every run.

### Measured structure of this exact input (`instrument.py`)

These are properties of the *data*, not of the interpreter, so they carry to the VM
unchanged. They are what justify every decode-strategy choice below.

| Quantity | Value |
|---|---|
| bzip2 blocks | 1 |
| Huffman groups (tables) built | 6 |
| Alphabet size (`symbols_in_use`) | 147 |
| Huffman symbols decoded | **148,271** |
| MTF operations on the 147-entry favourites list | **89,837** |
| BWT input `L` | **336,184 bytes** |
| Final output after RLE4 | 399,360 bytes |
| RLE4 4-byte runs in the block | **8,542** |

**Code-length distribution over the 148,271 decoded symbols:**

| bits | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| % | 41.9 | 20.6 | 14.8 | 7.8 | 4.5 | 3.7 | 2.6 | 1.7 | 0.9 | 0.6 | 0.4 | 0.2 | 0.1 | 0.03 |

Mean code length **3.59 bits**. Cumulative: <=8 bits = 95.9%, <=11 bits = **99.6%**.
Per-table `(min_bits, max_bits)`: `(3,15)`, `(2,15)`x3, `(2,11)`, `(2,14)`.

**Linear-scan depth actually reached by stock `find_next_symbol`** (index into the
147-entry sorted table):

| stat | mean | p50 | p75 | p90 | p95 | p99 | max |
|---|---|---|---|---|---|---|---|
| entries walked | **5.0** | 2 | 5 | 13 | 21 | 48 | 146 |

**MTF rank distribution** (89,837 calls, list length 147):

| stat | mean | p50 | rank 1 | <= rank 8 | max |
|---|---|---|---|---|---|
| value | **7.17** | 3 | 30.4% | 77.0% | 144 |

---

## 1. Algorithmic analysis — what is a real complexity win and what is not

The single most important correction to the prior dossier: **the stock Huffman
matcher is *not* an O(258) scan in practice.** The table is sorted by
`(bits, code)` and the entropy coder puts frequent symbols at short lengths, so
the linear scan is self-adapting: it walks a **mean of 5.0 entries**, not 147.
The claim in the dossier of "O(symbols) linear scan -> 25-45% win" was based on
the worst case and overstates the Huffman opportunity by a large factor. The
real Huffman cost is not the loop *count*, it is the loop *body*: five
iterations of `LOAD_ATTR x.bits` / `LOAD_ATTR x.reverse_symbol` on
`HuffmanLength` objects, plus **2.3 `snoopbits()` bound-method calls per symbol**
(341,601 total, each of which calls `needbits()` and `_mask()`).

Verdicts, each measured independently (`micro.py`, `ablate.py`):

### 1a. Canonical Huffman decode — real win, but constant-factor, not asymptotic

Per-table `limit[]`/`base[]`/`perm[]` (the libbzip2 `hbCreateDecodeTables`
scheme), decoding by reading `min_bits` then extending one bit at a time.
Iteration count goes from mean 5.0 object-attribute steps to mean
`3.59 - 2 + 1 ~= 2.6` integer compares, **and** the per-step cost collapses from
attribute loads + method calls to pure local arithmetic.
Complexity: O(mean scan depth) -> O(len - min_len). Both are O(1) in the
alphabet for this distribution; the win is the constant.

**Measured: T1 -> T2 = 1.40x on the whole benchmark** (0.3325 -> 0.2372 s).
This is the largest Huffman-side win, and most of it comes from inlining the bit
reader into the symbol loop — canonical decode is only worth anything if "fetch
one more bit" is a shift rather than a bound-method call. The two are one change
and are reported as one.

### 1b. Multi-bit flat table decode — true O(1), but small marginal gain here

A flat table indexed by the next `PRIMARY_BITS` peeked bits, giving
`(symbol, length)` in one list index. This *is* a genuine complexity improvement
(O(1) vs O(len - min_len)) and is the structure real inflate implementations use.

Because bzip2 codes are canonical **and MSB-first**, the slots for consecutive
symbols in canonical order are **contiguous**, so the table is built with ~147
C-level span assignments (`tbl += [v] * span`) rather than 2^PB per-slot writes.
Measured build cost for all six tables: **0.39-0.86 ms** depending on width —
against 148,271 symbol decodes, i.e. **~0.3% of block time**. Amortization is a
non-issue; the two-level (primary + secondary table) variant is unnecessary here
and was not built. Codes longer than `PRIMARY_BITS` (0.4% of symbols) fall back
to the canonical stepping loop, which *is* the two-level structure with the
secondary tables replaced by arrays we already have.

But the marginal gain over 1a is small, because 1a already resolves the average
symbol in 2.6 cheap steps:
**Measured (ablation): the flat table is worth +10.1 ms out of 175.5 ms, ~5.4%.**

`PRIMARY_BITS` sweep, end-to-end, provisional:

| PRIMARY_BITS | 8 | 9 | 10 | 11 | 12 | 13 | 15 |
|---|---|---|---|---|---|---|---|
| best (s) | 0.192 | 0.182 | 0.197 | 0.194 | 0.191 | 0.190 | 0.200 |
| build, all 6 tables (ms) | 0.39 | 0.40 | 0.42 | 0.46 | 0.50 | 0.56 | 0.79 |

Flat within noise from 8 to 13 — coverage saturates (95.9% at 8 bits, 99.6% at
11) faster than the cache cost grows. **Chose 11**: 99.6% coverage, 2048 entries
(16 KB of pointers), comfortably cache-resident.

### 1c. Bit reader — real win, pure constant factor

Stock: `f.read(1)` per input byte (67,562 calls), then `_more` -> `_read` ->
`needbits` -> `_mask` per access (655,017 `_mask` calls). Replaced by a single
bulk read into `bytes`, a bounded window refilled 32 bits at a time (16,889
refills), a precomputed mask table, and full inlining into the symbol loop.

Note the stock accumulator was **already bounded** — `readbits` masks it back
down — so the "big-int arithmetic is ~20%" framing in the prior dossier is
wrong; the cost was *call overhead*, not int width. Folded into T1 and T2, so
not separately ablatable, but the `_mask` / `snoopbits` / `readbits` / `_more` /
`_read` rows of the T0 cProfile that it deletes total **0.293 s of 1.186 s**
profiled time.

### 1d. Inverse BWT — real algorithmic win in the transform, none in the walk

`bwt_transform` built `bytes(sorted(L))` — an **O(n log n)** sort of 336,184
bytes — purely to recover 256 bucket offsets, then called `F.find()` 256 times.
Replaced by an **O(n + 256)** counting sort. That is a genuine complexity win.

Histogram method matters (best-of-7, 336,184 bytes):

| method | ms |
|---|---|
| stock `bytes(sorted(L))` + 256 x `find()` | 15.13 |
| `collections.Counter(L)` (C `_count_elements`) | **7.94** |
| `[L.count(i) for i in range(256)]` | 21.98 |

The **chain walk is irreducibly serial** — `end = T[end]; out[i] = L[end]`, a
data-dependent pointer chase over a 336 KB working set. Five formulations were
tried; only the container choice moved the number:

| walk variant | ms |
|---|---|
| stock: `list.append(L[end])` then `bytes(out)` | 77.8 |
| **preallocated `bytearray` slot assign** | **64.6** |
| packed single-lookup list, entry = `(T[i] << 8) + L[T[i]]` | 84.4 |
| F-form `out[i]=F[e]; e=T[e]` (uses the identity `L[T[b]] == F[b]`) | about the same |
| x8 unrolled | about the same or worse |

This is the honest ceiling of pure Python here, and it is exactly why the
inverse BWT is the right target for the *hardware* half of the talk (§4/§6).

**Fusing RLE4 into the chain walk: evaluated and rejected.** Adding a run-detect
compare to all 336,184 walk iterations costs more than the entire regex RLE4
pass (10.8 ms). Measured, not assumed.

### 1e. MTF — the biggest single win, and a real complexity change

Stock `l[:] = l[c:c+1] + l[0:c] + l[c+1:]` allocates three slices and rewrites
all 147 entries: **O(n) per call, 89,837 calls.**
The measured rank distribution (mean 7.17, p50 = 3, 77% at rank <= 8) says the
*useful* work per call is tiny. Keeping the list in **reverse order** makes
move-to-front `l.append(l.pop(-r))`, which memmoves only `rank` slots:
**O(rank), mean 7.2.**

| MTF implementation | ms for the real 89,837-call trace |
|---|---|
| stock 3-slice rebuild | **80.4** |
| `l.insert(0, l.pop(c))` (what the prior dossier suggested) | 7.5 |
| **reversed list, `l.append(l.pop(-1-c))`** | **6.1** |

O(n) -> O(rank) with n = 147 and mean rank 7.2. A bucketed / sqrt-decomposed
structure was **not** pursued: at 147 entries with mean rank 7, the pointer
chasing and Python-level bookkeeping would cost more than the 6.1 ms that is
left. Measuring the rank distribution first is what made that call obvious — and
it is the answer to "why not a fancier structure".

### 1f. RLE4 expansion — real algorithmic win: O(n) Python iterations -> O(runs)

Stock walked all 336,184 bytes one at a time, testing four neighbours and
appending a fresh one-byte `bytes` object per literal. Runs are rare (**8,542**).
Replaced by a compiled regex for "four identical bytes followed by at least one
more": the regex engine finds the next run at C speed and each literal stretch
between runs is copied with one slice. Semantics are identical left-to-right (a
run consumes 4 bytes plus the count byte; scanning resumes after it).
**Measured: 68.5 ms -> 10.8 ms.** Python-level iterations: 336,184 -> 8,542.

### 1g. Fusing Huffman -> MTF -> RLE

Done. The stock code materialized ~90,000 one-byte `bytes` objects in a list and
joined them at the end. Now the three stages share one loop and write straight
into a single `bytearray`. Folded into T1.

### Summary: which are true complexity improvements?

| change | complexity | verdict |
|---|---|---|
| MTF reversed-list | O(n=147) -> O(rank~7) per call | **true win, largest single item** |
| RLE4 regex | O(n) Python iters -> O(runs) | **true win** |
| BWT counting sort | O(n log n) -> O(n + 256) | **true win** |
| flat Huffman table | O(len-min) -> O(1) | true win, but only ~5% here |
| canonical Huffman | constant-factor (5.0 -> 2.6 cheap steps) | big win, not asymptotic |
| bulk/inlined bit reader | constant-factor (call elimination) | big win, not asymptotic |
| bytearray fusion | constant-factor (allocation elimination) | moderate win |
| BWT chain walk | irreducibly serial O(n) | **no win available in Python** |

---

## 2. The ladder

Files in `dev/pyflate/`, each a standalone module exposing `decompress(path) -> bytes`:

- `t0_stock.py` — the pyperformance 1.14.0 algorithm, verbatim, harness stripped.
- `t1_micro.py` — bulk read + 32-bit refills + inlined `_mask` + reversed-list MTF
  + `bytearray` accumulation + locals binding. **Linear-scan Huffman untouched**,
  so the T1 -> T2 delta isolates the decode strategy.
- `t2_canonical.py` — `limit`/`base`/`perm` canonical decode + bit reader inlined
  into the symbol loop. Inherits everything else from T1.
- `t3_table.py` — flat primary lookup table + counting-sort BWT + regex RLE4.

Harnesses: `bench.py` (interleaved timing + MD5 + byte-diff vs `bz2`, and
`--profile <tier>` for cProfile), `instrument.py` (distributions), `micro.py`
(per-primitive micro-benchmarks on the real intermediate data), `ablate.py`
(remove one optimization from T3 at a time), `sweep.py` (`PRIMARY_BITS`).

### 2a. Ladder results — CPython 3.12.6, Windows, PROVISIONAL

Interleaved round-robin, best-of-7. Interleaving so drift hits every tier
equally; best-of because the workload is deterministic and the noise is
one-sided.

| tier | best (s) | vs T0 | correctness |
|---|---|---|---|
| T0 stock | 0.4347 | 1.00x | OK (MD5 + byte-equal to `bz2`) |
| T1 micro | 0.3325 | **1.31x** | OK (MD5 + byte-equal to `bz2`) |
| T2 canonical | 0.2372 | **1.83x** | OK (MD5 + byte-equal to `bz2`) |
| T3 table | 0.1459 | **2.98x** | OK (MD5 + byte-equal to `bz2`) |

A second interleaved run gave T0 0.3604 / T1 0.2403 (1.50x) / T2 0.1651 (2.18x),
so the *ordering* is stable and the ratios sit at 1.3-1.5x, 1.8-2.2x, ~3.0x.
Every tier clears the required 7% by a very wide margin; **T1 alone clears it
more than 4x over**, which is a comfortable safety net if any later tier is
challenged.

pyperf on the landed benchmark (one `--rigorous` stock baseline taken before the
no-rigorous instruction arrived; P-core-pinned via `start /affinity FFF`):
stock **417 ms +- 61 ms**; unpinned it was 495 ms +- 91 ms; a pinned `--fast`
run was 401 ms +- 29 ms. Pinning to P-cores cut the std dev from 18% to 7% —
**the noise is hybrid-core scheduling, not background load** (measured CPU load
was 1%). Recommendation for the final A/B: pin affinity to the P-cores.
A direct `bench_pyflake(1, ...)` call on the landed file returns **0.143 s**,
consistent with the T3 tier number.

### 2b. Ablation — which optimization is worth what (3.12, best-of-7, provisional)

Start from T3 and put **one** stock/T1 component back:

| variant | best (s) | cost of reverting |
|---|---|---|
| T3 full | 0.1755 | — |
| minus flat table (canonical stepping instead) | 0.1856 | +10.1 ms |
| minus regex RLE4 (per-byte loop) | 0.2077 | +32.3 ms |
| minus counting-sort BWT (stock sort + walk) | 0.2140 | +38.6 ms |
| T1 only (all Huffman/BWT/RLE work reverted) | 0.3760 | +200.6 ms |

Note the ordering: **the flat lookup table, the fanciest change, is the least
valuable one**, and the two "boring" back-end fixes (RLE4, BWT) are each 3-4x
more valuable. That is the opposite of what the prior dossier predicted, and it
makes a genuinely good slide.

### 2c. Cross-version expectations

- **3.14.6 cross-check:** pending.
- **3.10 (the VM version, and the one that matters):** expect the ladder to be
  **larger** than on 3.12, not smaller. The specializing interpreter in 3.11+
  already cheapens exactly what T1/T2 remove — `LOAD_ATTR` on instances, `CALL`
  of bound methods, `BINARY_OP` on small ints. On 3.10 every one of the 341,601
  `snoopbits` calls is a full unspecialized call with a frame push. The
  algorithmic items (MTF, RLE4, BWT counting sort) should be roughly
  version-neutral, being dominated by C-level work in both cases.
  Quantitative expectation: **T3 around 3.2-4.0x on 3.10** against ~3.0x on 3.12.
  Numbers pending.

---

## 3. cProfile — the hotspot actually moving

CPython 3.12.6, one decode, via `bench.py --profile <tier>`.

**Total function calls: 3,185,455 -> 423,176 (7.5x fewer). Profiled time 1.186 s -> 0.285 s.**

### T0 stock (1.186 s, 3,185,455 calls) — one dominant tower plus a long tail

| tottime | cumtime | ncalls | function |
|---|---|---|---|
| 0.241 | 1.172 | 1 | `decode_huffman_block` |
| **0.152** | **0.519** | **148,271** | **`find_next_symbol`** (the tower) |
| 0.110 | 0.110 | 92,803 | `move_to_front` |
| 0.107 | 0.182 | 1 | `bwt_reverse` |
| 0.104 | 0.246 | 341,601 | `snoopbits` |
| 0.087 | 0.087 | 766,811 | `list.append` |
| 0.085 | 0.129 | 156,708 | `readbits` |
| 0.072 | 0.072 | **655,017** | `_mask` |
| 0.055 | 0.055 | 674,570 | `len` |
| 0.033 | 0.095 | 67,562 | `_more` |
| 0.032 | 0.049 | 67,562 | `_read` |
| 0.027 | 0.042 | 1 | `bwt_transform` |
| 0.013 | 0.013 | 1 | `sorted` |

### T3 (0.285 s, 423,176 calls) — the tower is gone; two balanced peaks remain

| tottime | cumtime | ncalls | function |
|---|---|---|---|
| **0.106** | 0.284 | 1 | `decode_huffman_block` (Huffman+MTF+RUN, all inlined) |
| **0.104** | 0.113 | 1 | **`bwt_reverse`** (the new hotspot) |
| 0.011 | 0.011 | 89,837 | `list.pop` (MTF) |
| 0.010 | 0.010 | 111,853 | `list.append` |
| 0.009 | 0.009 | 1 | `_collections._count_elements` (histogram) |
| 0.009 | 0.009 | **8,543** | `re.Pattern.search` (RLE4; was 336k iterations) |
| 0.009 | 0.009 | 89,837 | `bytearray.append` |
| 0.006 | 0.018 | 1 | `rle4_expand` |
| 0.002 | 0.002 | 16,891 | `int.from_bytes` (refills; was 67,562 `f.read(1)`) |

`find_next_symbol`, `snoopbits`, `readbits`, `_mask`, `_more`, `_read`,
`move_to_front` and `sorted` have **all left the profile entirely** on the bzip2
path. The story for the talk is exact: *the Huffman matcher tower collapses, and
what is left is the serial inverse-BWT pointer chase* — which is the thing you
cannot fix in software and therefore the thing you build hardware for.

Intermediate tiers, for the ladder slide: T1 1,650,795 calls / 0.652 s;
T2 994,266 calls / 0.454 s.

---

## 4. Rust / PyO3 design for the critical path

Crate: `rust/pyflate/` (`Cargo.toml`, `src/lib.rs`, `README.md`).
It **cannot be compiled in this session** (no cargo/rustc on the Windows side,
and installing a toolchain was out of scope), so it is written to be
correct-by-inspection, with the expected gain argued from the measured profile
rather than measured directly. The WSL environment note says rustc 1.98 and
maturin 1.15 are available there, and that a `cp310 manylinux_2_34` wheel built
there is directly usable on the course VM (glibc 2.35) — so the build step is a
one-command follow-up, not a redesign.

### The scoping line, and why it is drawn there

**Rust gets exactly two kernels:**

1. `decode_symbols(data: &[u8], bit_pos: u64, tables: Vec<Vec<u8>>, selectors:
   &[u8], symbols_in_use: u32, favourites: &[u8]) -> (Vec<u8>, u64)`
   — the `HuffmanGroupDecoder`. In: the raw compressed buffer, the current bit
   offset, the six code-length vectors, the selector list. Out: the fully
   MTF-decoded, RUNA/RUNB-expanded byte stream for the block (i.e. the BWT input
   `L`), plus the new bit offset. This is one FFI crossing per block that
   replaces **148,271 Huffman decodes + 89,837 MTF operations**.
2. `bwt_inverse(l: &[u8], ptr: u32) -> Vec<u8>` — optional second kernel, one
   crossing, replacing the 336,184-step serial pointer chase.

**Python keeps:** the stream magic and header parse, blocksize, the `used`
bitmap (`compute_used`), the selector MTF list (`compute_selectors_list`), the
delta-coded code-length reading (`compute_tables` bit loop), the block loop,
the RLE4 expansion, the `b"".join`, and the MD5 check.

**A full `bzip2_main` in Rust is benchmark deletion and must not be done.** The
reason is not squeamishness, it is that the benchmark stops measuring anything.
`bm_pyflate` exists to time *a pure-Python decompressor*; if the whole
decompressor is native, the remaining Python is a `open()` and a hash, and the
result is indistinguishable from `import bz2` with extra steps. The line drawn
here is the same line CPython itself draws with `_json` and `_pickle`: **a
native kernel may replace an inner loop that the profile identifies; it may not
replace the program.** Concretely: after these two kernels, Python still runs
the whole block structure, still parses every header field bit by bit, and still
does the final RLE4 expansion — roughly 25-30% of the optimized runtime stays
interpreted, and the Amdahl ceiling is honest and visible.

### Why the boundary is cheap

A PyO3 call costs roughly 25-60 ns plus per-argument conversion. Here there is
**one crossing per block** (two if `bwt_inverse` is used), and the arguments are
a zero-copy `&[u8]` borrow of the input `bytes`, six small `Vec<u8>` code-length
vectors (147 bytes each), and a selector list of ~2,966 bytes. Return is a
single `Vec<u8>` -> `PyBytes`. Marshalling is microseconds against a ~150 ms
block. This is the pydantic-core / polars shape: hand the data over once, do all
the work natively, hand one buffer back.

### Kernel design (matches the Python T3 tier, so the two validate each other)

- Bit reader: `u64` accumulator, `refill()` when `nbits < 32`, MSB-first, over a
  `&[u8]` with 8 bytes of tail padding. No bounds checks in the hot path beyond
  the refill guard.
- Huffman: exactly the T3 structure — per group, `limit[l]`, `base[l]`, `perm[]`
  built by the same canonical construction, plus a flat `Vec<u32>` primary table
  of `1 << PRIMARY_BITS` entries packed as `(sym << 5) | len`. One index resolves
  99.6% of symbols; longer codes step canonically. In Rust the flat table is
  unambiguously the right call (it is a `Vec<u32>` of 2048 entries = 8 KB, L1
  resident, and there is no interpreter overhead to hide behind).
- MTF: a 256-byte array with `copy_within` for the shift. At mean rank 7.2 this
  is a ~7-byte `memmove` — the same complexity argument as the Python tier, but
  now with no object overhead at all. (This array *is* the shift-register CAM of
  the hardware proposal, which is why the two designs mirror each other.)
- RUNA/RUNB: accumulated in the same loop, emitted with `extend_from_slice` /
  `resize`.
- Table switch every 50 symbols driven by the selector list, exactly as Python.

### Expected gain, argued from the measured profile

From the T3 cProfile: `decode_huffman_block` (the Huffman+MTF+RUN loop) is
0.106 s and `bwt_reverse` is 0.104 s of a 0.285 s profiled decode — call it
~45% and ~40% of a ~150 ms real decode, with RLE4 and the header work making up
the rest.

- Kernel 1 alone: native symbol decode should run 20-50x faster than the
  interpreted loop (it is pure integer work on cache-resident tables). Taking a
  conservative 20x, ~67 ms of Python becomes ~3 ms, giving roughly
  **1.8x over T3** end to end, i.e. **~5.5x over stock**.
- Kernels 1+2: the BWT walk is latency-bound rather than dispatch-bound, so it
  gains less — maybe 8-15x rather than 20-50x. ~60 ms becomes ~5 ms, giving
  roughly **3.5x over T3**, i.e. **~10x over stock**, with the residual being
  RLE4 plus the Python header parsing.
- These are estimates, explicitly labelled as such. The honest framing for the
  talk is the Amdahl one: *each kernel you move gives less than the last, and
  the Python you keep sets the ceiling.*

The Rust kernel also doubles as the **behavioral spec for the hardware
proposal**: its FFI boundary (input buffer + bit offset + table region +
selector list in, symbol buffer out) is exactly the DMA descriptor of the
accelerator in §6.

---

## 5. Risk assessment — could a grader call any tier benchmark deletion?

Ranked most to least defensible.

1. **T1 (micro).** Unimpeachable. Bulk I/O instead of `read(1)` per byte, fewer
   method calls, a `bytearray` instead of a list of one-byte `bytes` objects.
   Nobody can call this anything but competent Python. **And it alone clears the
   7% bar by more than 4x**, which is the safety net for the whole benchmark.
2. **T2 (canonical Huffman).** Very defensible — arguably the *most* defensible
   change in the project. The file docstring says, verbatim, "there is certainly
   some room for improvement in the Huffman bit-matcher", and canonical decode is
   the textbook fix that both libbzip2 and zlib use. Same algorithm class, same
   bit stream, same symbol sequence, same output.
3. **T3 back end (counting-sort BWT, reversed-list MTF).** Defensible. Counting
   sort replacing a comparison sort used only to derive 256 bucket offsets is a
   pure algorithm-class improvement that any algorithms course would mark
   correct. The MTF change is a data-structure orientation change with an
   O(n) -> O(rank) argument backed by a measured rank distribution.
4. **T3 regex RLE4.** Defensible, with one caveat worth disclosing rather than
   hiding: it pushes a byte-scanning loop into the C regex engine. That is using
   the standard library the way it is meant to be used — the same category as
   `bytes.join` instead of `+=`, or `bytes.count` instead of a loop — and `re`
   ships with CPython. But a strict grader could ask whether Python is still
   doing the work. The defence: the algorithm is unchanged (same left-to-right
   run semantics, verified byte-for-byte), only the scan is delegated, and the
   ablation table shows exactly what it is worth. If someone objected, dropping
   it costs 32 ms and the benchmark still clears 7% by a mile.
5. **T3 flat Huffman table.** Defensible and standard (it is what inflate does),
   and conveniently the *least* valuable change at ~5%. If challenged it can be
   dropped almost for free — a good position to be in.
6. **Rust kernel (designed, not landed).** Gray zone by construction. Scoped as
   in §4 it is the same argument CPython makes with its own C accelerators.
   Present it as an *additional* optimization stage on top of a pure-Python tier
   that already clears the bar, and clear it with staff before relying on it.

**What would be cheating, and is not done anywhere:** calling `bz2` or `zlib`;
caching the decoded output across loops; weakening, moving or removing the MD5
check; changing the input file; hoisting work out of the timed region. The MD5
check is byte-identical to stock, sits in the same place, and every tier is
*additionally* verified byte-for-byte against `bz2.decompress` by `bench.py`.

**One disclosure, for honesty.** The landed file changes the gzip dispatch from
`gzip_main(field)` to `gzip_main(field.remainder())`, because the new bit reader
is buffer-backed rather than file-backed. That path **cannot execute** for this
benchmark (the input is bzip2, magic `0x425a`) and is **already broken in stock
on Python 3**: `gzip_main` ends by joining a list of `bytes` with a `str`
separator, which raises `TypeError`. Verified against the unmodified upstream
file. The whole DEFLATE half of the module — `Bitfield`, `HuffmanTable`,
`OrderedHuffmanTable`, `find_next_symbol`, `gzip_main` — is deliberately left
**intact rather than deleted**, precisely so the diff cannot be read as "removed
the parts we did not want to optimize".

---

## 6. Recommendation: should pyflate be one of the two benchmarks we keep?

**Yes — and it should be the anchor benchmark of the talk, not the sidekick.**

### Margin over the required 7%: 10/10

Not close. The bar is 1.07x. T1, the tier anyone could defend line by line, is
**1.3-1.5x**. The landed T3 is **~3.0x on 3.12 and should be larger on the VM
3.10**. There is no plausible measurement dispute at that margin — pyperf noise
here is 7-18% std dev and a 3x mean shift is significant under any t-test. There
are also **four independent sources of win** (Huffman, MTF, BWT, RLE4), so even
if a grader rejects one on principle the benchmark still passes comfortably.
Very few benchmarks give that much slack.

### Presentation story for 20 minutes: 10/10

The arc writes itself and every step has a measured number behind it:

1. "This benchmark is called pyflate but it decodes bzip2" — a small, credible
   hook that shows real analysis rather than skimming.
2. Profile: one dominant tower, `find_next_symbol`, 148,271 calls, 44% cumulative.
3. "The obvious story is that this is an O(258) linear scan. **We measured it. It
   walks 5 entries on average.**" — the best moment in the talk, because it is a
   correction of the obvious answer, backed by a distribution.
4. Explain canonical Huffman codes, fix it properly, show the tower collapse in
   the before/after profile.
5. "Here is the surprise: the fancy O(1) table was worth 5%; the boring RLE4 and
   BWT fixes were each worth 3-4x more." — the ablation table.
6. Show that what is left is a **serial pointer chase** that software cannot fix,
   and pivot to hardware.

Step 6 is the crucial one: the SW section *ends by motivating* the HW section
instead of sitting beside it. Most benchmarks cannot do that.

### Hardware-accelerator story: 10/10 — the strongest in the list

Two named blocks and one exotic closer, all justified by the measured profile:

- **Fixed-function canonical-Huffman decode engine.** A 64-bit barrel-shifter
  bit aligner feeding a length-limited comparator cascade against per-length
  first_code/limit registers, subtract, index a symbol RAM — 1 symbol/cycle. A
  small FSM swaps tables every 50 symbols from the selector list; config and
  tables arrive by DMA descriptor. **This is real silicon: Intel IAA (In-Memory
  Analytics Accelerator, Sapphire Rapids) does exactly this for DEFLATE, with an
  AECS config region holding the tables.** That precedent is worth a slide by
  itself, and an ECE audience already believes in it.
- **MTF engine: 256-entry shift-register CAM.** Parallel compare finds the
  matched entry in one cycle; entries below it shift down; the match moves to
  front. It is the most tractable and most formally checkable RTL block available
  anywhere in this benchmark list — and our measured mean rank of 7.2 gives a
  real area/power trade-off to discuss (256 comparators for 1-cycle latency,
  versus a short shifter that covers rank <= 8 in one cycle and 77% of traffic,
  spilling the rest). That trade-off is derived from **our own measurement**,
  which is exactly what earns marks.
- **PIM inverse-BWT** as the provocative closer — and the profile now *demands*
  it: after the SW work, `bwt_reverse` is the co-equal hotspot, a 336 KB
  data-dependent chain walk that neither Python nor Rust fully fixes. Honest
  nuance: PIM cuts per-step latency but cannot parallelize a single chain.

Note also that the Rust FFI boundary designed in §4 **is** the MMIO/DMA
descriptor of the accelerator. SW optimization, native kernel and HW proposal
become three views of one design, which makes the project cohere instead of
reading as three disconnected deliverables.

### Implementation risk: 9/10 (very low)

- The correctness oracle is **built into the benchmark** (MD5 every run), and we
  added a byte-for-byte `bz2` diff on top. A wrong byte fails loudly; there is no
  silent-corruption failure mode.
- Deterministic, single-threaded, no I/O variance, no RNG, one block.
- The work is **already done and verified** — all four tiers pass MD5 + byte-diff.
- Residual risks are small and bounded: (a) the regex RLE4 could be objected to
  on taste, costing 32 ms to drop; (b) the 3.10 numbers are not yet taken, though
  theory says they should be *better*, not worse; (c) the tail padding in the bit
  reader is a correctness-sensitive detail, mitigated by byte-exact verification.

### The one honest argument against

pyflate is a *long* benchmark to explain: bit reader, Huffman, MTF, RUNA/RUNB,
BWT, RLE4 — six stages before you can even state what was optimized. nbody can
be explained in 30 seconds. If the talk runs tight, pyflate needs a disciplined
pipeline diagram up front. That is a slide-design problem, not a reason to drop
it, and the payoff is that the same diagram carries the hardware section.

### Verdict

**Keep pyflate.** Pair it with whichever of nbody/mdp gives the cleaner *short*
story and let pyflate carry the depth: largest margin, the only "we measured the
obvious answer and it was wrong" moment, and by far the best hardware narrative,
with shipping silicon (Intel IAA) to point at.
