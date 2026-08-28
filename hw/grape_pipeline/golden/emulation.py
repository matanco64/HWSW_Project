"""Emulation model for grape_pipeline: the hardware's exact FP64 operation sequence, IEEE-complete.

Identical to nbody_ref.advance except for r^-1.5, which hardware computes with three correctly
rounded IEEE-754 binary64 (RNE) operations instead of libm pow:
    s = sqrt(dsq); d3 = dsq * s; rcp = 1.0 / d3; mag = dt * rcp
Every other operation is performed in the same order as the benchmark. The RTL must match this
model bit-for-bit (PRD-F2, pair order per PRD-F3); see ADR-0002.

Arithmetic is done on numpy float64 scalars so that IEEE special values propagate (Inf/NaN, e.g.
dsq = 0 for coincident bodies) instead of raising, and the IEEE exception flags are accumulated
as the sticky-flag reference for PRD-F13: advance() returns the set of flags raised
({"invalid", "divzero", "overflow", "underflow"}).
"""
import numpy as np

F = np.float64
_FLAG = {"invalid value": "invalid", "divide by zero": "divzero",
         "overflow": "overflow", "underflow": "underflow"}


def advance(dt, n, bodies, pairs):
    """In-place, like nbody_ref.advance; returns the set of IEEE flags raised."""
    flags = set()

    def _on_err(kind, _flag):
        flags.add(_FLAG.get(kind, kind))

    dt = F(dt)
    old = np.seterrcall(_on_err)
    try:
        with np.errstate(all="call"):
            for _ in range(n):
                for (([x1, y1, z1], v1, m1), ([x2, y2, z2], v2, m2)) in pairs:
                    dx = F(x1) - F(x2)
                    dy = F(y1) - F(y2)
                    dz = F(z1) - F(z2)
                    dsq = dx * dx + dy * dy + dz * dz
                    s = np.sqrt(dsq)
                    d3 = dsq * s
                    rcp = F(1.0) / d3
                    mag = dt * rcp
                    b1m = F(m1) * mag
                    b2m = F(m2) * mag
                    v1[0] = float(F(v1[0]) - dx * b2m)
                    v1[1] = float(F(v1[1]) - dy * b2m)
                    v1[2] = float(F(v1[2]) - dz * b2m)
                    v2[0] = float(F(v2[0]) + dx * b1m)
                    v2[1] = float(F(v2[1]) + dy * b1m)
                    v2[2] = float(F(v2[2]) + dz * b1m)
                for (r, [vx, vy, vz], m) in bodies:
                    r[0] = float(F(r[0]) + dt * F(vx))
                    r[1] = float(F(r[1]) + dt * F(vy))
                    r[2] = float(F(r[2]) + dt * F(vz))
    finally:
        np.seterrcall(old)
    return flags
