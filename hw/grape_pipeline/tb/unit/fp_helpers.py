"""Bit-exact FP64 oracle for the unit tests (rtl_contracts.md). numpy float64 = IEEE binary64
RNE with full subnormals — the same semantics as golden/emulation.py."""
import math
import struct

import numpy as np

CANON_QNAN = 0x7FF8000000000000
_FLAG = {"invalid value": 8, "divide by zero": 4, "overflow": 2, "underflow": 1}


def f2b(x: float) -> int:
    return struct.unpack(">Q", struct.pack(">d", x))[0]


def b2f(b: int) -> float:
    return struct.unpack(">d", struct.pack(">Q", b))[0]


def ref_op(op: str, a_bits: int, b_bits: int = 0):
    """Returns (result_bits, flags) for op in {add, sub, mul, sqrt, rcp}; NaN results canonical."""
    flags = 0

    def _cb(kind, _f):
        nonlocal flags
        flags |= _FLAG.get(kind, 0)

    a = np.float64(b2f(a_bits))
    b = np.float64(b2f(b_bits))
    old = np.seterrcall(_cb)
    try:
        with np.errstate(all="call"):
            if op == "add":
                r = a + b
            elif op == "sub":
                r = a - b
            elif op == "mul":
                r = a * b
            elif op == "sqrt":
                r = np.sqrt(a)
            elif op == "rcp":
                r = np.float64(1.0) / a
            else:
                raise ValueError(op)
    finally:
        np.seterrcall(old)
    rb = f2b(float(r))
    if math.isnan(float(r)):
        rb = CANON_QNAN
    # numpy underflow flag: raised only when tiny AND inexact (IEEE default) — matches hardware.
    return rb, flags
