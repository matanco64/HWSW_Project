# Project close-out tracker

Trackable version of the close-out plan. Tick a box (`[ ]` → `[x]`), commit, move on.
Owner: **Y** = Yuval (hardware), **M** = Matan (software / reports), **B** = both.
Each step names the command or artifact that proves it is done — tick only with that in hand.

Progress: `grep -c '^- \[x\]' report/CLOSEOUT.md` done / `grep -c '^- \[ \]' report/CLOSEOUT.md` left.

**Current phase → A**

---

## Phase A — Save the work (Y, ~10 min)

- [ ] A1 Review the diff: `git diff --stat` then `git diff hw/ README.md` — nothing unexpected.
- [ ] A2 Commit the reconciliation + hardware report + README fix (branch or main, your call).
      Proof: `git log -1 --stat` shows `hw/docs/hardware_report.md`, `report/REPORT_DELTAS.md`,
      the six `hw/*/docs/*.md`, `hw/STATUS.json`, `README.md`, `.gitignore`.
- [ ] A3 Drop the redundant stash: `git stash drop` (its content is already in `prompt.txt`).
      Proof: `git stash list` is empty.
- [ ] A4 Push. Proof: `git status -sb` first line ends `main...origin/main` with no ahead/behind.

**Gate A:** `git status --porcelain | grep -v synth/formal` is empty.

## Phase B — Read the reports as a grader (B, ~1.5 h)

Check every section against the required contents in `project_instructions.md` "What You Need
to Submit → 1. Benchmark Reports": Overview · Initial Analysis · Optimizations · Performance
Comparison · Hardware Proposal · Conclusion. Note anything you could not explain aloud.

- [ ] B1 `report_nbody.pdf` — all six sections present and explainable. (M reads SW, Y reads §5)
- [ ] B2 `report_pyflate.pdf` — all six sections present and explainable. (M reads SW, Y reads §5)
- [ ] B3 `report_appendix.pdf` — know what A1–A7 hold so you can point to them in Q&A.
- [ ] B4 `hw/docs/hardware_report.md` — Y re-reads; §6 table maps every §7 bullet × module.
- [ ] B5 Walk `report/REPORT_DELTAS.md`; mark each item **apply** / **skip** in the file.
      Must-apply: **C4** (huffman 8.9 → 25.1 MHz post-CTS). Optional: B1–B3.

**Gate B:** a list of "could not explain" items exists (empty is fine) and C4 is marked apply.

## Phase C — Close the one inconsistency (M, ~30 min)

The submitted `report_pyflate.txt` still says huffman ≈ 8.9 MHz pre-placement (3 places);
measured post-CTS is 25.1 MHz. Only Matan edits `report/*.typ`.

- [ ] C1 Apply REPORT_DELTAS **C4** to `report/report_pyflate.typ` lines ~303, 304, 310–312.
- [ ] C2 Apply any B1–B3 items marked "apply" in Phase B.
- [ ] C3 Rebuild: `cd report && ./build.sh` (needs `typst` + `pdftotext`/poppler on the build
      machine; Yuval's WSL has typst but not pdftotext).
- [ ] C4 Verify: `grep -c "8.9 MHz" report_pyflate.txt` → 0 (or 1 if kept as labeled history)
      and `grep -c "25.1" report_pyflate.txt` ≥ 1. Root `.txt`/`.pdf` newer than `.typ`.
- [ ] C5 Commit + push the rebuilt reports.

**Gate C:** README, `hw/` docs, `STATUS.json` and `report_pyflate.txt` all say 25.1 MHz.

## Phase D — Reproducibility (B, ~30 min, mostly waiting)

- [ ] D1 Read `README.md` top to bottom as a stranger: repo structure + how to run (§8).
- [ ] D2 `bash -n script_nbody.sh script_pyflate.sh` — both parse.
- [ ] D3 Optional real run on the VM: `tools/vm_launch.sh start nbody`, then `status` / `fetch`.
- [ ] D4 Hardware sanity (doubles as the §9 live-demo candidate later):
      `make -C hw/mtf_cam sim` → 16/16 PASS.
- [ ] D5 `./make_submission.sh`; open the archive: reports, scripts, `hw/`, README,
      `prompt.txt` all inside.

**Gate D:** D2, D4, D5 pass on a fresh shell.

## Phase F — Final close & submit (B, ~20 min) — depends on A–D only

- [ ] F1 Prompt files: `prompt.txt` is the required name; `promts.txt` is Matan's log. Merge
      into `prompt.txt` or add a one-line pointer from `prompt.txt` to `promts.txt`.
- [ ] F2 `git log --oneline -30` reads as a development story (§8 +5 bonus); squash only if
      something is embarrassing, otherwise leave history.
- [ ] F3 Final push; `git status -sb` clean and in sync.
- [ ] F4 Submit per course instructions; record the submitted commit hash here: `________`.

**Gate F:** submitted hash recorded above.

## Phase P — Presentation (B; AFTER submission, BEFORE the scheduled session)

Not part of the upload (§8 lists only reports, scripts, HW files, prompt.txt), but §9 still
requires a 20–25 min talk + 5–10 min Q&A at a time the staff schedule. Submit first (Gate F),
then do this; the repo is frozen so nothing here changes the submission.

- [ ] P1 Read `report/defense_guide.md` — the existing talk outline.
- [ ] P2 Agree the split: ~12 min software (M) · ~10 min hardware (Y) · 2 min close (B).
- [ ] P3 Software slides (M): benchmark → flame graph → bottleneck → optimization → results,
      per benchmark; one slide for the Rust tier.
- [ ] P4 Hardware slides (Y): boundary chosen · 3 block diagrams (`hw/*/docs/block_diagram.svg`)
      · cross-module table (`hardware_report.md` §4) · trade-off slide (grape K1, mtf W-sweep,
      huffman storage) · **one honest-limits slide**: no GDS, 50 MHz missed, speedups are
      projections, evidence stages.
- [ ] P5 Demo plan: which command runs live (D4 candidate) and a fallback recording/screenshot.
- [ ] P6 Rehearse once with a timer; trim to 25 min.
- [ ] P7 Q&A prep — each of you can answer the list below without notes.

**Gate P:** rehearsal ≤ 25 min and every grill question has an owner.

---

## Grill questions (owner in brackets)

- Why do all three modules miss 50 MHz, and what fixes each? [Y] — grape: pipeline the
  integrate-multiply path; huffman: pipeline the table build / register the readback mux;
  mtf: register the CAM read-mux.
- Why did huffman's 8.9 MHz disappear? [Y] — pre-placement wireload artifact on one very
  high-fanout net; post-CTS buffering gives the real 25.1 MHz (same class as grape's pre-PnR net).
- Why does the nbody accelerator lose to the 9.53 ms native software? [Y+M] — compute-bound at
  19.46 MHz (127 ms); the win is gated on timing closure, not the interface.
- Why is the Huffman speedup ~2× at any clock? [Y] — Amdahl-fraction-bound (f ≈ 0.50), not
  clock-bound.
- What does "post-CTS" mean and why isn't it silicon? [Y] — placed cells + real clock tree, but
  no detailed routing / GDS; net RC would still move it.
- Why these two benchmarks? [M] — complementary hardware boundaries (streaming symbol pipeline
  vs stateful force loop).
- How were the 7% / 4.00× / 6.61× numbers measured? [M] — course VM, pyperf, 120 values,
  pinned CPU, canonical run `vm_canonical_20260910_2c8c754` (Appendix A7).
- Why no MDP? [M] — retired to focus the two-benchmark scope (commit `4abb512`).
