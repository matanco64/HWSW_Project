# nbody hardware acceleration — GRAPE lineage and design-space survey

Date: 2026-08-26. Input to the `grape_pipeline` PRD/uArch stages. Compiled by a research agent
from primary sources (URLs at the end); items marked *[unverified]* were taken from abstracts or
secondary summaries only.

Benchmark facts (pyperformance `nbody`): 5 bodies (Sun + Jupiter, Saturn, Uranus, Neptune),
10 precomputed pairs, 20,000 semi-implicit-Euler steps per iteration, dt = 0.01, Python floats
(IEEE-754 binary64). Per pair: `dx,dy,dz; dsq = dx²+dy²+dz²; mag = dt * dsq**-1.5;
v_i -= d*m_j*mag; v_j += d*m_i*mag`; then `r += dt*v`. Energy conservation is the oracle.

## 1. GRAPE (GRAVITY PIPE) datapath and number formats

Per-pair pipeline in every generation: `dx = x_j − x_i → r² = |dx|² + ε² → r⁻³ (or r⁻⁵ for jerk)
→ × m_j → accumulate`.

| Gen (year) | Arithmetic per stage | Pipes/chip, clock, perf | Host I/F | Accuracy |
|---|---|---|---|---|
| GRAPE-1 (1990) | positions fixed-point (subtract in fixed); everything else 8–16-bit **logarithmic** (LNS); force sum wide fixed | 1 pipe/board, ~100 Mflops-equiv, 2.5 W | host bus (VME later) | ~5 % rel. force |
| GRAPE-3 (1993) | 20-bit fixed positions, 14-bit mass, LNS force, 56-bit fixed accumulate | 8 chips/board @ 20 MHz, >4 Gflops/board | VME | ~1–2 % rms |
| GRAPE-4 / HARP (1995) | FP (24-bit mantissa *[unverified]*) + fixed accumulate; force + jerk (Hermite) | 1 pipe @ 32 MHz, ≈0.5–0.6 Gflops/chip; 1692 chips = 1.08 Tflops | VME → PCI-HIB | — |
| GRAPE-5 (1999) | 32-bit fixed positions; 17-bit LNS (15-bit log2, 8 frac bits, zero, sign); 64-bit fixed force / 50-bit potential accumulate; r⁻³ᐟ² and cutoff via on-chip RAM table | 2 real × 6 virtual pipes @ 80 MHz, 38.4 Gflops/board (8 chips) | PCI (10× faster than VME) | ~0.3 % rel. |
| GRAPE-6 (2003) | dx in **64-bit two's-complement fixed**; converted to FP36 (24-bit mantissa, 10-bit exp); r⁻⁵ by **segmented 2nd-order polynomial**; multiplies for m_j·r⁻³, m_j/r; force sum 64-bit fixed, jerk 32-bit fixed | 6 pipes × 8-way virtual multiple pipeline @ 90–96 MHz, 30.8 Gflops/chip; 2048 chips = 63 Tflops | 32-bit/33 MHz PCI (PLX 9080), DMA + FIFO; host sends predicted x, v; gets a, ȧ, φ | ≈FP32-class per pair, exact-ish sums |
| GRAPE-DR (2009) | programmable SIMD, 512 PEs, FP64-capable | 500 MHz, 512 SP / 256 DP Gflops/chip | PCIe | FP64 |
| GRAPE-8 (2012) | fixed-function pipes again | 48 pipes/chip, ~40 flops/interaction, 480 Gflops, 20.5 Gflops/W | PCIe (FPGA bridge) | — |
| MDGRAPE-4 (2014) | 32-bit fixed coords, ~FP32 pairwise, **32-bit fixed** force sum, ROM-table function eval | 64 pipes/SoC @ 0.8 GHz, 51.2 G interactions/s | on-chip Xtensa + network | — |

**Key GRAPE lesson:** cheap per-pair precision (LNS / FP24–36) plus wide fixed-point *accumulation*
so pair errors are random rather than systematic. That accuracy goal (1e-3…1e-6 force error) is
**not** compatible with reproducing pyperformance's FP64 energy trace.

## 2. Other architectures — one-line takeaways

- **Anton (D. E. Shaw):** 32 PPIMs per ASIC @ 800 MHz, each with two unrolled pairwise-interaction
  pipelines; fixed-point datapaths, reciprocal unit + tabulated polynomial evaluators, one pair per
  cycle. Bit widths *[unverified — paywalled]*. Takeaway: table + polynomial function evaluators.
- **GPU (Nyland/Harris/Prins, GPU Gems 3 ch. 31):** 20 flops/interaction, p×p shared-memory tiles,
  `sqrtf` + div, all FP32; >10 G interactions/s on 8800 GTX. Takeaway: tiling is irrelevant at
  N = 5; FP32 gives ~1e-3 energy error vs ~1e-5 for FP64 (Sapporo2 / NBSymple).
- **FPGA, Lienhart et al. (FCCM 2002):** fully pipelined FP N-body/SPH force unit, 60 FP operators,
  3.9 Gflops on one FPGA. Takeaway: custom-width FP pipelines are area-feasible.
- **PROGRAPE / PGR (Hamada–Nakasato):** GRAPE-3-style pipelines on FPGAs with bit-width-parametrised
  fixed/FP/LNS modules; PROGRAPE-3 = 324 Gflops on 4× XC2VP70. Takeaway: parametrised modules are
  the right SystemVerilog style for our design-point exploration.
- **Double-single / double-double on GPUs (Sapporo2):** DS ≈ GRAPE precision; two orders of
  magnitude worse energy than true FP64.

## 3. r⁻³ᐟ² (reciprocal square-root cube) implementation options

| Method | Latency | Area | Accuracy |
|---|---|---|---|
| LNS: log2 table, ×(−1.5), antilog table (GRAPE-1/3/5) | ~3 stages | 2 ROMs, no multiplier | 1e-2 … 3e-3 rel. |
| Segmented 2nd-order polynomial on r² (GRAPE-6, Anton/MDGRAPE) | 3–4 stages | ROM (2⁸–2¹⁰ entries × 3 coeffs) + 2 multipliers | ~24-bit |
| Magic-constant bit hack + Newton–Raphson (0x5FE6EB50C7B537A9 for FP64) | 1 + 4 NR iterations | tiny + one FMA-class multiplier per iteration | 3.4 % → 0.17 % (1 NR) → ~FP64 after 4 |
| ROM seed + NR (y·(3 − x·y²)/2), quadratic convergence | ≈11 cycles for an FP64 reciprocal unit (2¹⁰ × 20-bit ROM + 2 NR) | ROM + 2–3 FP64 multipliers | 53 bits; FMA-compensated final step ⇒ ≤1 ulp / almost always correctly rounded (arXiv 2112.14321) |
| Digit-recurrence (SRT) sqrt + divider | ~30–60 cycles (1–2 bits/cycle) | small, iterative | correctly rounded IEEE sqrt |
| CORDIC (hyperbolic) | ~55 iterations for FP64 | small shifters/adders | slow convergence; poor fit |
| Full IEEE FP64 sqrt → FP64 div (or multiply chain) | ~40 cycles pipelined | FPnew-class FP64 units (open-source SystemVerilog) | correctly rounded per op |

## 4. Numeric-fidelity strategy (recommendation adopted for the PRD)

- CPython `float_pow` calls libm `pow(iv, iw)` with no special case for −1.5. glibc ≥ 2.28 `pow`
  is **not correctly rounded**: worst case ≈0.54 ulp (exp(y·log x) with ~2⁻⁶⁸ internal error).
  `sqrt` *is* correctly rounded. So `dsq**-1.5` in Python already has libm-dependent last bits —
  **bit-exact reproduction of `pow` is not a meaningful target**. Hardware computing 1/(d·√d) with
  two correctly-rounded operations differs by ≤ ~1–2 ulp per pair.
- **Recommend:** IEEE-754 binary64 (RNE) for the whole datapath — subtract, square/sum in the same
  left-to-right order (dx² + dy², then + dz²), mag, mass × mag, v −=, r += — matching the benchmark's
  operation order; r⁻³ᐟ² as FP64 sqrt (SRT or NR) followed by NR reciprocal with an FMA-compensated
  final step. Energy trace then differs from Python only at ~1e-16 relative per step.
- **Oracle:** |ΔE/E| tolerance (~1e-12) plus per-step diff against a NumPy/mpmath reference. Do not
  promise bit-exact trajectories over 20,000 steps (chaotic sensitivity); the symplectic integrator's
  own energy oscillation is O(dt), so a tolerance oracle is robust.
- **Avoid:** FP32 per-pair + wide fixed sum (GRAPE style) — energy error 1e-3…1e-5, visibly
  diverging from the Python trace. Optional PPA-comparison variant: GRAPE-6-style 64-bit fixed
  positions (AU ∈ [−40, 40] fits fixed point at 2⁻⁵⁶ resolution) with FP64 pair arithmetic.

## 5. Algorithmic crossover and integrator facts

- Yokota & Barba (arXiv 1010.1482): treecode vs direct-sum crossover N ≈ 3×10³ (CPU), 2×10⁴ (GPU);
  FMM 3×10³ (CPU), 4×10⁴ (GPU), at force L² error 1e-4. Kawai/Makino/Ebisuzaki: at N ≈ 10⁶ tree is
  ~50× cheaper at 1e-5 accuracy. At N = 5 (10 pairs) direct sum is trivially optimal.
- **Consequence for our accelerator:** the bottleneck is the **serial step dependency** (20,000
  dependent steps), not pair throughput — the latency of the rsqrt chain and the step FSM set
  performance, not pipeline count. PRD KPI = cycles per step.
- The benchmark updates velocities from old positions, then positions from *new* velocities =
  semi-implicit (symplectic) Euler; it conserves a modified Hamiltonian so energy error stays bounded
  (no secular drift), unlike explicit Euler (Hairer–Lubich–Wanner, Acta Numerica 2003).
- Barnes–Hut / FMM role for this project: report discussion + a pair-list input interface on
  `grape_pipeline` so a software tree walk could feed it at large N (stretch demo).

## Unverified
GRAPE-4 mantissa width; Anton PPIP bit widths (HPCA 2008, paywalled); GRAPE-6 "24-bit mantissa"
from ar5iv extraction, not re-read against the PDF; Makino's jun.artcompsci.org was unreachable.

## Sources
- https://en.wikipedia.org/wiki/Gravity_Pipe
- GRAPE-6: https://arxiv.org/abs/astro-ph/0310702 · GRAPE-6A: https://arxiv.org/abs/astro-ph/0504407
- GRAPE-5: https://arxiv.org/abs/astro-ph/9909116 · GRAPE-3 accuracy: https://arxiv.org/abs/astro-ph/9709246
- GRAPE-4: https://arxiv.org/abs/astro-ph/9612090 · https://iopscience.iop.org/article/10.1086/303972
- GRAPE-DR: https://ieeexplore.ieee.org/document/5348841/ · GRAPE-8: https://ieeexplore.ieee.org/document/6468520/
- MDGRAPE-4: https://pmc.ncbi.nlm.nih.gov/articles/PMC4084528/
- Anton: https://en.wikipedia.org/wiki/Anton_(computer) · https://ieeexplore.ieee.org/document/4658650/
- GPU Gems 3 ch. 31: https://developer.nvidia.com/gpugems/gpugems3/part-v-physics-simulation/chapter-31-fast-n-body-simulation-cuda
- Lienhart et al.: https://www.semanticscholar.org/paper/783cf7bd004eedd3c76a5531870d4b6e816275de
- PROGRAPE: https://arxiv.org/pdf/astro-ph/0604295 · http://grape.artcompsci.org/newsletter/051124.html
- Sapporo2: https://arxiv.org/pdf/1510.04068
- Crossover: https://arxiv.org/abs/1010.1482 · https://iopscience.iop.org/article/10.1086/381391
- Semi-implicit Euler: https://en.wikipedia.org/wiki/Semi-implicit_Euler_method
- CPython float pow: https://github.com/python/cpython/blob/main/Objects/floatobject.c
- glibc math errors: https://sourceware.org/glibc/manual/latest/html_node/Errors-in-Math-Functions.html · pow 0.54 ulp: https://sourceware.org/legacy-ml/libc-alpha/2018-06/msg00968.html
- Correctly-rounded NR reciprocal: https://ar5iv.labs.arxiv.org/html/2112.14321
- Fast inverse sqrt: https://en.wikipedia.org/wiki/Fast_inverse_square_root · Ercegovac et al.: https://doi.org/10.1109/12.863031
- FPnew: https://arxiv.org/pdf/2007.01530
- Benchmark source: https://github.com/python/pyperformance/blob/main/pyperformance/data-files/benchmarks/bm_nbody/run_benchmark.py
