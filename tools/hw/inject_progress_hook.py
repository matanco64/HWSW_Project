#!/usr/bin/env python3
"""SessionStart hook, gated by the HW-flow mode (tools/hw/mode.py):

  unset -> inject a short instruction to ask the user (AskUserQuestion) whether this checkout is
           used for hardware-flow work, and record the answer with tools/hw/mode.py. Asked once.
  off   -> silent (software-only teammate: no hardware context in their sessions).
  on    -> inject hw/PROGRESS.md as additionalContext.

Contract: {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ...}}.
"""
import json
import sys

from _common import HW, payload
from mode import get as get_mode

PROGRESS = HW / "PROGRESS.md"

ASK = (
    "HW-flow mode is not set for this checkout. Before doing anything else in this session, use the "
    "AskUserQuestion tool with header \"HW flow\" and the question \"Is this checkout used for the "
    "hardware-accelerator flow (hooks + hw-* skills), or software-only work?\", options: "
    "\"HW flow\" (enables hw/PROGRESS.md injection, stale-sim reminders and /hw-flow) and "
    "\"Software only\" (keeps every hardware hook silent; can be changed later with /hw-mode on). "
    "Then run `python3 tools/hw/mode.py on` or `python3 tools/hw/mode.py off` accordingly and "
    "continue with the user's request."
)


def emit(text: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                             "additionalContext": text[:9500]}}))


def main() -> None:
    payload()
    mode = get_mode()
    if mode == "unset":
        emit(ASK)
    elif mode == "on" and PROGRESS.exists():
        emit("Hardware flow (mode on; `/hw-mode off` to silence): contract in hw/FLOW.md; current "
             "state below (hw/PROGRESS.md, generated from hw/STATUS.json via tools/hw/status.py).\n\n"
             + PROGRESS.read_text(encoding="utf-8"))
    # mode off: silent


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
