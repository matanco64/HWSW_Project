#!/usr/bin/env python3
"""Check a desktop-agent STATUS block against the deck spec.

Usage: check_status.py presentation/verify/<id>.status [...]

The block format is defined in presentation/prompts/README_AGENT.md. For a slide prompt the
checker compares title_as_typed, body kind, position, tracker stage and notes against deck.md,
and requires result=done, gemini_used=no (or explains it), deviations=none, screenshot=taken.
For setup prompts it checks result, deck_url and that deviations were reported.
Exit 0 only when every file passes. This is the mechanical half of verification; the Drive
text read and the screenshot review remain manual.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deckspec import parse  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PRES = ROOT / "presentation"
FIELDS = ("result", "deck_url", "slide_url", "position", "title_as_typed", "body", "notes_set",
          "tracker", "gemini_used", "deviations", "screenshot")


def read_status(path: Path) -> tuple[str, dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^\s*STATUS\s+(\S+)\s*$", text, re.M)
    if not m:
        raise ValueError("no 'STATUS <id>' header")
    pid = m.group(1)
    fields: dict[str, str] = {}
    key = None
    for line in text[m.end():].splitlines():
        fm = re.match(r"^\s*([a-z_]+):\s*(.*)$", line)
        if fm and fm.group(1) in FIELDS:
            key = fm.group(1)
            fields[key] = fm.group(2).strip()
        elif key == "deviations" and line.strip():
            fields[key] += "\n" + line.strip()
    return pid, fields


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'").replace("‘", "'").strip().strip('"'))


def expected_body(slide) -> str:
    v = slide.fields.get("visual", "")
    if v.startswith("assets/"):
        return f"image {v.split('/', 1)[1]}"
    if v == "title":
        rows = [r for r in slide.table.splitlines()[2:] if r.startswith("|")]
        return f"title-lines {len(rows)}"
    if v == "table":
        rows = [r for r in slide.table.splitlines() if r.startswith("|") and not set(r) <= set("|-: ")]
        return f"table {len(rows)}x{rows[0].count('|') - 1}" if rows else "table"
    return v


def check(path: Path, slides) -> list[str]:
    errs: list[str] = []
    try:
        pid, f = read_status(path)
    except ValueError as e:
        return [str(e)]
    if path.stem != pid:
        errs.append(f"file is {path.stem} but block says {pid}")
    missing = [k for k in FIELDS if k not in f]
    if missing:
        errs.append("missing fields: " + ", ".join(missing))
    if not f.get("result", "").startswith("done"):
        errs.append(f"result is {f.get('result')!r}")
    if f.get("result") == "done-with-deviation" or norm(f.get("deviations", "none")) != "none":
        errs.append("deviations reported: " + f.get("deviations", "").replace("\n", " | "))
    if not f.get("deck_url", "").startswith("https://docs.google.com/presentation/"):
        errs.append("deck_url is not a Google Slides URL")
    if not f.get("screenshot", "").startswith("taken"):
        errs.append("screenshot not taken")
    if not f.get("gemini_used", "no").startswith("no"):
        errs.append("gemini used: " + f["gemini_used"] + " (verify the touched text manually)")
    by_id = {s.id: s for s in slides}
    if pid in by_id:
        s = by_id[pid]
        main = [x for x in slides if not x.is_backup]
        if norm(f.get("title_as_typed", "")) != norm(s.title):
            errs.append(f"title differs:\n      typed: {f.get('title_as_typed')}\n      spec : {s.title}")
        if norm(f.get("body", "")) != norm(expected_body(s)):
            errs.append(f"body is {f.get('body')!r}, spec expects {expected_body(s)!r}")
        pos = f.get("position", "")
        pm = re.match(r"(\d+)\s+of\s+(\d+)", pos)
        if not s.is_backup:
            want = main.index(s) + 1
            if not pm or int(pm.group(1)) != want:
                errs.append(f"position is {pos!r}, spec expects {want}")
        elif pm and int(pm.group(1)) <= len(main):
            errs.append(f"backup slide placed at {pos}, must come after the {len(main)} main slides")
        stage = s.fields.get("stage", "")
        tr = f.get("tracker", "")
        if s.fields.get("visual") == "title":
            if not tr.startswith("none"):
                errs.append("title slide must have no tracker")
        elif not tr.startswith(stage):
            errs.append(f"tracker is {tr!r}, spec expects {stage!r} highlighted")
        if s.notes and not f.get("notes_set", "").startswith("yes"):
            errs.append("notes not set")
        elif s.notes:
            head = re.search(r"\((.*?)\)", f.get("notes_set", ""))
            if head and not norm(s.notes).lower().startswith(norm(head.group(1)).lower()[:20]):
                errs.append(f"notes start {head.group(1)!r} does not match the spec's opening words")
        if not re.search(r"#slide=id\.", f.get("slide_url", "")):
            errs.append("slide_url lacks #slide=id. (select the slide before copying the URL)")
    elif not pid.startswith("00"):
        errs.append(f"unknown slide id {pid}")
    return errs


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    slides = parse(PRES / "deck.md")
    bad = 0
    for arg in argv[1:]:
        p = Path(arg)
        errs = check(p, slides)
        if errs:
            bad += 1
            print(f"FAIL {p.name}")
            for e in errs:
                print(f"     - {e}")
        else:
            print(f"ok   {p.name}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
