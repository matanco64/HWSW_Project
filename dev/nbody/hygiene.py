"""Measurement hygiene helpers for a noisy Windows desktop.

Two things matter on this box:
  * Raise the process to HIGH_PRIORITY_CLASS and pin it to a single core, so
    the scheduler stops migrating the hot loop between cores mid-measurement.
  * Estimate with min-of-many-short-rounds rather than mean-of-few-long-runs.
    The true cost is a hard lower bound; every perturbation (an interrupt,
    another process, a frequency dip) only ever adds time.  Interleaved
    round-robin ordering then makes slow drift hit every variant alike.

NB the ctypes declarations matter: GetCurrentProcess() returns the pseudo
handle (HANDLE)-1, which truncates to a bogus 32-bit value unless restype is
c_void_p -- with the default int restype SetPriorityClass silently fails.
"""
import os
import sys

HIGH_PRIORITY_CLASS = 0x00000080
REALTIME_PRIORITY_CLASS = 0x00000100


def tune(affinity_cpu=None):
    """Best-effort: high priority + single-core affinity.  Never fatal."""
    if affinity_cpu is None:
        affinity_cpu = int(os.environ.get("NBODY_CPU", "0"))
    notes = []
    if sys.platform == "win32":
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        k32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k32.GetPriorityClass.argtypes = [ctypes.c_void_p]
        k32.SetProcessAffinityMask.argtypes = [ctypes.c_void_p,
                                               ctypes.c_size_t]
        h = k32.GetCurrentProcess()
        try:
            if k32.SetPriorityClass(h, HIGH_PRIORITY_CLASS):
                notes.append("priority=HIGH")
            else:
                notes.append("priority unchanged")
            if k32.SetProcessAffinityMask(h, 1 << affinity_cpu):
                notes.append("affinity=cpu%d" % affinity_cpu)
        except Exception as exc:                       # pragma: no cover
            notes.append("win32 tuning failed: %r" % (exc,))
    elif hasattr(os, "sched_setaffinity"):
        try:
            os.sched_setaffinity(0, {affinity_cpu})
            notes.append("affinity={%d}" % affinity_cpu)
            os.nice(-5)
            notes.append("nice=-5")
        except Exception as exc:                       # pragma: no cover
            notes.append("posix tuning partial: %r" % (exc,))
    return ", ".join(notes) or "no tuning applied"
