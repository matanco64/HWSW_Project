# Rust/PyO3 acceleration crates (stage-2 optimizations)

Planned crates (built inside the VM with `maturin develop --release`, no abi3,
`[profile.release] debug = true` for perf symbols):

- `pyflate_kernel/` — block-decode kernel (Huffman group decoder + MTF/RLE/BWT),
  bytes in / symbol stream out, 1-3 FFI crossings per decode.
- `nbody_kernel/` — `advance(dt, n, bodies)` on `[f64; 3]` structs,
  one FFI call per 20,000-step advance.

Wheels are referenced from the benchmark copies' requirements.txt so
`pyperformance run --manifest` installs them into its measured venv.
