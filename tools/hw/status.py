#!/usr/bin/env python3
"""hw-status: the only sanctioned writer of hw/STATUS.json (see hw/FLOW.md, "Tracking").

CLI (matches the hw-* skills):
  status.py init                                   create STATUS.json if missing
  status.py show [<module>]
  status.py next <module>                          -> "<stage> <state>" then "checkpoint" | "-"
  status.py set <module> <stage> <state> [--reason "<text>"]   (reason required for blocked)
  status.py gate <module> <stage> "<criterion>" pass|fail|n/a "<evidence>"
  status.py metric <module> dv.<key>|ppa.<key> <value>          (also: metric <m> dv <key> <v>)
  status.py render                                 regenerate hw/PROGRESS.md
Library: load(), save(), next_stage(), STAGES, STATES, CHECKPOINTS, GATES.
"""

import datetime
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
HW = ROOT / "hw"
STATUS = HW / "STATUS.json"
LESSONS = HW / "docs" / "lessons.md"

MODULES = ["grape_pipeline", "huffman_engine", "mtf_cam"]
STAGES = ["prd", "mas", "uarch", "rtl", "dv_testplan", "dv_bringup",
          "dv_coverage", "dv_signoff", "ppa", "integration"]
STATES = ["todo", "in_progress", "review", "done", "blocked"]
CHECKPOINTS = {"prd", "mas", "uarch", "dv_signoff"}
RESULTS = ["pass", "fail", "n/a"]

# Gate criteria, wording taken from the FLOW.md stage table.
GATES = {
    "prd": ["every requirement has a measurable KPI + acceptance test", "HW/SW split table",
            "workload slice quantified from results/ profile", "hw-review findings resolved"],
    "mas": ["I/O table with widths + clock", "register map (offset, name, bits, access, reset)",
            "DMA/stream protocol", "driver API sketch", "block diagram", "hw-review resolved"],
    "uarch": ["pipeline/FSM diagrams", "number formats fixed", "memories sized",
              "per-stage timing budget", "latency/throughput derived and matches PRD KPI",
              "hw-review resolved"],
    "rtl": ["make lint clean (verilator --lint-only -Wall)",
            "Yosys synth succeeds (synthesizable subset)", "agent code review resolved"],
    "dv_testplan": ["features ↔ tests ↔ covergroups ↔ checkers matrix",
                    "golden-model interface defined", "formal properties listed"],
    "dv_bringup": ["pyuvm env instantiates", "first directed test passes on Verilator",
                   "scoreboard compares against golden"],
    "dv_coverage": ["constrained-random sequences", "line/toggle ≥ 90 %",
                    "all functional covergroups hit"],
    "dv_signoff": ["golden equivalence on the full benchmark input",
                   "directed + random suites pass", "coverage goals", "lint clean",
                   "Icarus 4-state run X-free after reset", "formal (sby) where listed"],
    "ppa": ["Yosys+Liberty area + cell counts", "OpenLane 2 run: Fmax, area µm², power",
            "trade-off table (≥2 design points)"],
    "integration": ["register map ↔ driver model consistent",
                    "cycle-accurate speedup estimate vs results/baseline_*",
                    "report §7 bullets mapped"],
}


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def initial() -> dict:
    mods = {}
    for m in MODULES:
        mods[m] = {
            "stages": {s: {"state": "todo", "started": "", "finished": "",
                           "gate": {c: {"result": "n/a", "evidence": ""} for c in GATES[s]}}
                       for s in STAGES},
            "metrics": {"dv": {"line_cov": 0, "toggle_cov": 0, "func_cov": 0,
                               "tests_run": 0, "tests_pass": 0, "formal": "n/a"},
                        "ppa": {"cells": 0, "area_um2": 0, "fmax_mhz": 0, "power_mw": 0}},
        }
    return {"modules": mods, "order": list(MODULES), "stages": list(STAGES), "updated": now()}


def load() -> dict:
    if not STATUS.exists():
        return initial()
    return json.loads(STATUS.read_text(encoding="utf-8"))


def save(data: dict) -> None:
    data["updated"] = now()
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def die(msg: str) -> None:
    print(f"status.py: {msg}", file=sys.stderr)
    sys.exit(1)


def check(data, module=None, stage=None, state=None, result=None):
    if module is not None and module not in data["modules"]:
        die(f"unknown module {module!r}; known: {', '.join(data['order'])}")
    if stage is not None and stage not in data["stages"]:
        die(f"unknown stage {stage!r}; known: {', '.join(data['stages'])}")
    if state is not None and state not in STATES:
        die(f"unknown state {state!r}; known: {', '.join(STATES)}")
    if result is not None and result not in RESULTS:
        die(f"unknown gate result {result!r}; known: {', '.join(RESULTS)}")


def next_stage(data: dict, module: str):
    """First stage not done -> (stage, state, is_checkpoint); (None, None, False) if all done."""
    for s in data["stages"]:
        st = data["modules"][module]["stages"][s]["state"]
        if st != "done":
            return s, st, s in CHECKPOINTS
    return None, None, False


def render() -> None:
    subprocess.run([sys.executable, str(ROOT / "tools" / "hw" / "render_progress.py")], check=False)


# ---------------------------------------------------------------- commands
def cmd_init(data, args):
    if STATUS.exists():
        print(f"{STATUS.relative_to(ROOT)} already exists")
        return
    save(data)
    if not LESSONS.exists():
        LESSONS.parent.mkdir(parents=True, exist_ok=True)
        LESSONS.write_text("# Hardware-flow lessons\n\nAppended by `hw-advisor` after each gate; "
                           "one entry per lesson (date, module/stage, friction, fix).\n",
                           encoding="utf-8")
    print(f"created {STATUS.relative_to(ROOT)}")


def cmd_show(data, args):
    mods = args[:1] if args else data["order"]
    for m in mods:
        check(data, module=m)
        print(m)
        for s in data["stages"]:
            st = data["modules"][m]["stages"][s]
            gate = st["gate"]
            passed = sum(1 for g in gate.values() if g["result"] == "pass")
            extra = f"  reason: {st['reason']}" if st.get("reason") else ""
            print(f"  {s:<12} {st['state']:<12} gate {passed}/{len(gate)}{extra}")


def cmd_next(data, args):
    if not args:
        die("usage: next <module>")
    check(data, module=args[0])
    s, st, cp = next_stage(data, args[0])
    if s is None:
        print("done done")
        print("-")
        return
    print(f"{s} {st}")
    print("checkpoint" if cp else "-")


def cmd_set(data, args):
    reason = None
    if "--reason" in args:
        i = args.index("--reason")
        reason = args[i + 1] if i + 1 < len(args) else ""
        args = args[:i] + args[i + 2:]
    if len(args) != 3:
        die('usage: set <module> <stage> <state> [--reason "<text>"]')
    m, s, state = args
    check(data, module=m, stage=s, state=state)
    if state == "blocked" and not reason:
        die("--reason is required when state is blocked")
    st = data["modules"][m]["stages"][s]
    st["state"] = state
    if state == "in_progress" and not st.get("started"):
        st["started"] = now()
    if state == "done":
        st["finished"] = now()
        st.pop("reason", None)
    if reason is not None:
        st["reason"] = reason
    save(data)
    print(f"{m}/{s} -> {state}")


def cmd_gate(data, args):
    if len(args) != 5:
        die('usage: gate <module> <stage> "<criterion>" pass|fail|n/a "<evidence>"')
    m, s, crit, result, evidence = args
    check(data, module=m, stage=s, result=result)
    data["modules"][m]["stages"][s]["gate"].setdefault(crit, {})
    data["modules"][m]["stages"][s]["gate"][crit] = {"result": result, "evidence": evidence,
                                                     "at": now()}
    save(data)
    print(f"{m}/{s} gate [{crit}] = {result}")


def cmd_metric(data, args):
    if len(args) == 4:                       # metric <m> dv <key> <v>
        m, group, key, value = args
    elif len(args) == 3 and "." in args[1]:  # metric <m> dv.<key> <v>
        m, gk, value = args
        group, key = gk.split(".", 1)
    else:
        die("usage: metric <module> dv.<key>|ppa.<key> <value>")
    check(data, module=m)
    metrics = data["modules"][m]["metrics"]
    if group not in metrics:
        die(f"unknown metric group {group!r}; known: dv, ppa")
    try:
        v = float(value)
        value = int(v) if v.is_integer() else v
    except ValueError:
        pass
    metrics[group][key] = value
    save(data)
    print(f"{m} {group}.{key} = {value}")


def cmd_render(data, args):
    render()


COMMANDS = {"init": cmd_init, "show": cmd_show, "next": cmd_next, "set": cmd_set,
            "gate": cmd_gate, "metric": cmd_metric, "render": cmd_render}


def main(argv) -> None:
    if not argv or argv[0] not in COMMANDS:
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(2)
    COMMANDS[argv[0]](load(), argv[1:])


if __name__ == "__main__":
    main(sys.argv[1:])
