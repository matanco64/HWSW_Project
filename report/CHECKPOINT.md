# Report revision checkpoint — 2026-09-07

This is an intentional work-in-progress checkpoint, requested before the session
limit. The latest PDFs are **not the final submission**.

## User preferences and remaining scope

- Keep the playful spacecraft introductions, refining their connection to the workloads.
- Shorten repetition and correct technical/provenance errors while retaining technical depth.
- Show full original flame graphs with highlighted regions and enlarged details, rather than
  collapsing them into function summaries.
- Explain native versus Python performance with measured instructions, cycles, IPC, branch
  and cache behavior, in addition to elapsed time.

## Completed

- Rewrote the two report sources, retaining the introductions and correcting baseline,
  environment, profiling-scope, hardware-status and performance claims.
- Added a shared 11 pt layout, clearer tables, pipeline/hardware diagrams and Windows builds.
- Built and visually inspected an intermediate set of PDFs: nbody 4 pages, pyflate 4 pages,
  appendix 3 pages. Generated real text companions replacing the TODO skeletons.
- Updated the figure generator to preserve full original flame-graph geometry, add numbered
  outlines and show magnified context crops. Generation succeeds, but these latest figures
  have not yet been integrated into the page layout or visually checked in the PDFs.
- Ran 24 matched-work counter measurements on the course VM: 2 benchmarks × 2 backends ×
  2 event passes × 3 rounds. Measurements use acknowledged perf FIFO enable/disable controls
  after initialization/warmup and a fixed guest CPU. Existing benchmark sources were unchanged.
- Retrieved all raw measurements into `results/native_counters_20260907/`.

## Resume here

1. **Validate counters before reporting them.** `report/summarize_counters.py` intentionally
   stopped at `nbody_python_cache_1.perf.csv`: `L1-dcache-loads` returned zero despite 100%
   counter running time. The requested `:u` suffix is absent on the returned L1 event names.
   Do not interpret the zero as a real absence of loads or claim all events were valid.
   Inspect all event passes. Core events and generic cache events may still be usable;
   remeasure L1 events separately if needed. Normalize names only after checking semantics.
   The archive import already succeeded; run the summarizer **without** `--import-base64`
   when resuming. It must not overwrite/reimport the existing raw data directory.
2. Add validated median counter tables and interpretation to both native comparison sections.
   Include absolute instructions/misses per completed benchmark, not just IPC/miss rates.
   Account for the small gating boundary and distinguish this matched-loop experiment from
   the saved rigorous pyperf comparisons. Verify output digests across all configurations.
3. Update report captions, Appendix A3 and README: they still describe the superseded
   function-grouped flame graphs. The generator now uses full original SVGs plus crops.
   Nbody's stock view now uses the C-level debug profile, highlighting `list_ass_item`,
   `PyNumber_AsSsize_t` and `binary_op1`; its old Python-frame caption is no longer correct.
4. Give the full-profile/detail plates enough space, likely a dedicated profiling page.
   Preserve original widths and distinguish inclusive call-path shares from flat self time.
5. Rebuild PDFs/text companions, render every page and inspect for overflow, tiny labels,
   misplaced highlights and table breaks. Sources have changed since the last PDF build.

## Commands and tools

- Windows: `./report/build.ps1 -Typst 'C:/path/to/typst.exe'`.
  Typst 0.14.2 is installed locally through WinGet; its protected package directory may
  require execution approval. WSL is not required for PDF builds.
- Linux/WSL: `./report/build.sh` with `TYPST` set if needed.
- Figures: `python report/make_figures.py` (standard library only).
- Counter summary: `python report/summarize_counters.py`.
- Counter collection: `report/measure_native_counters.py` on Linux, with `--repo` and a
  fresh `--out` directory; raw protocol metadata is retained with the results.
- PDF review: Poppler `pdftoppm`, `pdfinfo`, `pdftotext` are available on Windows.
- Read `VM_GUIDE.local.md` for private VM access instructions; do not commit that file.

The earlier VM correctness checks passed for shipped Python/native nbody after 20,000 steps
and for Python/hybrid pyflate output, intermediate L-vector and ending bit position.
No hardware RTL or software benchmark implementation was changed during this report revision.
