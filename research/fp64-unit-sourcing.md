# FP64 unit sourcing spike — grape_pipeline uArch input

Date: 2026-09-04. Research agent, primary sources; feeds ADR-0007. Items marked *[unverified]*.

## CVFPU / FPnew (openhwgroup/cvfpu)
- FP64 add/sub/mul/FMA/div/sqrt, all IEEE rounding modes. Div/sqrt via `DivSqrtSel`: PULP
  (fpu_div_sqrt_mvp, Solderpad 0.51, iterative non-pipelined, 3 bits/cycle → FP64 div/sqrt =
  21 cycles), TH32 (FP32 only), THMULTI (*rounding status unverified*).
- **Red flag (README):** "compliance issues … for the PULP DivSqrt unit. Rounding mismatches …
  off by 1 ulp"; inexact flag can be missed → conflicts with ADR-0002 correctly-rounded sqrt.
- Tooling: Verilator OK (CVA6 TB); stock Yosys cannot parse it (cva6 #2319) — needs yosys-slang
  (Basilisk tapeout, arXiv 2505.10060) or sv2v. Licence Solderpad 0.51 / Apache-2.0.
- Area/latency (GF22, arXiv 2007.01530): full FPU 247 kGE; FP64 FMA 4 cycles II=1; DIVSQRT 19 kGE.

## Berkeley HardFloat
Verilog-2001, BSD-3, IEEE-conformant incl. subnormals; add/mulAdd are combinational (pipeline
registers are ours to add); `divSqrtRecFN_small` ≈ 1 bit/cycle → 55–60-cycle FP64 sqrt,
non-pipelined; recoded internal format. Good as a DV reference checker.

## lowRISC / OpenCores
No FP64 candidates (Ibex/OpenTitan integer-only; OpenCores double_fpu lacks sqrt, licence unclear).

## Own plain-SV datapath (chosen — ADR-0007)
add 3–4 st, mul 3–4 st, pipelined SRT-radix-4 sqrt 28–32 cycles (⌈55/2⌉ iterations, II 1..5),
NR reciprocal 12–16 cycles (2^10×20b ROM seed, 3 quadratic iterations, FMA-compensated final step
→ ≤ 1 ulp / correctly rounded; Borges arXiv 2112.14321). Effort ~15–22 days with the bit-exact
emulation model. Never fuse mul+add where Python rounds separately; FMA hardware only inside NR.

## K1 arithmetic (pipelined, pair i issues at cycle 2i, II = 2 front end)
sub 3 → dsq 11 → sqrt 30 → d3 3 → rcp 14 → mag/b1m/b2m 9 → forces 3; pair 9 forces ready ≈ 88;
ordered accumulate on 2 FMA lanes (3 cycles/pair, hazard stalls ≤ 8) → ≈ 104; integrate 15 FMAs
on 2 lanes ≈ 12; FSM 4 ⇒ **≈ 120 ≤ 128** (worst corner sqrt 32/rcp 16 ≈ 126).

## sky130 area sanity
266 kGE/mm² raw (SkyWater docs). FP64-only inventory (2 add, 2 mul, sqrt, rcp, 2 FMA ≈ 180–250
kGE) ≈ 0.7–0.95 mm² at II = 1..2 — inside the 1.0 mm² soft ceiling; II-folding is the relief valve.

Sources: github.com/openhwgroup/cvfpu (+docs, README), github.com/pulp-platform/fpu_div_sqrt_mvp,
arXiv 2007.01530, arXiv 2505.10060, arXiv 2406.15107, github.com/openhwgroup/cva6 (#2319),
jhauser.us/arithmetic/HardFloat.html, opencores.org/projects/double_fpu, arXiv 2112.14321,
skywater-pdk.readthedocs.io (foundry libraries), cvfpu #39.
