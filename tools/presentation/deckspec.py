"""Parser for presentation/deck.md (format documented in presentation/STRATEGY.md).

A slide starts with a level-2 heading ``## <ID> · <claim title>``. It is followed by
``- key: value`` lines, then optional ``table:`` / ``notes:`` / ``sources:`` blocks, in
that order. A block runs until the next block keyword or the next heading.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

HEADING = re.compile(r"^## (?P<id>[SB]\d{2}) · (?P<title>.+?)\s*$")
FIELD = re.compile(r"^- (?P<key>[a-z]+): ?(?P<value>.*?)\s*(\(.*\))?\s*$")
BLOCKS = ("table", "notes", "sources")
SOURCE = re.compile(r"^- (?P<quote>.+?) → (?P<path>[^:\s]+):(?P<lo>\d+)(?:-(?P<hi>\d+))?\s*$")


@dataclass
class Source:
    quote: str
    path: str
    lo: int
    hi: int


@dataclass
class Slide:
    id: str
    title: str
    fields: dict = field(default_factory=dict)
    table: str = ""
    notes: str = ""
    sources: list = field(default_factory=list)
    bad_sources: list = field(default_factory=list)
    line: int = 0

    @property
    def is_backup(self) -> bool:
        return self.id.startswith("B")


def parse(path: Path) -> list[Slide]:
    slides: list[Slide] = []
    cur: Slide | None = None
    block: str | None = None
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.rstrip()
        m = HEADING.match(line)
        if m:
            cur = Slide(id=m["id"], title=m["title"], line=n)
            slides.append(cur)
            block = None
            continue
        if cur is None:
            continue
        if line.rstrip(":") in BLOCKS and line.endswith(":"):
            block = line[:-1]
            continue
        if block is None:
            fm = FIELD.match(line)
            if fm:
                cur.fields[fm["key"]] = fm["value"].strip()
            continue
        if block == "table":
            if line.strip():
                cur.table += line + "\n"
        elif block == "notes":
            cur.notes += line + "\n"
        elif block == "sources":
            if not line.strip():
                continue
            sm = SOURCE.match(line)
            if sm:
                lo = int(sm["lo"])
                hi = int(sm["hi"] or lo)
                cur.sources.append(Source(sm["quote"].strip(), sm["path"], lo, hi))
            else:
                cur.bad_sources.append((n, line))
    for s in slides:
        s.notes = s.notes.strip()
        s.table = s.table.strip()
    return slides
