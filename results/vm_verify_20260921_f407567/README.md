# VM correctness evidence — 2026-09-21, revision `f407567`

**This is not a timing run.** No measurement was taken here and nothing in this
directory may be quoted as a performance number. The headline timings come from
`results/vm_canonical_20260910_2c8c754/` (Appendix A7).

It exists to put two claims on the course VM rather than on a development host.

| Artifact | What it shows |
|---|---|
| `environment.txt` | `ubuntu-server`, Linux 5.15.0-1106-kvm, CPython 3.10.12, cargo/rustc 1.98.0, maturin 1.14.1 |
| `rust_tests.log` | `cargo test` on the VM: **11 passed, 0 failed** |
| `check_all.log` | `tools/check_all.sh --require-native`: **all 8 checks pass**, including the Rust kernel bit-identical to stock at **N = 5, 10 and 31** after 20,000 steps, and the pyflate kernel against its golden model |
| `build_{nbody,pyflate}.log`, `wheel_*.json` | both wheels built from this revision on the VM, with the imported module path and SHA-256 |

Why it was needed: the eleventh crate test (a Kraft-complete property test) was
added after the timed revision, so the canonical run's log records ten. The
high-N exactness check was added at the same time and had never been recorded on
the VM at all. Both now are, at the submitted revision.

Reproduce: `export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"`, then
`cargo test` in `rust/pyflate/` and `./tools/check_all.sh --require-native`.
