#!/usr/bin/env python3
"""Stop hook (only when HW mode is on and something under hw/ changed): warn if hw/**/*.sv changed without a later `make sim`
(hw/.advisor/last_sim.txt is touched by Makefile.cocotb's sim target), and remind to run
the hw-advisor skill. Never blocks; never spawns anything.

Contract (code.claude.com/docs/en/hooks, "Stop decision control" / "Exit code 0"): plain
stdout of a Stop hook is not shown; `systemMessage` shows a warning to the user without
continuing; `hookSpecificOutput.additionalContext` is "non-error feedback" that lets Claude
act once (guarded by stop_hook_active + the 8-continuation cap). We use systemMessage for the
reminder and (by decision) also for the stale-sim warning, so a Stop never auto-continues.
"""
import json
import subprocess
import sys

from _common import HW, ROOT, payload
from mode import get as get_mode

LAST_SIM = HW / ".advisor" / "last_sim.txt"


def changed_hw():
    """(all changed paths under hw/, the .sv subset) from git status; [] on any failure."""
    try:
        r = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", "hw/"], cwd=ROOT, text=True,
                           capture_output=True, timeout=15)
    except Exception:
        return [], []
    files = [line[3:].split(" -> ")[-1].strip() for line in r.stdout.splitlines()]
    return files, [f for f in files if f.endswith(".sv")]


def main() -> None:
    p = payload()
    if p.get("stop_hook_active") or get_mode() != "on":
        return  # software-only checkout (or mode unset): stay silent
    changed, sv = changed_hw()
    if not changed:
        return  # nothing under hw/ touched this session: no reminder
    out = {}
    if sv:
        sim_t = LAST_SIM.stat().st_mtime if LAST_SIM.exists() else 0
        newest = max((ROOT / f).stat().st_mtime for f in sv if (ROOT / f).exists()) if sv else 0
        if newest > sim_t:
            warn = (f"hw: {len(sv)} changed .sv file(s) ({', '.join(sv[:5])}) have no `make sim` "
                    "run after them this session (hw/.advisor/last_sim.txt is older). Run "
                    "`make sim` in the module dir before finishing.")
            out["systemMessage"] = warn + " | "
    out["systemMessage"] = out.get("systemMessage", "") + "hw reminder: run the hw-advisor skill to mine friction from this session."
    print(json.dumps(out))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
