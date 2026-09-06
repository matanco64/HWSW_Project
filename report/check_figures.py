"""Verify that every generated overview preserves the source's frame geometry."""
from collections import Counter
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
NS = '{http://www.w3.org/2000/svg}'


def frames(tree):
    result = []
    for group in tree.iter(NS + 'g'):
        title, rect = group.find(NS + 'title'), group.find(NS + 'rect')
        if title is None or rect is None:
            continue
        if re.search(r' \([\d,]+ samples?, [\d.]+%\)', title.text or ''):
            result.append((title.text, tuple(sorted(rect.attrib.items()))))
    return Counter(result)


def main():
    metadata = json.loads((ROOT / 'report/fig/profile_counts.json').read_text())
    for entry in metadata:
        source = ET.parse(ROOT / 'results' / entry['source'])
        output = ET.parse(ROOT / 'report/fig' / entry['output']).getroot()
        overview = output.find(NS + 'svg')
        assert overview is not None
        expected, actual = frames(source), frames(overview)
        assert actual == expected, f'Lost or changed frames: {entry["output"]}'
        assert sum(actual.values()) == entry['source_frame_count']
        badges = output.findall(NS + 'circle')
        assert len(badges) == len(entry['highlights'])
        for i, first in enumerate(badges):
            for second in badges[i+1:]:
                dx = float(first.get('cx')) - float(second.get('cx'))
                dy = float(first.get('cy')) - float(second.get('cy'))
                assert dx*dx + dy*dy >= 16*16, 'Overlapping highlight badges'
        print(f'{entry["output"]}: all {sum(actual.values())} source frames preserved; badges separated')


if __name__ == '__main__':
    main()
