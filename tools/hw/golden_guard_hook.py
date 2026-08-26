#!/usr/bin/env python3
"""PreToolUse (Edit|Write|MultiEdit|NotebookEdit) hook: deny edits under hw/*/golden/**.

Contract (code.claude.com/docs/en/hooks, "Exit code 2"): exit 2 blocks the tool call and the
stderr text is the reason shown to Claude.
"""
import re
import sys

from _common import payload, rel, file_path

GOLDEN = re.compile(r"^hw/[^/]+/golden/")


def main() -> None:
    p = payload()
    paths = [file_path(p)]
    for e in (p.get("tool_input") or {}).get("edits") or []:   # MultiEdit
        paths.append(e.get("file_path") or "")
    if any(GOLDEN.match(rel(x)) for x in paths if x):
        print("golden models are frozen references; ask the user to unlock explicitly",
              file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
