#!/usr/bin/env python3
"""Print the one-line area summary from synth/area.txt (Yosys stat -liberty)."""
import re
import sys


def main(path: str) -> int:
    txt = open(path).read()
    # Yosys >= 0.4x prints "<n> [<area>] cells"; older prints "Number of cells: <n>".
    cells = re.findall(r"^\s*(\d+)\s+(?:[\d.E+-]+\s+)?cells\s*$", txt, re.M) or re.findall(r"Number of cells:\s+(\d+)", txt)
    area = re.findall(r"Chip area for (?:top )?module.*?:\s+([\d.]+)", txt)
    if not cells:
        print("area: no stat output in", path)
        return 1
    # Last block is the liberty-mapped one (script order: generic stat first, then liberty).
    print(f"area: {cells[-1]} sky130_fd_sc_hd cells, {area[-1] if area else '?'} um^2 -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "synth/area.txt"))
