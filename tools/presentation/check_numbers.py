#!/usr/bin/env python3
"""Every number on a slide must be quoted from a shipped file at a cited line.

Usage: check_numbers.py [presentation/deck.md]

Two checks per slide:
1. Each ``sources`` line ``- <quote> → <path>:<lo>[-<hi>]`` must have its quote present
   (whitespace-collapsed) in lines lo..hi of the file. As a fallback the quote passes if
   every numeric token in it appears in that line range.
2. Every *significant* number in the title, table and notes must appear as a numeric token
   in one of the slide's source quotes. Significant = has a decimal point, or is >= 100, or
   is followed by a unit. Small bare integers are exempt; ``- exempt: 4, 10`` exempts more.

Also refuses known-stale figures in report/defense_guide.md (kept in STALE below).
Exit status 0 only when every slide passes.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deckspec import Slide, parse  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
UNITS = r"(?:x|×|%|ms|s|MHz|mm²|mm\^2|mW|cycles?|bytes?|samples?|cells?|steps?|pairs?|entries|bodies|Mcycles)"
NUM = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(?:\s?(" + UNITS + r"))?(?![\w])")
STALE = {
    "report/defense_guide.md": ["37.6 MHz", "4.24 ms", "13.7 mW", "about 2x at any clock"],
}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("−", "-").replace("–", "-")).strip()


def numeric_tokens(s: str) -> set[str]:
    return {(m.group(1) + (m.group(2) or "")).replace(",", "") for m in NUM.finditer(s)}


def significant_numbers(text: str, exempt: set[str]) -> set[str]:
    out = set()
    for m in NUM.finditer(text):
        whole, frac, unit = m.group(1), m.group(2), m.group(3)
        value = (whole + (frac or "")).replace(",", "")
        if value in exempt:
            continue
        if frac or unit or float(value) >= 100:
            out.add(value)
    return out


def check_slide(s: Slide, cache: dict) -> list[str]:
    errs: list[str] = []
    for n, line in s.bad_sources:
        errs.append(f"line {n}: unparsable sources line: {line!r}")
    quoted: set[str] = set()
    for src in s.sources:
        p = ROOT / src.path
        if p not in cache:
            # split on "\n" only: the .txt reports contain form feeds, which splitlines() would
            # also split on, making checker line numbers drift from editor line numbers.
            cache[p] = p.read_text(encoding="utf-8", errors="replace").split("\n") if p.exists() else None
        lines = cache[p]
        if lines is None:
            errs.append(f"{src.path}: file not found")
            continue
        if src.hi > len(lines):
            errs.append(f"{src.path}:{src.lo}-{src.hi}: beyond end of file ({len(lines)} lines)")
            continue
        span = norm(" ".join(lines[src.lo - 1 : src.hi]))
        q = norm(src.quote)
        toks = numeric_tokens(src.quote)
        if q not in span and not (toks and toks <= numeric_tokens(span)):
            errs.append(f"quote {src.quote!r} not at {src.path}:{src.lo}-{src.hi}")
        quoted |= toks
    exempt = {x.strip() for x in s.fields.get("exempt", "").split(",") if x.strip()}
    text = " ".join([s.title, s.table, s.notes])
    missing = sorted(significant_numbers(text, exempt) - quoted, key=lambda v: float(v))
    if missing:
        errs.append("unsourced numbers: " + ", ".join(missing))
    for key in ("owner", "status", "seconds", "visual"):
        if key not in s.fields and not (s.is_backup and key == "seconds"):
            errs.append(f"missing field: {key}")
    if s.fields.get("owner") == "M" and s.fields.get("status") not in ("DRAFT", "CONFIRMED"):
        errs.append("SW slide must be DRAFT or CONFIRMED")
    return errs


def check_stale() -> list[str]:
    errs = []
    for rel, needles in STALE.items():
        p = ROOT / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for needle in needles:
            if needle in text:
                errs.append(f"{rel}: stale figure still present: {needle!r}")
    return errs


def main(argv: list[str]) -> int:
    deck = Path(argv[1]) if len(argv) > 1 else ROOT / "presentation" / "deck.md"
    if not deck.exists():
        print(f"{deck}: not found")
        return 1
    slides = parse(deck)
    if not slides:
        print(f"{deck}: no slides parsed")
        return 1
    cache: dict = {}
    failed = 0
    for s in slides:
        errs = check_slide(s, cache)
        if errs:
            failed += 1
            print(f"FAIL {s.id} (line {s.line}): {s.title}")
            for e in errs:
                print(f"     - {e}")
    stale = check_stale()
    for e in stale:
        print(f"FAIL {e}")
    total = len(slides)
    print(f"{total - failed}/{total} slides pass; {len(stale)} stale-figure hits")
    return 1 if failed or stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
