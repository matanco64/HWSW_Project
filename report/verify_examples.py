"""Validate report teaching examples against shipped functions; no third-party packages.

Functions are loaded from their AST without running benchmark imports or timers.
This checks the examples, not the full software/RTL regression or the VM performance.
"""
import ast
import collections
import copy
import itertools
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parent.parent


def load_functions(path, names, namespace):
    tree = ast.parse((ROOT / path).read_text())
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name in names]
    assert {node.name for node in selected} == set(names)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)


def main():
    ns = {'PRIMARY_BITS': 11, 'MASK': [(1 << i) - 1 for i in range(65)],
          'collections': collections, 'RUN4': re.compile(rb'(?s)(.)\1{3}(?=.)')}
    load_functions('benchmarks/bm_pyflate/run_benchmark.py',
                   ['build_huffman_table', 'bwt_transform', 'move_to_front', 'rle4_expand'], ns)
    pb, _, table, limit, base, perm = ns['build_huffman_table']([2, 2, 2, 3, 3], 2)
    assert pb == 2 and table == [2, 34, 66, 0]
    assert limit[3] == 7 and base[3] == 3 and perm[6 - base[3]] == 3
    # The expected bitstream and symbols come directly from the printed codebook.
    bits, pos, decoded = '01110', 0, []
    while pos < len(bits):
        z = int(bits[pos:pos + pb], 2)
        entry = table[z]
        if entry:
            width, symbol = entry & 31, entry >> 5
        else:
            width = pb
            while z > limit[width]:
                width += 1
                z = int(bits[pos:pos + width], 2)
            symbol = perm[z - base[width]]
        decoded.append(symbol)
        pos += width
    assert decoded == [1, 3] and pos == 5
    assert ns['build_huffman_table']([2, 2, 2, 3, 3], 3)[2] == [2, 2, 34, 34, 66, 66, 99, 131]
    print('Huffman: primary hit, fallback, packed entries and exact consumed bits PASS')

    L = b'banana'
    pointer = ns['bwt_transform'](L)
    assert pointer == [1, 3, 5, 0, 2, 4] == sorted(range(len(L)), key=lambda i: L[i])
    print('BWT: pointer table equals independent stable-sort oracle PASS')
    logical = list('abcd')
    ns['move_to_front'](logical, 2)
    reverse = list('dcba')
    selected = reverse.pop(-3)
    reverse.append(selected)
    assert selected == 'c' and logical == list('cabd') and reverse == logical[::-1]
    assert ns['rle4_expand'](b'AAAA\x02B') == b'AAAAAAB'
    print('MTF and final RLE4 examples PASS')

    bodies = [[[0.0, 0.0, 0.0], [0.0, 0.02, 0.0], 1.0],
              [[1.0, 0.0, 0.0], [0.0, 0.1, 0.0], 0.002],
              [[0.0, 2.0, 0.0], [-0.05, 0.0, 0.0], 0.003]]
    generated_bodies, stock_bodies = copy.deepcopy(bodies), copy.deepcopy(bodies)
    generated_pairs = list(itertools.combinations(generated_bodies, 2))
    stock_pairs = list(itertools.combinations(stock_bodies, 2))
    gen = {'_bodies': generated_bodies}
    load_functions('benchmarks/bm_nbody/run_benchmark.py', ['_advance_source'], gen)
    exec(gen['_advance_source'](generated_bodies, generated_pairs), gen)
    stock = {}
    load_functions('dev/nbody/t0_stock.py', ['advance'], stock)
    gen['advance'](0.01, 100)
    stock['advance']((stock_bodies, stock_pairs), 0.01, 100)
    def packed(state):
        return b''.join(struct.pack('>d', value) for r, v, mass in state for value in r + v + [mass])
    assert packed(generated_bodies) == packed(stock_bodies)
    print('Nbody: actual generator matches stock on three bodies / 100 steps bit for bit PASS')


if __name__ == '__main__':
    main()
