"""Golden model for grape_pipeline: wraps the pyperformance nbody kernel, never re-implements it.

Imports benchmarks/bm_nbody/run_benchmark.py (pyperformance 1.14.0) with a stub for pyperf so the
numerics are the benchmark's own bytes. Exposes advance, report_energy, offset_momentum,
combinations and benchmark_system(). Frozen: the acceptance oracle for the accelerator.
"""
import copy
import importlib.util
import pathlib
import sys
import types

_REPO = pathlib.Path(__file__).resolve().parents[3]
_SRC = _REPO / "benchmarks" / "bm_nbody" / "run_benchmark.py"

if "pyperf" not in sys.modules:           # the kernel only needs pyperf at benchmark time
    sys.modules["pyperf"] = types.ModuleType("pyperf")
_spec = importlib.util.spec_from_file_location("bm_nbody_kernel", _SRC)
_bm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bm)

BODIES = _bm.BODIES
advance = _bm.advance
report_energy = _bm.report_energy
offset_momentum = _bm.offset_momentum
combinations = _bm.combinations


def benchmark_system():
    """Fresh copy of the benchmark's initial state after offset_momentum('sun'), plus its pair list.
    Matches bench_nbody(): pairs are built from the same body objects as the state."""
    bodies = copy.deepcopy(list(BODIES.values()))
    offset_momentum(bodies[0], bodies)
    return bodies, combinations(bodies)
