#!/usr/bin/env python3
"""SessionStart hook: inject hw/PROGRESS.md as additionalContext
(contract: {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ...}})."""
import json
import sys

from _common import HW, payload

PROGRESS = HW / "PROGRESS.md"


def main() -> None:
    payload()
    if not PROGRESS.exists():
        return
    text = ("Hardware flow: contract in hw/FLOW.md; current state below (hw/PROGRESS.md, "
            "generated from hw/STATUS.json via tools/hw/status.py).\n\n"
            + PROGRESS.read_text(encoding="utf-8"))
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                             "additionalContext": text[:9500]}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
