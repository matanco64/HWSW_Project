#!/usr/bin/env python3
"""PostToolUse (Edit|Write) hook: verilator --lint-only -Wall on any edited hw/**/*.sv.

Contract (code.claude.com/docs/en/hooks, "Exit code 0" + "PostToolUse decision control"):
plain stdout of a PostToolUse hook is NOT shown to Claude, so findings are returned as
{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": ...}}.
"""
import json
import subprocess
import sys

from _common import ROOT, HW, payload, rel, file_path

VERILATOR = HW / "tools" / "oss-cad-suite" / "bin" / "verilator"


def main() -> None:
    p = payload()
    f = rel(file_path(p))
    if not (f.startswith("hw/") and f.endswith(".sv")) or not VERILATOR.exists():
        return
    cmd = [str(VERILATOR), "--lint-only", "-Wall", "-Ihw/common/rtl", f]
    try:
        r = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=30)
        # verilator prints a "Verilation Report" banner even when clean; keep only findings
        lines = [ln for ln in (r.stdout + r.stderr).splitlines()
                 if not ln.startswith("- V") and not ln.startswith("- Verilator")]
        text = "\n".join(lines).strip()
        findings = any(ln.startswith(("%Warning", "%Error")) for ln in lines)
        verdict = "clean" if r.returncode == 0 and not findings else f"exit {r.returncode}"
    except subprocess.TimeoutExpired:
        text, verdict = "", "timed out after 30 s"
    if verdict == "clean":
        return
    msg = f"verilator --lint-only -Wall {f}: {verdict}\n{text[-6000:]}"
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                             "additionalContext": msg}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
