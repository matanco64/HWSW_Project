# nbody software tiers on the course VM (2026-10-05)

`dev/nbody/` and `benchmarks/bm_nbody/` at 80ba1dd, copied to a clean /tmp
directory on the VM, CPython 3.10.12, `taskset -c 0`, estimator = min over
interleaved rounds (see each script's docstring). NumPy is not installed on
the VM, so the NumPy anti-result was skipped (development numbers only).

| file | contents | usable? |
|---|---|---|
| run1_ladder_variants_sweep.log | `bench.py --rounds 21`; `t1_variants.py --rounds 15`; `sweep_n.py` (timed); `sweep_n.py --build-only`; `sweep_n.py --emitter-ab` | ladder, build-only and emitter A/B: yes. **t1_variants: no** (control read 0.945x). **Timed sweep: no** -- see below |
| run2_sweep_python_backend.log | `HWSW_BACKEND=python sweep_n.py --bodies 5,...,400 --rounds 7` | yes |
| run3_t1_variants_41rounds.log | `t1_variants.py --rounds 41` | yes (control 0.998x) |

**Run 1's timed sweep is invalid above N = 5.** nbody_rs is installed on the VM,
so `run_benchmark._configure()` binds `advance` to the rolled stock loop for
N > 5 (the native path never calls it); the "opt" column therefore timed stock
against stock. Run 2 forces the Python backend and is the one to quote.
In run 2, N = 400 reads 1.00x by design: 79,800 pairs exceeds
`_MAX_UNROLL_PAIRS` (20,000), so the benchmark deliberately uses the rolled loop.

Headline numbers:

| | VM |
|---|---|
| T1 micro-opt AoS | 1.108x |
| T2 SoA flat lists | 0.917x |
| T3e unrolled, bit-exact (shipped) | 1.593x |
| T3 sqrt / T3f sqrt+fold | 1.614x / 1.596x |
| direct indexing (t1_variants B) | 0.923x |
| velocity locals (D) / shipped T1 (G) | 1.110x / 1.105x |
| unrolled vs stock, N = 5 / 50 / 200 | 1.60x / 1.45x / 1.39x (bit-exact at every N) |
| Rust vs stock, any N | 21.6x to 23.3x |
| hoisted-temporaries emitter, N = 32 / 50 / 100 | 1.066x / 1.081x / 1.054x |
| compile time of the unrolled function, N = 5 / 100 / 400 | 1.2 ms / 455-643 ms / 7.2-8.1 s |
