#!/usr/bin/env python3
"""Verify a .pptx export of the Google Slides deck against the deck spec. Stdlib only.

Usage: check_pptx.py presentation/verify/deck_export.pptx [--through S12] [--dump]

Google Slides → File → Download → Microsoft PowerPoint (.pptx). The file is a zip of XML; this
reads it directly (no python-pptx needed) and checks, slide by slide in deck order:
  * the title text equals the spec's claim title (whitespace/quote-normalised);
  * a spec table's cells all appear in a table shape on the slide; an image slide has a picture;
  * speaker notes start with the spec's opening words;
  * the footer tracker text is present on content slides and absent on the title slide;
  * fonts: every text run that names a font names Roboto (theme fonts are reported, not failed).
Slides in the export beyond --through (or beyond the spec) are listed as extra. --dump prints
what was found per slide instead of checking.
"""
from __future__ import annotations

import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deckspec import parse  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PRES = ROOT / "presentation"
NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}
TRACKER = ["Analyze", "Profile", "Optimize", "Accelerate", "Trade-offs"]


def norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace(" ", " ").replace("×", "x").replace("−", "-").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def text_of(el) -> str:
    """Concatenate a:t runs, paragraphs separated by newlines."""
    paras = []
    for p in el.iter(f"{{{NS['a']}}}p"):
        paras.append("".join(t.text or "" for t in p.iter(f"{{{NS['a']}}}t")))
    return "\n".join(x for x in paras if x.strip())


class Slide:
    def __init__(self):
        self.title = ""
        self.texts: list[str] = []
        self.tables: list[list[str]] = []
        self.pictures = 0
        self.notes = ""
        self.fonts: set[str] = set()
        self.layout = ""


def load(path: Path) -> list[Slide]:
    z = zipfile.ZipFile(path)
    pres = ET.fromstring(z.read("ppt/presentation.xml"))
    rels = ET.fromstring(z.read("ppt/_rels/presentation.xml.rels"))
    rid2target = {r.get("Id"): r.get("Target") for r in rels}
    order = [rid2target[s.get(f"{{{NS['r']}}}id")] for s in pres.iter(f"{{{NS['p']}}}sldId")]
    out = []
    for target in order:
        name = "ppt/" + target.lstrip("/").removeprefix("ppt/")
        root = ET.fromstring(z.read(name))
        s = Slide()
        relname = name.replace("slides/", "slides/_rels/") + ".rels"
        srels = {r.get("Id"): (r.get("Type", "").rsplit("/", 1)[-1], r.get("Target")) for r in ET.fromstring(z.read(relname))} if relname in z.namelist() else {}
        for typ, tgt in srels.values():
            if typ == "slideLayout":
                lay = ET.fromstring(z.read("ppt/" + tgt.lstrip("/").removeprefix("ppt/").replace("../", "")))
                cs = lay.find(f"{{{NS['p']}}}cSld")
                s.layout = cs.get("name", "") if cs is not None else ""
            if typ == "notesSlide":
                notes = ET.fromstring(z.read("ppt/" + tgt.replace("../", "")))
                bodies = []
                for sp in notes.iter(f"{{{NS['p']}}}sp"):
                    ph = sp.find(f".//{{{NS['p']}}}ph")
                    if ph is not None and ph.get("type") == "body":
                        bodies.append(text_of(sp))
                s.notes = "\n".join(bodies)
        for sp in root.iter(f"{{{NS['p']}}}sp"):
            ph = sp.find(f".//{{{NS['p']}}}ph")
            txt = text_of(sp)
            if ph is not None and ph.get("type") in ("title", "ctrTitle") and txt:
                s.title = txt
            elif txt:
                s.texts.append(txt)
        for latin in root.iter(f"{{{NS['a']}}}latin"):
            if latin.get("typeface"):
                s.fonts.add(latin.get("typeface"))
        for tbl in root.iter(f"{{{NS['a']}}}tbl"):
            s.tables.append([text_of(tc) for tc in tbl.iter(f"{{{NS['a']}}}tc")])
        s.pictures = sum(1 for _ in root.iter(f"{{{NS['p']}}}pic"))
        out.append(s)
    return out


def spec_cells(table: str, values_only: bool = False) -> list[str]:
    """Cell texts of a spec table; for the title slide only the value column is on the slide."""
    out = []
    rows = [r for r in table.splitlines() if r.startswith("|") and not set(r) <= set("|-: ")]
    for row in rows[1:] if values_only else rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        if values_only:
            cells = cells[1:2]
        out += [c for c in cells if c and c != "—"]
    return out


def check(found: Slide, spec) -> list[str]:
    errs = []
    if norm(found.title) != norm(spec.title):
        errs.append(f"title differs:\n      deck: {found.title!r}\n      spec: {spec.title!r}")
    visual = spec.fields.get("visual", "")
    if visual.startswith("assets/") and found.pictures == 0:
        errs.append(f"no picture on the slide; spec expects {visual}")
    if visual in ("table", "title") and spec.table:
        hay = norm(" ".join(c for t in found.tables for c in t) + " " + " ".join(found.texts))
        lost = [c for c in spec_cells(spec.table, values_only=(visual == "title")) if norm(c) not in hay]
        if lost:
            errs.append("table cells missing: " + "; ".join(lost[:6]) + (" ..." if len(lost) > 6 else ""))
        if visual == "table" and not found.tables:
            errs.append("no table shape on the slide")
    if spec.notes:
        if not found.notes.strip():
            errs.append("speaker notes empty")
        elif not norm(found.notes).startswith(norm(spec.notes)[:40]):
            errs.append(f"notes do not start with the spec's words: {found.notes[:50]!r}")
    body = " ".join(found.texts)
    has_tracker = all(w.lower() in body.lower() for w in TRACKER)
    if visual == "title" and has_tracker:
        errs.append("tracker present on the title slide")
    if visual != "title" and not has_tracker:
        errs.append("footer tracker text missing")
    odd = {f for f in found.fonts if not f.startswith("+") and "roboto" not in f.lower()}
    if odd:
        errs.append("non-Roboto fonts on slide: " + ", ".join(sorted(odd)))
    return errs


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    deck = load(Path(argv[1]))
    spec = parse(PRES / "deck.md")
    if "--through" in argv:
        ids = [s.id for s in spec]
        spec = spec[: ids.index(argv[argv.index("--through") + 1]) + 1]
    if "--dump" in argv:
        for n, s in enumerate(deck, 1):
            print(f"[{n}] layout={s.layout!r} title={s.title!r} pics={s.pictures} tables={len(s.tables)} fonts={sorted(s.fonts)}")
            print(f"     texts={[t[:40] for t in s.texts]}\n     notes={s.notes[:80]!r}")
        return 0
    bad = 0
    for n, sp in enumerate(spec):
        if n >= len(deck):
            print(f"MISSING {sp.id}: not in the export (deck has {len(deck)} slides)")
            bad += 1
            continue
        errs = check(deck[n], sp)
        if errs:
            bad += 1
            print(f"FAIL {sp.id} (export slide {n + 1})")
            for e in errs:
                print(f"     - {e}")
        else:
            print(f"ok   {sp.id} (export slide {n + 1})")
    if len(deck) > len(spec):
        print(f"extra: export has {len(deck) - len(spec)} slide(s) beyond {spec[-1].id}")
    print(f"{len(spec) - bad}/{len(spec)} slides pass")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
