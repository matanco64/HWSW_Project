---
status: accepted
---
# grape_pipeline: own plain-SystemVerilog FP64 units (3 add, 3 mul, SRT-radix-4 sqrt, NR reciprocal; no FMA); II=2 static schedule

The datapath needs IEEE binary64 RNE add/mul, a **correctly rounded** sqrt and a ≤ 1-ulp
reciprocal (ADR-0002). The spike (`research/fp64-unit-sourcing.md`) ruled out the candidates:
CVFPU's PULP div/sqrt documents 1-ulp rounding mismatches and FPnew needs a yosys-slang frontend;
HardFloat is correct but combinational with a 55-cycle serial sqrt; nothing else exists. We build
our own: pipelined add (3 stages), mul (3 stages), **fully pipelined SRT-radix-4 sqrt (30 ± 2
cycles, II = 2)** and an NR reciprocal engine (2^10 × 20-bit ROM seed, three quadratic
iterations, FMA-compensated final step per Borges arXiv 2112.14321) — ~13–19 days of work (no FMA unit)
against the existing bit-exact emulation model, in a guaranteed Yosys/Verilator-clean subset,
no licence friction. Structure (uArch Q1 = "c then a", corrected by the uArch review R1–R6 and the cycle-accurate
schedule model `docs/schedule_model.py`): **no FMA units at all** — every Python-visible mul and
add/sub is its own rounded binary64 op (fusion would break bit-exactness; FMA-style residual
arithmetic exists only inside the rcp engine's fixed-point internals, which are not
Python-visible). Inventory: **3 add, 3 mul, 1 pipelined SRT-r4 sqrt (30 ± 2, II = 2), 1 rcp
engine (22 ± 2, II = 2)**; pairs issue at II = 2; the ordered velocity accumulate runs on the add
units with a per-(body, component) chain scoreboard. Simulated step = **123 cycles nominal, 127
worst corner ≤ K1 128** (2 add/3 mul = 125/129 — rejected, 1 cycle over at the corner; 2 mul
inventories = 133, structurally short of issue bandwidth: 145 mul-ops/step). The fully pipelined II = 1 pipe is the
PPA comparison point. Subnormals: **full IEEE support** (uArch Q6; STATUS bit 16 stays reserved,
the emulation model is untouched). FMA hardware is used only where Python has no intermediate
rounding (inside NR); mul+add pairs that Python rounds separately are never fused. Rejected:
single iterative sqrt (10 × 21 = 210 cycles of occupancy alone busts K1), CVFPU primary
(rounding risk), HardFloat primary (sqrt latency); HardFloat becomes a DV reference checker.
