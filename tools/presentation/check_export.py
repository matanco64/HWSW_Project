#!/usr/bin/env python3
"""Diff a Google Slides plain-text export against the deck spec.

Usage: check_export.py presentation/verify/deck_export.txt [--through S12]

Google Slides → File → Download → Plain text (.txt) writes every slide's text in order, with
speaker notes when present. This checker confirms, for every main-flow slide up to --through
(default: all slides that should exist so far, i.e. every slide whose title is found), that:
  * the claim title appears verbatim, and the titles appear in storyboard order;
  * the speaker notes' opening words follow the title before the next title;
  * for table slides, every cell text of the spec table appears between this title and the next.
It reports slides whose title is missing (not built yet, or mistyped) and any order violation.
This is the Drive-free readback; it complements check_status.py (agent's self-report) and the
screenshot review (layout).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deckspec import parse  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PRES = ROOT / "presentation"


def norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace(" ", " ").replace("×", "x").replace("−", "-").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def cells(table: str, values_only: bool = False) -> list[str]:
    out = []
    rows = [r for r in table.splitlines() if r.startswith("|") and not set(r) <= set("|-: ")]
    for row in rows[1:] if values_only else rows:
        cs = [c.strip() for c in row.strip("|").split("|")]
        if values_only:
            cs = cs[1:2]
        out += [c for c in cs if c and c != "—"]
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    export = norm(Path(argv[1]).read_text(encoding="utf-8", errors="replace"))
    through = argv[argv.index("--through") + 1] if "--through" in argv else None
    slides = parse(PRES / "deck.md")
    if through:
        ids = [s.id for s in slides]
        slides = slides[: ids.index(through) + 1]
    found: list[tuple[str, int]] = []
    missing: list[str] = []
    for s in slides:
        i = export.find(norm(s.title))
        (found if i >= 0 else missing).append((s.id, i) if i >= 0 else s.id)
    errs: list[str] = []
    order = [i for _, i in found]
    if order != sorted(order):
        bad = [sid for (sid, i), j in zip(found, sorted(order)) if i != j]
        errs.append("titles out of storyboard order around: " + ", ".join(bad))
    by_id = {s.id: s for s in slides}
    for k, (sid, i) in enumerate(found):
        s = by_id[sid]
        later = [j for _, j in found if j > i]
        end = min(later) if later else len(export)
        seg = export[i:end]
        if s.notes:
            head = norm(s.notes)[:40]
            if head not in seg:
                errs.append(f"{sid}: notes opening not found after the title ({head[:30]!r}...)")
        if s.fields.get("visual") in ("table", "title") and s.table:
            lost = [c for c in cells(s.table, values_only=(s.fields.get("visual") == "title")) if norm(c) not in seg]
            if lost:
                errs.append(f"{sid}: table cells missing: " + "; ".join(lost[:6]) + (" ..." if len(lost) > 6 else ""))
    print(f"{len(found)} of {len(slides)} slide titles found in the export")
    if missing:
        print("not found (not built yet, or title mistyped): " + ", ".join(missing))
    for e in errs:
        print("FAIL " + e)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
