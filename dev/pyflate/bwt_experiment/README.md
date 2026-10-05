# Inverse BWT in Rust: experiment scripts

Branch `experiment/bwt-rust` only, not part of the submission. Write-up: `report_bwt_rust.md`.
All scripts take the benchmark directory (`benchmarks/bm_pyflate`) as their first argument.

| Script | What it does |
|---|---|
| `bwt_check.py` | Swaps each Rust variant into the full pyflate pipeline and checks the output byte-for-byte on 10 bz2 streams (periodic, odd length, 1 byte, random, multi-block, the benchmark). |
| `stages.py` | Per-stage time of one decode (`HWSW_BWT=python` or `rust`). |
| `bwt_time.py` | Kernel time of each variant, measured inside Rust, vs the Python functions. |
| `dump.py` + `phases.rs` | Dumps the BWT input `L` of the benchmark block and of a ~810 KB block; `phases.rs` (standalone, `rustc -O phases.rs`) splits histogram, table build and walk time. Usage: `python dump.py <bench dir> <out dir>`, then `./phases <out>/bench.L <end>` with the end pointer it prints. |
