#!/usr/bin/env python3
"""Calibration of the PRD tolerances (PRD-F4/F5): emulation model vs golden model over the
benchmark's 20,000 steps. Prints the measured maxima (per step for r/v, at every 1000th step and at
the end for energy) and the platform. PRD bounds: F5 = 2e-9 (r) / 5e-11 (v), ~19x the measured
maxima; F4 = 1e-12 (~50x the energy maximum). Golden side depends on libm pow (<= 0.54 ulp), hence the platform line.

    python3 hw/grape_pipeline/golden/calibrate.py [nsteps]
"""
import math
import platform
import sys

import emulation
import nbody_ref


def rel_norm(a, b):
    d = math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
    return d / max(math.sqrt(sum(x * x for x in a)), 1e-300)


def main(nsteps=20000):
    gold, gp = nbody_ref.benchmark_system()
    emu, ep = nbody_ref.benchmark_system()
    e0 = nbody_ref.report_energy(gold, gp)
    max_r = max_v = max_e = drift = e_final = 0.0
    for i in range(1, nsteps + 1):
        nbody_ref.advance(0.01, 1, gold, gp)
        emulation.advance(0.01, 1, emu, ep)
        for bg, be in zip(gold, emu):
            max_r = max(max_r, rel_norm(bg[0], be[0]))
            max_v = max(max_v, rel_norm(bg[1], be[1]))
        if i % 1000 == 0 or i == nsteps:
            eg = nbody_ref.report_energy(gold, gp)
            ee = nbody_ref.report_energy(emu, ep)
            e_final = abs((ee - eg) / eg)
            max_e = max(max_e, e_final)
            drift = max(drift, abs((eg - e0) / e0))
    print(f"steps                          : {nsteps}")
    print(f"max |dr|/|r| (emu vs golden)   : {max_r:.3e}")
    print(f"max |dv|/|v| (emu vs golden)   : {max_v:.3e}")
    print(f"max |E_emu-E_gold|/E (1000-step checkpoints): {max_e:.3e}; at completion: {e_final:.3e}")
    print(f"golden's own |E(t)-E(0)|/E     : {drift:.3e}  (integrator drift, not an error)")
    print(f"platform                       : {platform.platform()} {platform.libc_ver()} python {platform.python_version()}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20000)
