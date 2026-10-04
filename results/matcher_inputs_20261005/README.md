# Is the Huffman matcher optimization input dependent? (VM, 2026-10-05)

Tiers T1 (stock linear-scan matcher), T2 (canonical decode, inlined bit
reader) and T3 (flat 11-bit primary table + back-end changes) from
`dev/pyflate/` at f2dc1c7, run on five inputs compressed with `bz2 -9`,
CPython 3.10.12 on the course VM, `taskset -c 0`, best of 5. Every tier's
output equals the original bytes. "scan" = mean entries the stock matcher
checks per symbol (dev/pyflate/instrument.py), "p99" its 99th percentile,
">PB%" the share of codes longer than 11 bits (the T3 fallback path).

Driver: one-off script, not committed (code freeze); sha256 96e8b632e8bf15e1c04810f7dae388043ca2bfb843d65a7e9e27cfb0b2f39837.
Inputs: the benchmark tarball; repo-root *.txt repeated to 400 KB; 400 KB of
random.Random(0) bytes; 400 KB of b'a'; the first 200 bytes of the text.

    python 3.10.12  PRIMARY_BITS 11  best of 5
    input                   KB  symbols    scan     p99    >PB%     T1 ms     T2 ms     T3 ms  T1/T2  T1/T3
    benchmark tarball    390.0   148271     6.0      49    0.72     676.8     456.6     275.8   1.48   2.45
    English text         390.6   185205     5.3      56    0.80     820.8     578.6     319.4   1.42   2.57
    random bytes         390.6   399995   124.5     250    0.02    5626.1     908.2     566.4   6.19   9.93
    one repeated byte    390.6       26     1.6       5    0.00       3.9       3.8       4.0   1.02   0.96
    tiny (200 B text)      0.2      194    13.7      54    0.00       1.6       0.9       0.7   1.81   2.24

T1/T2 isolates the matcher change. T1/T3 also includes the regex RLE4 and
counting-sort BWT changes.
