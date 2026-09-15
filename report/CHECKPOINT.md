# Report revision status - 2026-09-15

Completed the three requested follow-ups using the user's updated flame graphs and
pyflate hardware section. The current reports are nbody 6 pages, pyflate 7 pages,
and appendix 5 pages. The September 7 notes below are historical, not current headlines.

- Added nbody and pyflate before/after examples, checked Huffman lookup/fallback,
  BWT pointer construction, reversed MTF and final RLE4 examples, and a generated
  nbody pair-dependency diagram.
- Preserved all four updated flame-graph SVGs byte for byte. Rebalanced document
  pages; the full-frame overview, row-aligned crops and aggregate labels remain.
- Updated nbody to the recorded 124-cycle RTL result and September 14 post-CTS
  estimate, with older mapped-area evidence labeled separately. Clarified pyflate
  module versus chain evidence, cycle model versus RTL, preliminary timing,
  default-activity power, DMA assumptions and projected SRAM area.
- Corrected pyflate whole-BWT/traversal wording and the profile/Amdahl mismatch;
  retained the eight canonical timing means and 120-value sample counts.
- Condensed methodology, corrected statistical wording, and preserved the old
  appendix under `report/history/`.
- Added `defense_guide.md` (23-minute route, 26 questions/answers, evidence links,
  demos) and detailed per-improvement prompts in root `promts.txt`.

Validation: report build successful; 77 checked table rows survive text export;
all four source-frame geometries and badge separation checks pass; worked examples
pass; eight canonical means/sample counts and defense links checked; all 18 final
PDF pages rendered and visually reviewed. Source diff whitespace check passes
(PDF binary content excluded). No new VM timings, native builds, RTL simulations,
physical-design runs or workload power measurements were performed in this revision.
The physical-run artifacts cited by the hardware documents are not in this checkout;
new hardware prose is based on the recorded documents, with that scope disclosed.

---

# Report revision status - 2026-09-07

The interrupted report work was preserved in commit `b23206b`. Its report-related
follow-ups are now complete; the root PDFs and text companions have been rebuilt.

## Completed report work

- Preserved the playful introductions, tightened the prose, and corrected baseline,
  environment, profiling-scope and hardware-status claims.
- Added matched Python/native comparisons for both benchmarks: instructions, cycles,
  IPC, branches, branch misses, and generic cache references/misses per iteration.
- Validated all 24 captured runs, including source hashes, loop counts, CPU selection,
  requested backends and equal final-output digests. Raw data and the derived summary
  are refreshed in `results/vm_release_20260907/counters/`; the original capture
  remains in `results/native_counters_20260907/`.
- Excluded both L1 events because the load denominator returned invalid zeros. No L1
  miss-rate claim is supported. Fresh captures no longer request those events.
- Verified actual pyflate dispatch on the VM: Python made zero native calls; native
  and auto each made one, with identical correct MD5 and output length. Rust was
  already integrated; the main Python comparison and hybrid-native comparison are
  separate runner stages. Future pyflate profiles now explicitly pin Python.
- Replaced grouped profiles with full original frame geometry, numbered outlines
  and enlarged context crops. Automated checks verify all four source frame sets
  and non-overlapping highlight badges; builds run those checks automatically.
- Rendered and visually inspected the reports: nbody 5 pages, pyflate 5 pages,
  appendix 4 pages, with shared 11 pt typography and unbroken tables.

## Code and measurement boundary

The pyflate Rust code is now split into bindings, bit reader, Huffman, decoder
and trace modules, with its public API and valid-stream behavior preserved.
Ten Rust unit tests and a rebuilt-extension suite covering seven blocks across
five fixtures passed under WSL CPython 3.12.3 and VM CPython 3.10.12. Oversubscribed tables and invalid
bit offsets now fail cleanly. Dependency resolution is pinned by Cargo.lock.

The refactored Rust source was built and measured in an isolated VM directory.
Pyflate's updated headline table includes stock Python (1129.89 ms), optimized
Python (288.00 ms), and Python plus Rust (173.59 ms): 6.51x overall, 1.66x from Rust.
All three JSONs contain 120 values from 40 workers; source hashes, backend selection,
CPU affinity, build metadata and correctness logs are preserved in
`results/vm_release_20260907/`. Its counter capture also uses the rebuilt extension.

The four previous rigorous reruns were retrieved into `results/vm_rerun_20260907/`.
They also contain 120 values each; the earlier claim that one rigorous job had less
evidence than the older files was incorrect and has been removed from the appendix.
The nbody native comparison now uses that verified rerun (15.00x). The Huffman
example was corrected to canonical codes 00, 01, 10, 110, 111.

No installed VM wheel, existing remote result, or hardware RTL was replaced.

The next performance experiment, if desired, is native inverse BWT: both table
construction and traversal. That is a new optimization beyond this refactor, not
an unimplemented requirement for the report revision.

## Reproduction

- Windows: `./report/build.ps1 -Typst 'C:/path/to/typst.exe'`.
- Linux/WSL: `./report/build.sh` with `TYPST` set if needed.
- Figures: `python report/make_figures.py`, then `python report/check_figures.py`.
- Latest timing summaries: `python report/summarize_refresh.py`.
- Latest counter summary: `python report/summarize_counters.py --directory results/vm_release_20260907/counters`.
- Another capture: add `--directory /path/to/capture` to the summarizer.
- Dispatch check: `python3 report/check_pyflate_backend.py /path/to/repo`, using
  an interpreter with the native wheel installed.
- Rust build/tests: see `rust/pyflate/README.md`; test the explicit newly built
  extension path to avoid accidentally checking an older installed wheel.
- Private VM access instructions remain in the untracked `VM_GUIDE.local.md`.
