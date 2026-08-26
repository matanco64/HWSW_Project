#!/usr/bin/env python3
"""HW-flow mode switch: the explicit, per-machine signal that this checkout is used for hardware
work. Stored in hw/.advisor/mode (gitignored) as "on" or "off". Unset = never asked.

  python3 tools/hw/mode.py            -> prints on|off|unset
  python3 tools/hw/mode.py on|off     -> sets it
  python3 tools/hw/mode.py clear      -> forgets it (the next session asks again)

Consumers: inject_progress_hook.py, stop_hook.py (silent unless "on"), the hw-flow skill.
"""
import sys

from _common import HW

MODE_FILE = HW / ".advisor" / "mode"


def get() -> str:
    try:
        v = MODE_FILE.read_text(encoding="utf-8").strip().lower()
        return v if v in ("on", "off") else "unset"
    except OSError:
        return "unset"


def set_mode(value: str) -> None:
    MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
    MODE_FILE.write_text(value + "\n", encoding="utf-8")


def main() -> None:
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else None
    if arg is None:
        print(get())
    elif arg in ("on", "off"):
        set_mode(arg)
        print(f"hw mode: {arg}")
    elif arg == "clear":
        MODE_FILE.unlink(missing_ok=True)
        print("hw mode: unset")
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
