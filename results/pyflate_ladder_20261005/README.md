# pyflate tier ladder, micro-benchmarks and cProfile on the course VM (2026-10-05)

`dev/pyflate/` at f2dc1c7 plus `benchmarks/bm_pyflate/data`, copied into a clean
`/tmp` directory on the VM (the VM checkout has local edits), CPython 3.10.12,
pinned with `taskset -c 0`. Commands, in order:

    python3 bench.py -r 7          # ladder, interleaved best-of-7
    python3 micro.py               # primitives on the real block data
    python3 bench.py --profile t0_stock
    python3 bench.py --profile t3_table

Full output in `run.log`. Every tier passed MD5 + byte-equality with `bz2`.

| tier | best | vs T0 |
|---|---|---|
| T0 stock | 1126.9 ms | 1.00x |
| T1 micro | 675.7 ms | 1.67x |
| T2 canonical | 454.9 ms | 2.48x |
| T3 table | 273.6 ms | 4.12x |

| primitive | stock | optimized |
|---|---|---|
| move-to-front, 89,837 calls | 155.29 ms | 11.44 ms (reversed list) |
| RLE4 expansion | 126.50 ms | 23.78 ms (regex) |
| BWT histogram | 27.42 ms | 19.16 ms (Counter) |
| inverse-BWT walk | 54.87 ms | 49.35 ms (bytearray) |

cProfile function calls: T0 3,185,456 -> T3 423,177.
