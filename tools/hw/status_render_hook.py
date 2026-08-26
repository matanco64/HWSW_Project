#!/usr/bin/env python3
"""PostToolUse (Edit|Write) hook: when hw/STATUS.json changes, regenerate hw/PROGRESS.md
and mirror to GitHub Issues (gh_sync.py is a no-op without gh auth)."""
import subprocess
import sys

from _common import ROOT, payload, rel, file_path

TOOLS = ROOT / "tools" / "hw"


def main() -> None:
    if rel(file_path(payload())) != "hw/STATUS.json":
        return
    subprocess.run([sys.executable, str(TOOLS / "render_progress.py")], check=False, timeout=30)
    subprocess.run([sys.executable, str(TOOLS / "gh_sync.py")], check=False, timeout=120)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
