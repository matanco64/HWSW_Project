#!/usr/bin/env python3
"""VCD -> CSV: one row per value change (sample-and-hold), one column per signal.

Follows the Verkor-paper flow: dump waves, flatten selected signals into a table
that a Python golden model / pandas can diff against.  Uses pyvcd's reader.

    python vcd2csv.py dump.vcd out.csv [--signals top.dut.out_valid top.dut.out_data ...]
"""
import argparse
import csv
import sys

from vcd.reader import TokenKind, tokenize


def vcd_to_rows(path, wanted=None):
    scope = []
    id_to_name = {}
    with open(path, "rb") as f:
        for tok in tokenize(f):
            if tok.kind is TokenKind.SCOPE:
                scope.append(tok.data.ident)
            elif tok.kind is TokenKind.UPSCOPE:
                scope.pop()
            elif tok.kind is TokenKind.VAR:
                name = ".".join(scope + [tok.data.reference])
                if wanted is None or name in wanted:
                    id_to_name.setdefault(tok.data.id_code, name)
            elif tok.kind is TokenKind.ENDDEFINITIONS:
                break
    names = sorted(set(id_to_name.values()))
    cur = {n: "x" for n in names}
    rows = []
    t = 0
    dirty = False
    with open(path, "rb") as f:
        for tok in tokenize(f):
            if tok.kind is TokenKind.CHANGE_TIME:
                if dirty:
                    rows.append([t] + [cur[n] for n in names])
                    dirty = False
                t = tok.data
            elif tok.kind in (TokenKind.CHANGE_SCALAR, TokenKind.CHANGE_VECTOR, TokenKind.CHANGE_REAL):
                n = id_to_name.get(tok.data.id_code)
                if n is not None:
                    v = tok.data.value
                    cur[n] = v if isinstance(v, str) else (hex(v) if isinstance(v, int) else str(v))
                    dirty = True
        if dirty:
            rows.append([t] + [cur[n] for n in names])
    return ["time"] + names, rows


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("vcd")
    p.add_argument("csv")
    p.add_argument("--signals", nargs="*", default=None, help="hierarchical names; default all")
    a = p.parse_args(argv)
    header, rows = vcd_to_rows(a.vcd, set(a.signals) if a.signals else None)
    with open(a.csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"vcd2csv: {len(rows)} rows x {len(header)-1} signals -> {a.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
