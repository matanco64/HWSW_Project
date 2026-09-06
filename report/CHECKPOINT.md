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
  remain in `results/native_counters_20260907/`.
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
five fixtures passed under WSL CPython 3.12.3. Oversubscribed tables and invalid
bit offsets now fail cleanly. Dependency resolution is pinned by Cargo.lock.

The refactor is a separate source change. The recorded VM
measurements used the previously installed extension, not the newly rebuilt
refactor. No VM wheel, benchmark source, existing remote result, or hardware RTL
was replaced during this report work. The appendix records this distinction.

The next performance experiment, if desired, is native inverse BWT: both table
construction and traversal. That is a new optimization beyond this refactor, not
an unimplemented requirement for the report revision.

## Reproduction

- Windows: `./report/build.ps1 -Typst 'C:/path/to/typst.exe'`.
- Linux/WSL: `./report/build.sh` with `TYPST` set if needed.
- Figures: `python report/make_figures.py`, then `python report/check_figures.py`.
- Saved counter summary: `python report/summarize_counters.py`.
- Another capture: add `--directory /path/to/capture` to the summarizer.
- Dispatch check: `python3 report/check_pyflate_backend.py /path/to/repo`, using
  an interpreter with the native wheel installed.
- Rust build/tests: see `rust/pyflate/README.md`; test the explicit newly built
  extension path to avoid accidentally checking an older installed wheel.
- Private VM access instructions remain in the untracked `VM_GUIDE.local.md`.
