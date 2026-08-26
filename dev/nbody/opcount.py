"""Counts *executed bytecodes per integration step* for each tier.

Wall-clock speedups depend on which CPython you run: 3.11+ specialises
BINARY_OP / BINARY_SUBSCR / STORE_SUBSCR adaptively; the VM's 3.10 does not.
Executed bytecode count does NOT depend on that -- it is a structural property
of the emitted code.  It is therefore the honest way to argue about what a
tier will do on 3.10 without having a 3.10 to run on.

Method: `sys.monitoring` (3.12+) INSTRUCTION events, enabled *locally* on the
`advance` code object only, so we count the hot loop and nothing else.
Instrumented execution is orders of magnitude slower than normal; this is a
counting tool, never a timing tool.

The interesting columns:
  ops/step    total bytecodes executed per integration step
  subscr      BINARY_SUBSCR + STORE_SUBSCR: on 3.10 each is a full
              PyObject_GetItem/SetItem round trip through _PyNumber_Index +
              PyLong_AsSsize_t (visible in the VM perf profile as ~9% of
              samples across list_item/list_ass_item/PyNumber_AsSsize_t/...)
  arith       BINARY_OP: on 3.10 this is binary_op1 + _Py_CheckSlotResult
              generic dispatch (5.75% + 2.22% in the same profile)

    python opcount.py [--steps 20]
"""
import argparse
import collections
import dis
import sys

import t0_stock
import t1_micro
import t2_soa
import t3_unroll

TIERS = [
    ("T0  stock", t0_stock.make_state, t0_stock.advance),
    ("T1  micro-opt AoS", t1_micro.make_state, t1_micro.advance),
    ("T2  SoA flat lists", t2_soa.make_state, t2_soa.advance),
    ("T3e unrolled bit-exact", t3_unroll.make_state_exact,
     t3_unroll.advance_exact),
    ("T3  unrolled sqrt", t3_unroll.make_state, t3_unroll.advance),
    ("T3f unrolled sqrt+fold", t3_unroll.make_state_fold,
     t3_unroll.advance_fold),
]

SUBSCR = {"BINARY_SUBSCR", "STORE_SUBSCR", "BINARY_OP_SUBSCR_LIST_INT"}
ARITH = {"BINARY_OP"}
TOOL_ID = 3


def _target_code(adv):
    """The code object that actually runs the step loop."""
    fn = adv
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn.__code__


def count(mk, adv, steps):
    st = mk()
    code = _target_code(adv)
    if adv.__name__ == "advance" and adv.__module__ == "t3_unroll":
        code = st[1].__code__          # the generated function
    hist = collections.Counter()
    offmap = {i.offset: i.opname for i in dis.get_instructions(code)}

    mon = sys.monitoring
    E = mon.events

    def cb(c, off):
        hist[offmap.get(off, "?")] += 1

    mon.use_tool_id(TOOL_ID, "nbody-opcount")
    try:
        mon.register_callback(TOOL_ID, E.INSTRUCTION, cb)
        mon.set_local_events(TOOL_ID, code, E.INSTRUCTION)
        adv(st, 0.01, steps)
        mon.set_local_events(TOOL_ID, code, 0)
        mon.register_callback(TOOL_ID, E.INSTRUCTION, None)
    finally:
        mon.free_tool_id(TOOL_ID)
    return hist


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--detail", action="store_true")
    a = ap.parse_args()
    if not hasattr(sys, "monitoring"):
        sys.exit("needs CPython >= 3.12 for sys.monitoring")
    print("python %s | bytecodes executed inside advance(), per integration "
          "step (5 bodies, 10 pairs)" % sys.version.split()[0])
    print("%-24s %10s %8s %8s %10s"
          % ("tier", "ops/step", "subscr", "arith", "vs stock"))
    base = None
    for (name, mk, adv) in TIERS:
        h = count(mk, adv, a.steps)
        tot = sum(h.values()) / a.steps
        sub = sum(v for k, v in h.items() if k in SUBSCR) / a.steps
        ari = sum(v for k, v in h.items() if k in ARITH) / a.steps
        if base is None:
            base = tot
        print("%-24s %10.1f %8.1f %8.1f %9.3fx"
              % (name, tot, sub, ari, base / tot))
        if a.detail:
            for k, v in h.most_common():
                print("        %-28s %8.1f" % (k, v / a.steps))


if __name__ == "__main__":
    main()
