"""Consistency check: driver register constants == MAS §4 register map.

Parses the register table in `docs/mas.md`, extracts (offset, name) rows, and
verifies every named register maps to the same byte offset as the matching
constant in `grape_pipeline_driver.py`. Exit 0 and "0 differences" on success.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MAS = os.path.join(HERE, "..", "docs", "mas.md")

sys.path.insert(0, HERE)
import grape_pipeline_driver as drv  # noqa: E402

# MAS name -> driver constant name (for names that differ or are windows)
NAME_MAP = {
    "ID": "ID", "VERSION": "VERSION", "CTRL": "CTRL", "STATUS": "STATUS",
    "IRQ_EN": "IRQ_EN", "IRQ_STATUS": "IRQ_STATUS",
    "CYCLES_LO": "CYCLES_LO", "CYCLES_HI": "CYCLES_HI", "STEPS_DONE": "STEPS_DONE",
    "DT_LO": "DT_LO", "DT_HI": "DT_HI", "NSTEPS": "NSTEPS", "NPAIRS": "NPAIRS",
}
WINDOWS = {  # base-address rows written with an offset expression
    "BODY": ("BODY_BASE", 0x200),
    "PAIR": ("PAIR_BASE", 0x400),
}

ROW = re.compile(r"^\|\s*(0x[0-9A-Fa-f]{3})[^\|]*\|\s*([A-Za-z0-9_\[\]]+)")


def parse_mas():
    rows = []
    for line in open(MAS, encoding="utf-8"):
        m = ROW.match(line.strip())
        if not m:
            continue
        off = int(m.group(1), 16)
        name = m.group(2)
        if name in ("—", "-"):
            continue
        rows.append((off, name))
    return rows


def main():
    rows = parse_mas()
    diffs = []
    checked = 0
    for off, name in rows:
        if name.startswith("BODY"):
            const, base = WINDOWS["BODY"]
            if off != base or getattr(drv, const) != base:
                diffs.append(f"{name}: MAS 0x{off:03x} vs driver {const}=0x{getattr(drv, const):03x}")
            checked += 1
            continue
        if name.startswith("PAIR"):
            const, base = WINDOWS["PAIR"]
            if off != base or getattr(drv, const) != base:
                diffs.append(f"{name}: MAS 0x{off:03x} vs driver {const}=0x{getattr(drv, const):03x}")
            checked += 1
            continue
        if name not in NAME_MAP:
            continue
        const = NAME_MAP[name]
        dv = getattr(drv, const, None)
        if dv is None:
            diffs.append(f"{name}: missing driver constant {const}")
        elif dv != off:
            diffs.append(f"{name}: MAS 0x{off:03x} vs driver {const}=0x{dv:03x}")
        checked += 1

    # sanity: every mapped driver constant appeared in the MAS table
    mas_names = {n for _, n in rows}
    for mas_name in NAME_MAP:
        if mas_name not in mas_names:
            diffs.append(f"driver constant {mas_name} not found in MAS table")

    print(f"check_regmap: {checked} register rows checked against docs/mas.md §4")
    print(f"ID_VALUE = 0x{drv.ID_VALUE:08x} (MAS reset 0x47525031)")
    if diffs:
        print(f"{len(diffs)} differences:")
        for d in diffs:
            print("  -", d)
        return 1
    print("0 differences")
    return 0


if __name__ == "__main__":
    sys.exit(main())
