#!/usr/bin/env python3
"""Summarise a Verilator coverage.dat: line / toggle / branch percentages.

Each record is  C '<key\x02val\x01key\x02val...>' <count>  where the `page`
key starts with v_line, v_toggle, v_branch or v_user.
"""
import re
import sys
from collections import defaultdict

REC = re.compile(r"^C '(.*)' (\d+)$")


def main(path: str) -> int:
    hit = defaultdict(int)
    tot = defaultdict(int)
    with open(path, encoding="latin-1") as f:
        for line in f:
            m = REC.match(line.rstrip("\n"))
            if not m:
                continue
            fields = m.group(1).split("\x01")
            kv = {}
            for fld in fields:
                if "\x02" in fld:
                    k, v = fld.split("\x02", 1)
                    kv[k] = v
            page = kv.get("page", "v_other")
            kind = page.split("/")[0].removeprefix("v_")
            tot[kind] += 1
            if int(m.group(2)) > 0:
                hit[kind] += 1

    def pct(k):
        return 100.0 * hit[k] / tot[k] if tot[k] else 0.0

    parts = []
    for k in ("line", "toggle", "branch", "user"):
        if tot[k]:
            parts.append(f"{k} {pct(k):.1f}% ({hit[k]}/{tot[k]})")
    if not parts:
        print("cov: no coverage points found in", path)
        return 1
    print("cov: " + "  ".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "coverage.dat"))
