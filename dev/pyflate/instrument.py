"""Instrumentation: measure the structural properties that justify the choice of
decode strategy -- code-length distributions, MTF rank distribution, symbol
counts, table-rebuild counts, and the linear-scan position histogram.

Run:  <python> dev/pyflate/instrument.py
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import t0_stock as S  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    '..', '..', 'benchmarks', 'bm_pyflate', 'data',
                    'interpreter.tar.bz2')

stats = {
    'symbols': 0,
    'blocks': 0,
    'tables_built': 0,
    'scan_positions': collections.Counter(),   # index reached in self.table
    'code_lengths': collections.Counter(),     # bits of the matched code
    'mtf_ranks': collections.Counter(),        # r-1 passed to move_to_front
    'runa_runb': 0,
    'literals': 0,
    'rle4_runs': 0,
    'rle4_literals': 0,
    'table_len': collections.Counter(),
    'table_minmax': collections.Counter(),
    'lenhist_per_table': [],
}

_orig_find = S.HuffmanTable.find_next_symbol


def find_next_symbol(self, field, reversed=True):
    cached_length = -1
    cached = None
    for i, x in enumerate(self.table):
        if cached_length != x.bits:
            cached = field.snoopbits(x.bits)
            cached_length = x.bits
        if (reversed and x.reverse_symbol == cached) or (not reversed and x.symbol == cached):
            field.readbits(x.bits)
            stats['symbols'] += 1
            stats['scan_positions'][i] += 1
            stats['code_lengths'][x.bits] += 1
            return x.code
    raise Exception("unfound")


S.HuffmanTable.find_next_symbol = find_next_symbol

_orig_mtf = S.move_to_front


def move_to_front(l, c):
    if len(l) > 6:          # the favourites list, not the selector list
        stats['mtf_ranks'][c] += 1
    _orig_mtf(l, c)


S.move_to_front = move_to_front

_orig_tables = S.compute_tables


def compute_tables(b, huffman_groups, symbols_in_use):
    t = _orig_tables(b, huffman_groups, symbols_in_use)
    stats['blocks'] += 1
    stats['tables_built'] += len(t)
    for tab in t:
        stats['table_len'][len(tab.table)] += 1
        stats['table_minmax'][(tab.min_bits, tab.max_bits)] += 1
        h = collections.Counter(x.bits for x in tab.table)
        stats['lenhist_per_table'].append(dict(sorted(h.items())))
    return t


S.compute_tables = compute_tables

_orig_dhb = S.decode_huffman_block


def main():
    out = S.decompress(DATA)
    print("output bytes:", len(out))
    print("blocks:", stats['blocks'], " tables built:", stats['tables_built'])
    print("table sizes:", dict(stats['table_len']))
    print("(min_bits,max_bits) per table:", dict(stats['table_minmax']))
    print("per-table code-length histograms:")
    for i, h in enumerate(stats['lenhist_per_table']):
        print("   table %d: %s" % (i, h))
    print()
    n = stats['symbols']
    print("huffman symbols decoded:", n)
    print("code-length histogram (bits -> count, %):")
    for b, c in sorted(stats['code_lengths'].items()):
        print("   %2d bits : %7d  %5.1f%%" % (b, c, 100.0 * c / n))
    wavg = sum(b * c for b, c in stats['code_lengths'].items()) / n
    print("   mean code length: %.2f bits" % wavg)

    sp = stats['scan_positions']
    tot = sum(sp.values())
    cum = 0
    print()
    print("LINEAR-SCAN position (index into the 258-entry sorted table):")
    print("   mean scan length: %.1f entries" % (sum(k * v for k, v in sp.items()) / tot))
    print("   max scan length : %d" % max(sp))
    for pct in (50, 75, 90, 95, 99):
        cum = 0
        for k in sorted(sp):
            cum += sp[k]
            if cum * 100.0 / tot >= pct:
                print("   p%-2d scan length : %d" % (pct, k))
                break
    # how many snoopbits calls does the scan make? = number of distinct
    # code-length transitions traversed
    print()
    mr = stats['mtf_ranks']
    tm = sum(mr.values())
    print("MTF calls:", tm)
    print("   mean rank: %.2f" % (sum(k * v for k, v in mr.items()) / tm))
    cum = 0
    for k in sorted(mr):
        cum += mr[k]
        if k <= 8 or k in (15, 31, 63, 127):
            print("   rank %3d: %7d (%5.1f%%)  cum %5.1f%%"
                  % (k, mr[k], 100.0 * mr[k] / tm, 100.0 * cum / tm))
    print("   max rank:", max(mr))


if __name__ == '__main__':
    main()
