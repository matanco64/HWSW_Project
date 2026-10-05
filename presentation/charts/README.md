# Charts for the deck

`python charts.py` (matplotlib) writes all four PNGs next to the script. Each function names
the repo file its numbers come from.

| PNG | Slide | Source |
|---|---|---|
| `nbody_ladder.png` | N-Body: original, optimized Python, Python + Rust (log scale) | `results/compare_nbody.txt`, `compare_nbody_native.txt`, `report_nbody.txt` |
| `bh_crossover.png` | Barnes-Hut tree time / direct time vs N, crossing near N = 300 | `results/bigN_sweep.txt` (VM, theta 0.5, best of 7) |
| `pyflate_ladder.png` | "Python rewrites do most of the work": the pyflate tier ladder | `results/compare_pyflate*.txt` (pyperf); starred bars `results/pyflate_ladder_20261005/README.md` (best of 7) |
| `pyflate_ladder_experiment.png` | Same ladder plus the post-submission bar (DRAFT copy of that slide) | as above, plus `results/bwt_rust_20261005/rest2.log` on branch `experiment/bwt-rust` |

The experiment bar (hatched, marked †) is **not part of the submission**. It is labelled
"11.06x vs 161 ms" because it was measured in a later session in which the submitted build ran at
161 ms, not the 170 ms of the submitted results; dividing by 170 would mix sessions.

Style: 8x4 in at 200 dpi (1600x800 px), Arial, navy `#1F3B5C`, accent `#D9822B`.
