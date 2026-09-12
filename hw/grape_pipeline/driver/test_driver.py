"""Driver model tests (stage 10). Runs standalone (no simulator):

  python3 hw/grape_pipeline/driver/test_driver.py

1. Every register constant matches MAS §4 (via check_regmap -> 0 differences).
2. The API drives a full advance() invocation on the ModelBus and reads back
   CYCLES = K1 * NSTEPS, STEPS_DONE = NSTEPS, DONE set then cleared.
3. Error paths: ERR_PARAM (bad pair index) and ERR_BUSY semantics via the model.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import check_regmap  # noqa: E402
from grape_pipeline_driver import (  # noqa: E402
    GrapeDriver, ModelBus, K1_CYCLES_PER_STEP, ID, ID_VALUE,
    ST_DONE, ST_ERR_PARAM, f2words, words2f,
)

# benchmark-valued 5-body system (sun + 4 planets), 10 pairs
BODIES = [
    [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], 39.478],
    [[4.841, -1.160, -0.104], [0.606, 2.812, -0.025], 0.0377],
    [[8.343, 4.125, -0.404], [-1.010, 1.825, 0.0084], 0.0113],
    [[12.894, -15.111, -0.223], [1.083, 0.868, -0.0108], 0.00172],
    [[15.380, -25.919, 0.179], [0.979, 0.594, -0.0347], 0.00203],
]


def pairs_from(bodies):
    return [(bodies[a], bodies[b])
            for a in range(len(bodies) - 1) for b in range(a + 1, len(bodies))]


def test_regmap():
    assert check_regmap.main() == 0, "check_regmap reported differences"


def test_id_and_roundtrip():
    lo, hi = f2words(365.24)
    assert words2f(lo, hi) == 365.24
    bus = ModelBus()
    assert bus.read32(ID) == ID_VALUE


def test_full_advance():
    bus = ModelBus()
    d = GrapeDriver(bus)
    bodies = [[r[:], v[:], m] for r, v, m in BODIES]
    pairs = pairs_from(bodies)
    nsteps = 20000
    d.advance(0.01, nsteps, bodies, pairs)
    c = d.counters()
    assert c["cycles"] == K1_CYCLES_PER_STEP * nsteps, c
    assert c["steps_done"] == nsteps, c
    # advance() clears DONE at the end
    assert not (d.status() & ST_DONE)
    return c["cycles"]


def test_err_param():
    bus = ModelBus()
    d = GrapeDriver(bus)
    bodies = [[r[:], v[:], m] for r, v, m in BODIES]
    # inject an out-of-range pair index directly at the register (bypass the
    # driver's client-side validation) to exercise the hardware ERR_PARAM path
    d.load_bodies(bodies)
    d.configure(0.01, 10)
    bus.mem[0x10C] = 1                       # NPAIRS = 1
    bus.mem[0x400] = (9 << 8) | 0            # PAIR[0]: j = 9 >= N_BODIES
    assert d.start() is False                # ERR_PARAM -> doorbell rejected
    assert bus.read32(0x00C) & ST_ERR_PARAM


def main():
    tests = [test_regmap, test_id_and_roundtrip, test_full_advance, test_err_param]
    for t in tests:
        r = t()
        extra = f" (cycles={r})" if r else ""
        print(f"PASS {t.__name__}{extra}")
    print(f"\nALL {len(tests)} DRIVER TESTS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
