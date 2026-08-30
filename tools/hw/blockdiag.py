#!/usr/bin/env python3
"""Block diagram from one JSON spec -> Mermaid (.mmd) + SVG (.svg), no external renderer.

Spec: {"title": str, "columns": [{"name": str, "blocks": [{"id": str, "label": str, "sub": str?}]}],
       "edges": [{"from": id, "to": id, "label": str?}]}
Columns are laid out left to right, blocks top to bottom inside a column; edges are drawn as
orthogonal-ish straight lines with the label at the midpoint. Deterministic, dependency-free.

    python3 tools/hw/blockdiag.py hw/<module>/docs/block_diagram.json
writes block_diagram.mmd and block_diagram.svg next to the spec.
"""
import json
import pathlib
import sys
from xml.sax.saxutils import escape

BW, BH, GX, GY, PAD, HDR = 190, 64, 70, 26, 24, 34


def mermaid(spec):
    out = ["flowchart LR"]
    for ci, col in enumerate(spec["columns"]):
        out.append(f"    subgraph C{ci}[\"{col['name']}\"]")
        out.append("        direction TB")
        for b in col["blocks"]:
            lab = b["label"] + (f"<br/><i>{b['sub']}</i>" if b.get("sub") else "")
            out.append(f"        {b['id']}[\"{lab}\"]")
        out.append("    end")
    for e in spec["edges"]:
        lab = f"|{e['label']}|" if e.get("label") else ""
        out.append(f"    {e['from']} -->{lab} {e['to']}")
    return "\n".join(out) + "\n"


def svg(spec):
    pos = {}
    cols = spec["columns"]
    height = HDR + max(len(c["blocks"]) for c in cols) * (BH + GY) + 2 * PAD
    width = PAD + len(cols) * (BW + GX) - GX + PAD
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}" font-family="Helvetica, Arial, sans-serif" font-size="12">',
             '<defs><marker id="arr" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">'
             '<path d="M0,0 L8,4 L0,8 z" fill="#333"/></marker></defs>',
             f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
             f'<text x="{PAD}" y="{PAD - 4}" font-size="15" font-weight="bold">{escape(spec["title"])}</text>']
    for ci, col in enumerate(cols):
        x = PAD + ci * (BW + GX)
        ch = len(col["blocks"]) * (BH + GY) + HDR
        parts.append(f'<rect x="{x - 8}" y="{PAD}" width="{BW + 16}" height="{ch}" rx="8" '
                     f'fill="#f4f6fa" stroke="#9aa5b5" stroke-dasharray="4 3"/>')
        parts.append(f'<text x="{x}" y="{PAD + 20}" font-weight="bold" fill="#3b4a5e">{escape(col["name"])}</text>')
        for bi, b in enumerate(col["blocks"]):
            y = PAD + HDR + bi * (BH + GY)
            pos[b["id"]] = (x, y)
            parts.append(f'<rect x="{x}" y="{y}" width="{BW}" height="{BH}" rx="6" fill="#ffffff" stroke="#333" stroke-width="1.2"/>')
            parts.append(f'<text x="{x + BW / 2}" y="{y + (26 if b.get("sub") else 37)}" text-anchor="middle" font-weight="bold">{escape(b["label"])}</text>')
            if b.get("sub"):
                parts.append(f'<text x="{x + BW / 2}" y="{y + 46}" text-anchor="middle" fill="#555" font-size="11">{escape(b["sub"])}</text>')
    for e in spec["edges"]:
        (x1, y1), (x2, y2) = pos[e["from"]], pos[e["to"]]
        if x2 > x1:            # left -> right
            sx, sy, tx, ty = x1 + BW, y1 + BH / 2, x2, y2 + BH / 2
        elif x2 < x1:          # right -> left (return path), drawn below
            sx, sy, tx, ty = x1, y1 + BH / 2 + 12, x2 + BW, y2 + BH / 2 + 12
        else:                  # same column, top -> bottom
            sx, sy, tx, ty = x1 + BW / 2, y1 + BH, x2 + BW / 2, y2
        parts.append(f'<line x1="{sx}" y1="{sy}" x2="{tx}" y2="{ty}" stroke="#333" stroke-width="1.2" marker-end="url(#arr)"/>')
        if e.get("label"):
            mx, my = (sx + tx) / 2, (sy + ty) / 2 - 5
            parts.append(f'<text x="{mx}" y="{my}" text-anchor="middle" font-size="11" fill="#1f4e79">'
                         f'<tspan style="paint-order:stroke" stroke="#fff" stroke-width="4">{escape(e["label"])}</tspan>'
                         f'{escape(e["label"])}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main():
    spec_path = pathlib.Path(sys.argv[1])
    spec = json.loads(spec_path.read_text())
    base = spec_path.with_suffix("")
    base.with_suffix(".mmd").write_text(mermaid(spec))
    base.with_suffix(".svg").write_text(svg(spec))
    print(f"wrote {base.with_suffix('.mmd')} and {base.with_suffix('.svg')}")


if __name__ == "__main__":
    main()
