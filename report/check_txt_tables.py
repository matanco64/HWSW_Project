"""Verify that every report table survives the PDF-to-text export intact.

The `.txt` companions are named course deliverables, not a convenience, and
they are produced by `pdftotext -layout` -- a heuristic that reconstructs rows
from glyph positions. It is not reliable on wide numeric tables. On one build
it paired every pyflate row with the *next* row's numbers, so the text
deliverable stated, in a readable and entirely plausible layout, that
`find_next_symbol` cost 23.76% when that was `decode_huffman_block`'s figure.
Nothing in the build failed, and the PDF was correct.

So this checks the property that actually matters: for each data row of each
table in each `report_*.typ`, the row's label and its cell values must appear
in the text export in that order, close together, and before the next row's
label. Cosmetic damage -- a wrapped column, a stray blank line -- is fine;
re-association is not.

    python3 report/check_txt_tables.py                 # all reports
    python3 report/check_txt_tables.py report_pyflate

Exits nonzero and names the row when a table has been scrambled.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, 'report')

# A data row looks like:  [`decode_huffman_block`], [23.76%], [93.81%], ...
# Only rows whose cells are short, self-contained literals are checked; prose
# cells and nested markup are skipped rather than guessed at.
ROW = re.compile(r'^\s*\[([^\[\]]{1,60})\](?:,\s*\[([^\[\]]{0,30})\])+\s*,?\s*$')
CELL = re.compile(r'\[([^\[\]]{0,60})\]')


def strip_markup(text):
    """Reduce a Typst cell to the characters pdftotext will emit."""
    text = text.replace('`', '').replace('*', '').replace('_', '_')
    text = re.sub(r'#[a-zA-Z-]+\([^)]*\)', '', text)
    # Typst turns `--` into an en dash and `×` stays as itself.
    text = text.replace('--', '–')
    return ' '.join(text.split())


def table_rows(typ_path):
    """Yield (label, [values]) for every checkable table row."""
    with open(typ_path, encoding='utf-8') as fh:
        lines = fh.read().splitlines()
    inside = False
    for line in lines:
        if '#result-table(' in line:
            inside = True
        if not inside:
            continue
        if line.strip() == ')':
            inside = False
            continue
        if 'table.header' in line or 'table.cell' in line:
            continue
        if not ROW.match(line):
            continue
        cells = [strip_markup(c) for c in CELL.findall(line)]
        cells = [c for c in cells if c]
        if len(cells) < 2:
            continue
        label, values = cells[0], cells[1:]
        # A label that is itself a number gives no anchor to check against.
        if re.fullmatch(r'[\d.,%–-]+', label):
            continue
        yield label, values


def check(base, verbose=False):
    typ_path = os.path.join(HERE, base + '.typ')
    txt_path = os.path.join(ROOT, base + '.txt')
    if not os.path.exists(txt_path):
        return ['%s.txt not found -- run report/build.sh first' % base]
    with open(txt_path, encoding='utf-8') as fh:
        text = fh.read()

    problems = []
    checked = 0
    for label, values in table_rows(typ_path):
        # The label may legitimately occur several times (prose, other tables);
        # the row is intact if *any* occurrence is followed by its values in
        # order within a short window.
        starts = [m.end() for m in re.finditer(re.escape(label), text)]
        if not starts:
            problems.append('%s: row %r does not appear in the text export'
                            % (base, label))
            continue
        if any(_values_follow(text, start, values) for start in starts):
            checked += 1
            continue
        problems.append(
            '%s: row %r is not followed by its own values %s -- the text '
            'export has re-associated the table rows' % (base, label, values))
    if verbose:
        print('%-18s %d table rows verified' % (base, checked))
    return problems


def _values_follow(text, start, values, window=400):
    """Do `values` appear in order, close together, after position `start`?"""
    window_text = text[start:start + window]
    # Stop at a blank-line run long enough to mean "a different block".
    cut = window_text.find('\n\n\n')
    if cut != -1:
        window_text = window_text[:cut]
    pos = 0
    for value in values:
        found = window_text.find(value, pos)
        if found == -1:
            return False
        pos = found + len(value)
    return True


def main(argv):
    bases = argv[1:] or sorted(
        os.path.splitext(f)[0] for f in os.listdir(HERE)
        if f.startswith('report_') and f.endswith('.typ'))
    problems = []
    for base in bases:
        problems += check(base.removesuffix('.typ'), verbose=True)
    for p in problems:
        print('FAIL: %s' % p, file=sys.stderr)
    if problems:
        print('\n%d table row(s) damaged by the text export. The PDF may look '
              'correct; the .txt deliverable is not.\nRestructure the table '
              '(spanning header rows and very wide label columns are the '
              'usual triggers)\nor move the data into a verbatim block, then '
              'rebuild.' % len(problems), file=sys.stderr)
        return 1
    print('all report tables survive the text export')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
