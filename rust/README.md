# Rust/PyO3 acceleration crates

A native tier for the hot kernel of a benchmark, kept deliberately narrow: the
harness, the orchestration and the I/O stay in Python, and only the inner loop
crosses into Rust. The same argument CPython itself makes with `_json` and
`_pickle`.

Two rules hold for every crate here:

1. **Scope.** Port the kernel, never the benchmark. A crate that swallows the
   whole workload is benchmark deletion, not optimization.
2. **Bit-identity.** Mirror the Python expression order exactly, and prove it
   with a checker rather than asserting it. No FMA contraction, no
   reassociation, no fast-math — see each crate's floating-point contract.

## Built

### `nbody/` — `nbody_rs`

`advance(dt, n)` and `energy()` on a resident `#[pyclass] System` holding
`Vec<Vec3>` positions and velocities plus the fixed pair schedule. One FFI
crossing per call; three per benchmark iteration.

Measured with `dev/nbody/rs_check.py`, 20,000 steps, min of 7 interleaved
rounds, on the course VM's CPython 3.10.12 (the WSL dev box is ~2.4x faster in
absolute terms — 3.1 ms vs 75.6 ms — but lands on the same ratio):

| | |
|---|---|
| kernel speedup | **24.1x** (9.48 ms vs 228.49 ms for 20,000 steps) |
| output | **bit-for-bit identical** — all 35 state floats and `report_energy()` compare `==` after 20,000 steps, `max abs delta = 0.0` |
| FFI crossing | ~224 ns, i.e. 2e-5 of one `advance()` call |

The `Vec3` rewrite of the kernel (grouping x/y/z out of the flat `Vec<f64>`)
was checked against the flat-array version it replaced by building both and
interleaving the runs: 9.45-9.54 ms vs 9.60-9.64 ms, i.e. ~1.5% *faster* --
`Vec<Vec3>` is the same bytes with one bounds check per body instead of three
-- and bit-identical to Python in both.

Build: `maturin build --release -i <python3.10>` produces a
`cp310-cp310-manylinux_2_34_x86_64` wheel. That tag needs glibc >= 2.34 and the
course VM is Ubuntu 22.04 (glibc 2.35), so a wheel built in WSL runs on the VM.

**Not wired into the measured benchmark**, deliberately: the pure-Python tier
already clears the required margin, and an optional import that silently falls
back would make the measured configuration ambiguous. It stands as a tier, and
as the behavioural specification for the `grape_pipeline` accelerator — the
`#[pyclass]` is the register file, `advance(dt, n)` is the doorbell write with
a step-count register, `state()` is the read-back window.

### `pyflate/` — `pyflate_rs`

A `#[pyclass] BlockDecoder`, configured once per block with the code-length
tables, selector list and favourites, then `decode(bit_pos) -> (L, end_bit_pos)`.
Inside: u64 bit reader with 32-bit refills, a flat 2048-entry primary table with
`limit`/`base`/`perm` fallback, the 50-symbol selector-driven table swap,
move-to-front, and RUNA/RUNB.

**The boundary is the hardware boundary.** It covers exactly
bit reader → canonical Huffman → MTF → RUNA/RUNB, which is `huffman_engine` +
`mtf_cam` in `hw/`. Header parsing, `bwt_reverse`, RLE4 and the MD5 check all
stay in Python. `group_tables()` exposes the built tables as the accelerator's
config region, and `--trace` dumps a `PFTRACE1` symbol trace for the RTL
testbench — so one interface serves the native tier, the register map and the
DV golden model.

`bwt_reverse` is deliberately **not** ported. It is an irreducibly serial
399 KB pointer chase, and the report's argument is precisely that no amount of
software fixes it; porting it would blur that.

Measured on CPython 3.10.21, min of 15 interleaved rounds (`dev/pyflate/rs_check.py`):

| | |
|---|---|
| kernel speedup | **25x** (43.4 ms → 1.73 ms) |
| end to end vs pure-Python T3 | **1.68x** (111.3 ms → 66.1 ms) |
| Amdahl cap | **1.73x** — 97-98% of it achieved on every run |
| residual | 80% inverse BWT, 15% RLE4 |
| output | **byte-exact**: `L` and end bit position identical to Python, final output identical to `bz2.decompress`, MD5 matches |
| FFI crossing | 27 ns |

Hitting 97% of the Amdahl cap is the point worth quoting: the kernel is
essentially free now, and everything left is the serial tail.

**Measurement note.** The same Python function timed 42 ms in one script and
92 ms in another on the same machine, so `rs_check.py` interleaves the variants
round-robin rather than timing them sequentially. An early sequential version
produced an impossible "1.84x against a 1.61x cap".

## Not built

There is **no mdp crate**. mdp is a measured candidate, not a submitted
benchmark; if it were revived, the natural boundary is the CSR value-iteration
sweep, whose export format is already the accelerator's DMA layout.
