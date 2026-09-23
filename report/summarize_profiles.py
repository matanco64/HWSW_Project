"""Flat function tables from the recorded profiles, with self and inclusive
percentages labelled as such.

A flame graph shows where time goes but is a poor thing to read a number off:
every width is *inclusive* of children, a function can appear at several call
paths, and the reports' print figures crop some labels. This produces the
companion a reader actually needs -- a short table per profile with both
percentages, explicitly named.

The two profile kinds are read differently because they record different things:

  perf_report_<bench>_<tag>.txt   perf's own flat report. Its first two columns
                                  are already "Children" (inclusive) and "Self",
                                  so they are read directly.
  pyspy_<bench>_<tag>_full.svg    a flame graph. Inclusive width comes from each
                                  frame's recorded sample count; self time is
                                  that frame's width minus the widths of the
                                  frames stacked directly on it.

Neither is re-sampled; both are re-read from `results/`.

    python3 report/summarize_profiles.py                 # every known profile
    python3 report/summarize_profiles.py --top 12
    python3 report/summarize_profiles.py --json report/fig/profile_functions.json
    python3 report/summarize_profiles.py --only perf_report_nbody_stock.txt \
        --group 'list access=^(list_|listiter_|PyNumber_AsSsize_t|PyLong_AsSsize_t)'

`--group NAME=REGEX` sums the *self* time of every symbol matching REGEX and
lists the contributors. Prose in the reports that adds up a family of symbols
("list access costs N%") should quote a number this prints, with the regex it
came from, rather than a figure a reader cannot reconstruct.

Summing self time across perf rows is the correct operation even though perf
emits some symbols more than once: an `(inlined)` entry carries inclusive time
and zero self, and separate entries for one symbol are separate contributions.
The self column over a whole report sums to ~100%, which is the check.

Percentages are shares of that profile's own total, so they compare call paths
within one graph and never across two independently normalized graphs.
"""
import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, 'results')
NS = '{http://www.w3.org/2000/svg}'

# The profiles the reports actually show, in report order.
PROFILES = [
    ('nbody stock (C frames, python3-dbg)', 'perf', 'perf_report_nbody_stock.txt'),
    ('nbody optimized (C frames, python3-dbg)', 'perf', 'perf_report_nbody_opt.txt'),
    ('nbody optimized (Python frames, py-spy)', 'flame', 'pyspy_nbody_opt_full.svg'),
    ('pyflate stock (C frames, python3-dbg)', 'perf', 'perf_report_pyflate_stock.txt'),
    ('pyflate optimized (C frames, python3-dbg)', 'perf', 'perf_report_pyflate_opt.txt'),
    ('pyflate stock (Python frames, py-spy)', 'flame', 'pyspy_pyflate_stock_full.svg'),
    ('pyflate optimized (Python frames, py-spy)', 'flame', 'pyspy_pyflate_opt_full.svg'),
]

# "    99.33%     0.02%  python3-dbg  python3.10d   [.] _PyEval_Vector"
PERF_ROW = re.compile(
    r'^\s*(\d+\.\d+)%\s+(\d+\.\d+)%\s+\S+\s+(\S+)\s+\[[^\]]+\]\s+(.+?)\s*$')


def read_perf(path):
    """Flat rows from `perf report --stdio`, ignoring the call-graph tree.

    perf prints each function's summary row at the left margin and then indents
    its call chain underneath with '|' and '--' characters; only the summary
    rows match here, so the tree is skipped without having to parse it.
    """
    rows = []
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            if line.startswith('#') or not line.strip():
                continue
            m = PERF_ROW.match(line)
            if not m:
                continue
            inclusive, self_pct, dso, symbol = m.groups()
            rows.append({'name': symbol, 'object': dso,
                         'inclusive_pct': float(inclusive),
                         'self_pct': float(self_pct)})
    if not rows:
        raise SystemExit('no flat rows parsed from %s' % path)
    return rows, None


def read_flame(path):
    """Self and inclusive shares per function from a flame-graph SVG.

    Frames are laid out with the root at the bottom, one row per stack depth,
    and each frame's horizontal extent contained by its parent's. Children are
    therefore the frames exactly one row above whose x-range falls inside this
    frame's, and self time is what is left of a frame once they are subtracted.

    Note that the row *pitch* is not the rectangle height: these graphs draw
    15px bars on a 16px grid, so stepping by the height lands between rows,
    finds no children, and makes every frame look like a leaf.
    """
    tree = ET.parse(path)
    frames = []
    for group in tree.iter(NS + 'g'):
        title, rect = group.find(NS + 'title'), group.find(NS + 'rect')
        if title is None or rect is None:
            continue
        m = re.search(r'^(.*?) \(([\d,]+) samples?, ([\d.]+)%\)',
                      title.text or '')
        if not m:
            continue
        # py-spy labels a frame `func (file:line)`, where the line is
        # whichever statement was executing when the sample landed. Aggregate
        # to `func (file)`: per-line rows would split one function across a
        # dozen entries, while the bare function name would merge pyperf's
        # `compute` with the benchmark's and attribute one's time to the other.
        frames.append({
            'name': re.sub(r':\d+\)$', ')', m[1]),
            'x': float(rect.get('x')), 'y': float(rect.get('y')),
            'w': float(rect.get('width')), 'h': float(rect.get('height')),
            'samples': int(m[2].replace(',', '')),
        })
    if not frames:
        raise SystemExit('no frames parsed from %s' % path)

    # The widest frame on the bottom row is the profile's root ("all").
    bottom = max(f['y'] for f in frames)
    root = max((f for f in frames if f['y'] == bottom), key=lambda f: f['w'])
    total = root['samples']

    by_row = {}
    for f in frames:
        by_row.setdefault(f['y'], []).append(f)

    rows_y = sorted(by_row)
    pitch = min((b - a for a, b in zip(rows_y, rows_y[1:])),
                default=frames[0]['h'])

    eps = 0.01
    for f in frames:
        children = [c for c in by_row.get(f['y'] - pitch, [])
                    if c['x'] >= f['x'] - eps
                    and c['x'] + c['w'] <= f['x'] + f['w'] + eps]
        f['self_samples'] = f['samples'] - sum(c['samples'] for c in children)
        f['parents'] = [p for p in by_row.get(f['y'] + pitch, [])
                        if f['x'] >= p['x'] - eps
                        and f['x'] + f['w'] <= p['x'] + p['w'] + eps]

    # A function reached through several call paths is summed. A function that
    # calls itself is counted once per outermost occurrence, so recursion does
    # not inflate its inclusive share past 100%.
    def has_same_named_ancestor(f):
        seen, stack = set(), list(f['parents'])
        while stack:
            p = stack.pop()
            key = (p['x'], p['y'])
            if key in seen:
                continue
            seen.add(key)
            if p['name'] == f['name']:
                return True
            stack.extend(p['parents'])
        return False

    agg = {}
    for f in frames:
        if f is root:
            continue
        e = agg.setdefault(f['name'], {'name': f['name'], 'inclusive': 0,
                                       'self': 0, 'sites': 0})
        e['self'] += f['self_samples']
        e['sites'] += 1
        if not has_same_named_ancestor(f):
            e['inclusive'] += f['samples']

    rows = [{'name': e['name'], 'object': None, 'sites': e['sites'],
             'inclusive_pct': 100.0 * e['inclusive'] / total,
             'self_pct': 100.0 * e['self'] / total}
            for e in agg.values()]
    return rows, total


def collect(top, only=None, patterns=None):
    out = []
    for label, kind, filename in PROFILES:
        if only and filename not in only and label not in only:
            continue
        path = os.path.join(RESULTS, filename)
        if not os.path.exists(path):
            print('skipping %s (missing)' % filename, file=sys.stderr)
            continue
        rows, total = (read_perf if kind == 'perf' else read_flame)(path)
        groups = group_totals(rows, patterns or [])
        rows.sort(key=lambda r: (-r['self_pct'], -r['inclusive_pct']))
        out.append({'profile': label, 'kind': kind, 'source': filename,
                    'total_samples': total, 'functions': rows[:top],
                    'self_pct_accounted': sum(r['self_pct'] for r in rows),
                    'groups': groups})
    return out


def group_totals(rows, patterns):
    """Self-time sum per named group, with the rows that contributed."""
    out = []
    for name, pattern in patterns:
        rx = re.compile(pattern)
        hits = [r for r in rows if rx.search(r['name']) and r['self_pct'] > 0]
        hits.sort(key=lambda r: -r['self_pct'])
        out.append({'group': name, 'pattern': pattern,
                    'self_pct': sum(r['self_pct'] for r in hits),
                    'members': hits})
    return out


def report(tables, stream=sys.stdout):
    for t in tables:
        print('\n%s' % t['profile'], file=stream)
        print('  source: results/%s%s'
              % (t['source'],
                 '' if t['total_samples'] is None
                 else '  (%d samples)' % t['total_samples']), file=stream)
        width = max([len(f['name']) for f in t['functions']]
                    + [len(r['name']) + 2 for g in t.get('groups', ())
                       for r in g['members']])
        print('  %-*s %10s %10s' % (width, 'function', 'self %', 'incl %'),
              file=stream)
        for f in t['functions']:
            print('  %-*s %9.2f%% %9.2f%%'
                  % (width, f['name'], f['self_pct'], f['inclusive_pct']),
                  file=stream)
        for g in t.get('groups', ()):
            print('\n  group %r matches /%s/: %.2f%% of self time, from %d '
                  'symbols' % (g['group'], g['pattern'], g['self_pct'],
                               len(g['members'])), file=stream)
            for r in g['members']:
                print('    %-*s %9.2f%%' % (width - 2, r['name'],
                                            r['self_pct']), file=stream)
    print('\nself % = time in the function itself; incl % = time in it and '
          'everything it calls.\nShares are of a profile\'s own total, so '
          'they compare call paths\nwithin one graph and never across two.',
          file=stream)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--top', type=int, default=10,
                    help='functions per profile (default: 10)')
    ap.add_argument('--only', action='append',
                    help='restrict to this profile source filename or label')
    ap.add_argument('--group', action='append', metavar='NAME=REGEX',
                    help='sum the self time of symbols matching REGEX')
    ap.add_argument('--json', metavar='PATH', help='also write JSON')
    args = ap.parse_args()

    patterns = []
    for spec in args.group or []:
        if '=' not in spec:
            ap.error('--group needs NAME=REGEX, got %r' % spec)
        name, _, pattern = spec.partition('=')
        patterns.append((name, pattern))

    tables = collect(args.top, args.only, patterns)
    report(tables)
    if args.json:
        with open(args.json, 'w') as fh:
            json.dump(tables, fh, indent=2, sort_keys=True)
        print('\nwrote %s' % args.json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
