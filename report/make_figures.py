"""Generate report-only SVGs from recorded profiles and current architecture.

No sampling or result files are changed. Python standard library only.
Flame graphs retain all original frames and widths. Numbered outlines link the
full view to magnified crops; crop percentages refer to the original whole graph.
"""
from pathlib import Path
import html
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'report' / 'fig'
NS = '{http://www.w3.org/2000/svg}'


def flame(source, target, root_name, highlights):
    """Full original geometry at left; highlighted context crops at right."""
    tree = ET.parse(ROOT / 'results' / source)
    source_root = tree.getroot()
    _, _, sw, sh = map(float, source_root.get('viewBox').split())
    frames = []
    for group in tree.iter(NS + 'g'):
        title, rect = group.find(NS + 'title'), group.find(NS + 'rect')
        if title is None or rect is None:
            continue
        match = re.search(r'^(.*?) \(([\d,]+) samples?, ([\d.]+)%\)', title.text or '')
        if not match:
            continue
        frames.append(dict(name=match[1].split(' (')[0], title=title.text,
                           x=float(rect.get('x')), y=float(rect.get('y')),
                           w=float(rect.get('width')), h=float(rect.get('height')),
                           weight=int(match[2].replace(',', '')), share=float(match[3]),
                           element=ET.tostring(group, encoding='unicode')))
    selected = []
    for name, label in highlights:
        candidates = [f for f in frames if f['name'] == name]
        if not candidates:
            raise ValueError(f'Missing {name} in {source}')
        selected.append((max(candidates, key=lambda f: f['w']), label))
    colors = ['#00779d', '#7c4285', '#bd512e']
    height = 580 if sh > 2000 else 480
    overview_w = 205
    overview_h = min(height - 65, sh / sw * overview_w)
    overview_y = 38
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="760" height="{height}" '
             f'viewBox="0 0 760 {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<text x="8" y="18" font-family="sans-serif" font-size="14" fill="#18344a">'
             'Full recorded flame graph</text>',
             '<text x="240" y="18" font-family="sans-serif" font-size="14" fill="#18344a">'
             'Highlighted regions - enlarged with surrounding frames</text>']

    def embed(x, y, width, h, view):
        vx, vy, vw, vh = view
        parts.append(f'<svg x="{x}" y="{y}" width="{width}" height="{h}" '
                     f'viewBox="{vx} {vy} {vw} {vh}" preserveAspectRatio="xMidYMid meet">'
                     '<g font-family="Verdana" font-size="12">')
        for f in frames:
            if f['x'] + f['w'] >= vx and f['x'] <= vx+vw and f['y']+f['h'] >= vy and f['y'] <= vy+vh:
                parts.append(f['element'])
        parts.append('</g></svg>')

    embed(8, overview_y, overview_w, overview_h, (0, 0, sw, sh))
    summary = []
    row_h = (height - 40) / len(selected)
    scale = overview_w / sw
    for index, (f, label) in enumerate(selected):
        color = colors[index % len(colors)]
        # The exact same frame is outlined in full view and detail view.
        ox, oy = 8 + f['x']*scale, overview_y + f['y']*scale
        parts.append(f'<rect x="{ox-1}" y="{oy-1}" width="{max(3,f["w"]*scale)+2}" '
                     f'height="{f["h"]*scale+2}" fill="none" stroke="{color}" stroke-width="2"/>')
        badge_x, badge_y = ox + f['w']*scale/2, oy-9-index*3
        parts.append(f'<circle cx="{badge_x}" cy="{badge_y}" r="8" fill="{color}"/>'
                     f'<text x="{badge_x}" y="{badge_y+4}" text-anchor="middle" '
                     f'font-family="sans-serif" font-size="11" fill="white">{index+1}</text>')
        top = 35 + index * row_h
        parts.append(f'<text x="240" y="{top+10}" font-family="sans-serif" font-size="14" '
                     f'font-weight="bold" fill="{color}">{index+1}. {html.escape(label)}</text>')
        parts.append(f'<text x="240" y="{top+28}" font-family="sans-serif" font-size="12" '
                     f'fill="#465969">{html.escape(f["name"])} | this frame: {f["share"]:.2f}% inclusive</text>')
        cw = min(540, max(300, f['w']+90))
        ch = 100
        cx = max(0, min(sw-cw, f['x']-35))
        cy = max(0, f['y']-55)
        px, py, pw, ph = 240, top+37, 510, row_h-49
        # Fit without stretching; duplicate transform for the overlay rectangle.
        s = min(pw/cw, ph/ch)
        dx, dy = px+(pw-cw*s)/2, py+(ph-ch*s)/2
        parts.append(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" '
                     'fill="#fafbfc" stroke="#d3dce4"/>')
        embed(px, py, pw, ph, (cx, cy, cw, ch))
        parts.append(f'<rect x="{dx+(f["x"]-cx)*s}" y="{dy+(f["y"]-cy)*s}" '
                     f'width="{f["w"]*s}" height="{f["h"]*s}" fill="none" '
                     f'stroke="{color}" stroke-width="2"/>')
        summary.append({k: v for k, v in f.items() if k != 'element'})
    if sh < 2000:
        y = overview_y+overview_h+24
        for line in ['Original widths and stack depth.', 'Imports and harness retained.',
                     'Each outline marks one call path.', 'The same function may recur.',
                     'Percentages are inclusive,',
                     'not flat self-time totals.']:
            parts.append(f'<text x="8" y="{y}" font-family="sans-serif" font-size="12" '
                         f'fill="#465969">{line}</text>')
            y += 19
    parts.append('</svg>')
    (OUT / target).write_text('\n'.join(parts), encoding='utf-8')
    return dict(source=source, output=target, source_frame_count=len(frames),
                transformation='full original frame geometry plus annotated context crops',
                highlights=summary)


def diagram(name, height, boxes, arrows):
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 {height}">',
             '<defs><marker id="a" markerWidth="8" markerHeight="8" refX="7" refY="4" '
             'orient="auto"><path d="M0 0L8 4L0 8Z" fill="#526b7e"/></marker></defs>']
    for path in arrows:
        parts.append(f'<path d="{path}" fill="none" stroke="#526b7e" stroke-width="1.6" '
                     'marker-end="url(#a)"/>')
    for x, y, w, h, lines, hardware in boxes:
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" '
                     f'fill="{"#e7f0f6" if hardware else "#f6f4ee"}" stroke="#8298a9"/>')
        start = y + h / 2 - (len(lines) - 1) * 10 + 5
        for i, line in enumerate(lines):
            parts.append(f'<text x="{x+w/2}" y="{start+i*20}" text-anchor="middle" '
                         f'font-family="sans-serif" font-size="14" fill="#18344a">'
                         f'{html.escape(line)}</text>')
    parts.append('</svg>')
    (OUT / name).write_text('\n'.join(parts), encoding='utf-8')


def main():
    OUT.mkdir(exist_ok=True)
    summaries = []
    profiles = [
        ('flame_nbody_stock_full.svg', 'print_nbody_stock.svg', [
            ('list_ass_item', 'List stores'), ('PyNumber_AsSsize_t', 'Index conversion'),
            ('binary_op1', 'Generic arithmetic dispatch')]),
        ('pyspy_nbody_opt_full.svg', 'print_nbody_opt.svg', [('advance', 'Generated integration loop')]),
        ('pyspy_pyflate_stock_full.svg', 'print_pyflate_stock.svg', [
            ('find_next_symbol', 'Huffman matcher'), ('move_to_front', 'Alphabet updates'),
            ('bwt_reverse', 'Inverse BWT')]),
        ('pyspy_pyflate_opt_full.svg', 'print_pyflate_opt.svg', [
            ('bwt_reverse', 'Inverse BWT'), ('bwt_transform', 'Index-table construction')]),
    ]
    for source, target, highlights in profiles:
        summaries.append(flame(source, target, None, highlights))
    (OUT / 'profile_counts.json').write_text(json.dumps(summaries, indent=2) + '\n', encoding='utf-8')
    diagram('grape_report.svg', 226, [
        (8, 8, 170, 72, ['Python + driver', 'one advance(dt, n)'], False),
        (230, 8, 258, 72, ['AXI4-Lite config / status', 'FP64 state, DT, NSTEPS'], True),
        (540, 8, 212, 72, ['State registers', 'working + committed'], True),
        (8, 132, 204, 80, ['Step / pair scheduler', 'issue control'], True),
        (260, 132, 280, 80, ['Shared FP64 datapath', '3 add, 3 mul, sqrt, reciprocal'], True),
        (590, 132, 162, 80, ['Ordered accumulate', 'position / commit'], True),
    ], ['M178 44H230', 'M488 44H540', 'M646 80V108H110V132',
        'M212 172H260', 'M540 172H590', 'M710 132V80'])
    diagram('pyflate_stages.svg', 185, [
        (8, 8, 170, 65, ['Compressed bytes', '67,562 B'], False),
        (230, 8, 300, 65, ['Bit reader + Huffman', 'MTF + RUNA/RUNB'], True),
        (584, 8, 168, 65, ['L-vector', '336,184 B'], False),
        (420, 112, 332, 60, ['Inverse BWT + RLE4', 'Python'], False),
        (8, 112, 340, 60, ['Output + MD5 check', '399,360 B'], False),
    ], ['M178 40H230', 'M530 40H584', 'M668 73V112', 'M420 142H348'])
    diagram('decode_report.svg', 235, [
        (8, 8, 230, 66, ['CPU: parse block headers', 'configure via AXI4-Lite'], False),
        (310, 8, 442, 66, ['Platform DMA', '32-bit bits + 8-bit selectors in; L-vector out'], False),
        (8, 137, 230, 82, ['huffman_engine', 'align / canonical decode', 'selector control'], True),
        (294, 137, 226, 82, ['mtf_cam', 'rank select / shift', 'run expander + FIFO'], True),
        (576, 137, 176, 82, ['Output packer', '64-bit data', '+ byte enables'], True),
    ], ['M123 74V137', 'M310 42H268V112H123V137', 'M238 178H294',
        'M520 178H576', 'M664 137V74', 'M200 74V100H407V137'])
    print('Generated four print profiles and three architecture/pipeline diagrams.')
    for item in summaries:
        print(f'{item["source"]}: {item["source_frame_count"]} original frames, {len(item["highlights"])} highlights')


if __name__ == '__main__':
    main()
