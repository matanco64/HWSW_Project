"""Verify that every report table survives the PDF-to-text export intact.

The `.txt` companions are named course deliverables, not a convenience, and
they are produced by `pdftotext` -- a heuristic that reconstructs rows from
glyph positions, whose output depends on the implementation. Poppler's
`-layout` kept these tables intact; a rebuild with xpdf's `pdftotext` 4.00
`-layout` paired rows with the *previous* row's values, so the text deliverable
stated, in a readable and entirely plausible layout, the wrong cost for every
pyflate ablation. Nothing in the build failed, and the PDF was correct. The
builds now prefer `-table` where it exists; this check gates whichever ran.

So this checks the property that actually matters: for each data row of each
table in each `report_*.typ`, the row's label must be followed by its own cell
values, in order, *before the next label of the same table appears*. A row
whose values wrap onto the following line is cosmetic and passes; a value that
turns up after another row's label has been re-associated and fails. A text
export that is not valid UTF-8 fails too (Typst math letters export that way).

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
MAX_ROW_SPAN = 2000        # characters; a guard, the next label is the real cut


def strip_markup(text):
    """Reduce a Typst cell to the characters pdftotext will emit."""
    text = text.replace('`', '').replace('*', '')
    text = re.sub(r'#[a-zA-Z-]+\([^)]*\)', '', text)
    text = text.replace('--', '–')          # Typst renders `--` as an en dash
    return ' '.join(text.split())


def tables(typ_path):
    """List of tables; each is a list of (label, [values]) checkable rows."""
    with open(typ_path, encoding='utf-8') as fh:
        lines = fh.read().splitlines()
    out, current = [], None
    for line in lines:
        if '#result-table(' in line:
            current = []
            out.append(current)
        if current is None:
            continue
        if line.strip() == ')':
            current = None
            continue
        if 'table.header' in line or 'table.cell' in line or not ROW.match(line):
            continue
        cells = [c for c in (strip_markup(c) for c in CELL.findall(line)) if c]
        if len(cells) < 2:
            continue
        label, values = cells[0], cells[1:]
        # A label that is itself a number gives no anchor to check against.
        if re.fullmatch(r'[\d.,%–-]+', label):
            continue
        current.append((label, values))
    return [t for t in out if t]


def _row_intact(text, label, values, other_labels):
    """Is some occurrence of `label` followed by its values before another label?"""
    for match in re.finditer(re.escape(label), text):
        start = match.end()
        end = min(len(text), start + MAX_ROW_SPAN)
        for other in other_labels:
            nxt = text.find(other, start, end)
            if nxt != -1:
                end = nxt
        pos, ok = start, True
        for value in values:
            found = text.find(value, pos, end)
            if found == -1:
                ok = False
                break
            pos = found + len(value)
        if ok:
            return True
    return False


def check_paths(base, typ_path, txt_path, verbose=False):
    """Check one report source against its text export."""
    if not os.path.exists(txt_path):
        return ['%s.txt not found -- run report/build.sh first' % base]
    problems = []
    raw = open(txt_path, 'rb').read()
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        text = raw.decode('utf-8', 'replace')
        problems.append(
            '%s: text export is not valid UTF-8 at byte %d (%s). Typst math in '
            'the source is the usual cause; set the expression as code instead.'
            % (base, exc.start, exc.reason))

    checked = 0
    for rows in tables(typ_path):
        labels = [label for label, _ in rows]
        for label, values in rows:
            if label not in text:
                problems.append('%s: row %r does not appear in the text export'
                                % (base, label))
                continue
            others = [o for o in labels if o != label and label not in o]
            if _row_intact(text, label, values, others):
                checked += 1
            else:
                problems.append(
                    '%s: row %r is not followed by its own values %s before '
                    'the next row -- the text export has re-associated the '
                    'table rows' % (base, label, values))
    if verbose:
        print('%-18s %d table rows verified' % (base, checked))
    return problems


def check(base, verbose=False):
    return check_paths(base, os.path.join(HERE, base + '.typ'),
                       os.path.join(ROOT, base + '.txt'), verbose)


def main(argv):
    bases = argv[1:] or sorted(
        os.path.splitext(f)[0] for f in os.listdir(HERE)
        if f.startswith('report_') and f.endswith('.typ'))
    problems = []
    for base in bases:
        problems += check(base[:-4] if base.endswith('.typ') else base, verbose=True)
    for p in problems:
        print('FAIL: %s' % p, file=sys.stderr)
    if problems:
        print('\n%d problem(s) in the text export. The PDF may look correct; the '
              '.txt deliverable is not.\nRestructure the table (spanning header '
              'rows and very narrow cells are the usual triggers)\nor move the '
              'data into a verbatim block, then rebuild.' % len(problems),
              file=sys.stderr)
        return 1
    print('all report tables survive the text export')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
