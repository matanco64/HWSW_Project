# Stock vs optimized nbody counters (2026-10-04, VM @ 97365b6)

Same protocol as `report/measure_native_counters.py` (3 rounds, 64 warm loops,
CPU 0, perf FIFO-gated user-mode events), via a one-off variant of that script
(not committed: code freeze; sha256 70fccb2e36e9a9d4e4ac3d6604e490e31c09c609491d2d8cc2b4b48d6ce3c58b)
whose `stock` backend loads pyperformance's original bm_nbody. Medians per iteration:

| | stock | optimized (re-measured) |
|---|---|---|
| ms/iter | 228.13 | 146.67 |
| instructions | 1,688.18 M | 1,089.98 M |
| cycles | 543.90 M | 349.90 M |
| IPC | 3.10 | 3.12 |
| branches | 288.63 M | 185.97 M |

All 6 core runs share output sha256 31fa324f991b...
