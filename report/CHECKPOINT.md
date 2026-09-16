# Repository cleanup - 2026-09-16

The active benchmark set is pyflate and nbody. Removed the abandoned benchmark's
source, development experiments, results, profiles and stamps, and updated the
manifest, VM defaults and active documentation. Older course instructions and
verbatim prompt records remain unchanged.

Consolidated the September 7 checkpoint into `history/checkpoint_20260907.md`.
The bundled nbody stock oracle is now `dev/nbody/stock_run_benchmark.py`; its bytes
are unchanged and its callers use the new path. Removed the obsolete generated
submission ZIP. After the user paused OneDrive syncing, restored all 14 figures
to `report/fig/` and removed the duplicate `report/fig 2/` folder. Their contents
match the committed originals and remained stable across repeated checks.

Validation: 24 unit tests, nbody Python exactness checks (including rolled fallback),
77 report-table rows and worked examples pass. Native checks skip locally because
the extensions are unavailable. The renamed bundled oracle ran 20,000 steps, and a
stubbed VM-runner check selected only the two remaining benchmarks. Shell syntax
and source whitespace checks pass. All four figure-geometry checks pass after
restoration. The software, worked-example and text-table checks were rerun and
passed with syncing paused; no figure paths disappeared during verification.
No performance reruns performed.

---

# Report revision status - 2026-09-15

Completed the three requested follow-ups using the user's updated flame graphs and
pyflate hardware section. The current reports are nbody 6 pages, pyflate 7 pages,
and appendix 5 pages. The September 7 notes are preserved in `history/checkpoint_20260907.md`.

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
