"""Consistency check: driver constants == MAS §4 register map == rtl/mtf_regs.sv decode.

Three sources must agree on every named register's byte offset:
  1. `mtf_cam_driver.py`   — the Python constants this driver uses.
  2. `docs/mas.md` §4      — the architecture-spec register table (parsed).
  3. `rtl/mtf_regs.sv`     — the actual AXI-Lite word decode (parsed; the RTL
                             uses 10-bit WORD addresses, so byte = word << 2).
Exit 0 and print "0 differences" on success (mirrors grape/huffman).
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MAS = os.path.join(HERE, "..", "docs", "mas.md")
RTL = os.path.join(HERE, "..", "rtl", "mtf_regs.sv")

sys.path.insert(0, HERE)
import mtf_cam_driver as drv  # noqa: E402

# MAS register name -> driver constant name (scalar rows).
NAME_MAP = {
    "ID": "ID", "VERSION": "VERSION", "CTRL": "CTRL", "STATUS": "STATUS",
    "IRQ_EN": "IRQ_EN", "IRQ_STATUS": "IRQ_STATUS",
    "CYCLES_LO": "CYCLES_LO", "CYCLES_HI": "CYCLES_HI",
    "SYMBOLS_IN": "SYMBOLS_IN", "BYTES_OUT": "BYTES_OUT",
    "INIT_CYCLES": "INIT_CYCLES", "MAX_RUN": "MAX_RUN",
    "SYMBOL_LIMIT": "SYMBOL_LIMIT", "BYTES_LIMIT": "BYTES_LIMIT",
    "CAPS": "CAPS", "DBG_SEL": "DBG_SEL", "DBG_DATA": "DBG_DATA",
}
# Windowed row: USED[w] at 0x200 + 4*w.
USED_WINDOW = ("USED", "USED_BASE", 0x200)

# rtl/mtf_regs.sv read-decode: register name -> the RTL right-hand signal (documentation only;
# the check is purely on the decoded WORD address). Maps the MAS name to the RTL case word addr.
RTL_EXPECT = {
    "ID": 0x000, "VERSION": 0x001, "CTRL": 0x002, "STATUS": 0x003,
    "IRQ_EN": 0x004, "IRQ_STATUS": 0x005,
    "CYCLES_LO": 0x010, "CYCLES_HI": 0x011, "SYMBOLS_IN": 0x012,
    "BYTES_OUT": 0x013, "INIT_CYCLES": 0x014, "MAX_RUN": 0x015,
    "SYMBOL_LIMIT": 0x040, "BYTES_LIMIT": 0x041, "CAPS": 0x042,
    "DBG_SEL": 0x043, "DBG_DATA": 0x044,
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


def parse_rtl_words():
    """Collect the word addresses the RTL read-decode maps, and the USED range."""
    text = open(RTL, encoding="utf-8").read()
    words = set(int(h, 16) for h in re.findall(r"10'h([0-9A-Fa-f]{3})\s*:\s*rd_data_n", text))
    # USED[w] lives in the default case, range-checked 0x080..0x087:
    used_lo = re.search(r"rd_addr_i\s*>=\s*10'h([0-9A-Fa-f]{3})\s*&&\s*rd_addr_i\s*<=\s*10'h([0-9A-Fa-f]{3})", text)
    used_range = (int(used_lo.group(1), 16), int(used_lo.group(2), 16)) if used_lo else None
    return words, used_range


def main():
    rows = parse_mas()
    rtl_words, rtl_used = parse_rtl_words()
    diffs = []
    checked = 0
    seen = set()

    for off, name in rows:
        if name.startswith("USED"):
            _, const, base = USED_WINDOW
            dv = getattr(drv, const, None)
            if off != base:
                diffs.append(f"USED: MAS 0x{off:03x} != 0x{base:03x}")
            elif dv != base:
                diffs.append(f"USED: driver {const}=0x{(dv or 0):03x} != MAS 0x{off:03x}")
            elif rtl_used is None or (off >> 2) < rtl_used[0] or (off >> 2) > rtl_used[1]:
                diffs.append(f"USED: RTL decode does not cover word 0x{off >> 2:03x}")
            checked += 1
            seen.add("USED")
            continue
        if name not in NAME_MAP:
            continue
        seen.add(name)
        const = NAME_MAP[name]
        dv = getattr(drv, const, None)
        if dv is None:
            diffs.append(f"{name}: missing driver constant {const}")
        elif dv != off:
            diffs.append(f"{name}: driver {const}=0x{dv:03x} != MAS 0x{off:03x}")
        # driver/MAS vs RTL word decode
        want_word = RTL_EXPECT.get(name)
        if want_word is None:
            diffs.append(f"{name}: no RTL expectation registered")
        elif want_word != (off >> 2):
            diffs.append(f"{name}: RTL word 0x{want_word:03x} != MAS byte 0x{off:03x} (word 0x{off >> 2:03x})")
        elif want_word not in rtl_words:
            diffs.append(f"{name}: rtl/mtf_regs.sv does not decode word 0x{want_word:03x}")
        checked += 1

    # every mapped driver constant / RTL expectation must have appeared in the MAS table
    for mas_name in list(NAME_MAP) + ["USED"]:
        if mas_name not in seen:
            diffs.append(f"MAS table is missing register {mas_name}")

    print(f"check_regmap: {checked} register rows checked (driver == docs/mas.md §4 == rtl/mtf_regs.sv)")
    print(f"ID_VALUE = 0x{drv.ID_VALUE:08x} (MAS/RTL reset 0x4d544631 'MTF1')")
    if diffs:
        print(f"{len(diffs)} differences:")
        for d in diffs:
            print("  -", d)
        return 1
    print("0 differences")
    return 0


if __name__ == "__main__":
    sys.exit(main())
