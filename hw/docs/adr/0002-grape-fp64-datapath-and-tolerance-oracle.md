---
status: accepted
---
# grape_pipeline: IEEE-754 FP64 datapath in the benchmark's operation order, r⁻³ᐟ² as sqrt + reciprocal, tolerance oracle

The pyperformance nbody kernel runs in Python floats (binary64) and CPython's `dsq ** -1.5` calls
glibc `pow`, which is not correctly rounded (≤ 0.54 ulp); bit-exact reproduction of the Python
trajectory is therefore not a meaningful target, and GRAPE-style reduced precision (FP32/LNS pairs,
wide fixed accumulate; 1e-3…1e-6 force error) visibly diverges from the FP64 energy trace. We
decided: every operation is IEEE-754 binary64 round-to-nearest-even, performed in exactly the
order the benchmark performs it (including the software-defined pair order, because FP64
accumulation is order-sensitive), with the single substitution `s = sqrt(dsq); d3 = dsq*s;
rcp = 1/d3; mag = dt*rcp`. Two references follow from this: the *emulation model*
(`golden/emulation.py`), which the RTL matches bit-for-bit, and the *golden model*
(`golden/nbody_ref.py`, the benchmark's own code), against which acceptance is by tolerance:
|E_hw − E_gold|/E ≤ 1e-12 at completion of the 20,000-step run (measured 1.7e-14 at completion,
1.9e-14 max over 1000-step checkpoints) and per-body ‖Δr‖/‖r_gold‖ ≤ 2e-9, ‖Δv‖/‖v_gold‖ ≤ 5e-11
(≈ 19× the per-step maxima 1.06e-10 / 2.64e-12 measured by `golden/calibrate.py`).
Note the oracle compares energies of the two final states, not energy conservation: the
benchmark's own semi-implicit Euler drifts by ~4e-4 over the run.

Considered and rejected: FP32 pairs + fixed accumulate (kept only as a PPA comparison variant);
a correctly rounded fused rsqrt (no open-source unit, more work than sqrt + reciprocal).
Sources: research/hw-algorithms-nbody.md §1, §3, §4.
