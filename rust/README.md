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

## Not built

There is **no pyflate or mdp crate**. Earlier revisions of this file listed a
planned `pyflate_kernel/` as though it existed; it never did. If one is added,
the defensible boundary is the symbol-decode loop only — bit reader, canonical
Huffman decode, move-to-front, RUNA/RUNB — which is also exactly the
`huffman_engine` + `mtf_cam` hardware boundary, so one interface would serve
the software tier, the native tier and the RTL golden model at once. A full
`bzip2_main` rewrite would not be defensible.
