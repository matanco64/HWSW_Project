# Project close-out tracker

Trackable version of the close-out plan. Tick a box (`[ ]` → `[x]`), commit, move on.
Owner: **Y** = Yuval (hardware), **M** = Matan (software / reports), **B** = both.
Each step names the command or artifact that proves it is done — tick only with that in hand.

Progress: `grep -c '^- \[x\]' report/CLOSEOUT.md` done / `grep -c '^- \[ \]' report/CLOSEOUT.md` left.

**Current phase → B4** (Yuval reads the hardware report) · Phase C can start in parallel (Matan)

---

## Phase A — Save the work (Y, ~10 min)

- [x] A1 Review the diff: `git diff --stat` then `git diff hw/ README.md` — nothing unexpected.
- [x] A2 Commit the reconciliation + hardware report + README fix (branch or main, your call).
      Proof: `git log -1 --stat` shows `hw/docs/hardware_report.md`, `report/REPORT_DELTAS.md`,
      the six `hw/*/docs/*.md`, `hw/STATUS.json`, `README.md`, `.gitignore`.
- [x] A3 Drop the redundant stash: `git stash drop` (its content is already in `prompt.txt`).
      Proof: `git stash list` is empty.
- [x] A4 Push. Proof: `git status -sb` first line ends `main...origin/main` with no ahead/behind.

**Gate A:** `git status --porcelain | grep -v synth/formal` is empty.

## Phase B — Read the reports as a grader (B, ~1.5 h)

Check every section against the required contents in `project_instructions.md` "What You Need
to Submit → 1. Benchmark Reports": Overview · Initial Analysis · Optimizations · Performance
Comparison · Hardware Proposal · Conclusion. Note anything you could not explain aloud.

- [x] B1 `report_nbody.pdf` — Y read §5 (2026-09-19): findings R1–R8, R13 in REPORT_DELTAS.
- [ ] B1m Matan reads the nbody software sections the same way.
- [x] B2 `report_pyflate.pdf` — Y read §5 + Conclusion: findings R9–R12, R15–R18; math audit R17 all correct.
- [ ] B2m Matan reads the pyflate software sections the same way.
- [x] B3 `report_appendix.pdf` — optional deliverable (R19); A1–A7 map known; findings R14, R20, R21.
- [ ] B4 `hw/docs/hardware_report.md` — Y re-reads; §6 table maps every §7 bullet × module.
- [x] B5 REPORT_DELTAS triaged: MUST / SHOULD / NICE / no-action table at the top of the file
      (21 reading-pass items R1–R21 + C4).

**Gate B:** B4 read, and the triage table in REPORT_DELTAS is agreed with Matan.

## Phase C — Apply the reading-pass deltas (M, ~2–3 h)

Only Matan edits `report/*.typ`. Work top-down through the triage table in
`report/REPORT_DELTAS.md`: every MUST, then SHOULD as time allows, NICE last.

- [ ] C1 Apply all **MUST** items (C4+R14, R5, R8, R11, R15, R18, R1, R9, R12).
- [ ] C2 Apply **SHOULD** items (R10, R13, R16, R4, R7, R21), then **NICE** (R2, R3, R20, B1, B3).
      Check page counts after R2 (nbody prototyped: stays 6 pages).
- [ ] C3 Rebuild: `cd report && ./build.sh` (needs `typst` + `pdftotext`/poppler on the build
      machine; Yuval's WSL has typst but not pdftotext).
- [ ] C4 Verify: `grep -c "8.9 MHz" report_pyflate.txt` → 0 (or 1 if kept as labeled history)
      and `grep -c "39.9" report_pyflate.txt` ≥ 1. Root `.txt`/`.pdf` newer than `.typ`.
- [ ] C5 Commit + push the rebuilt reports.

**Gate C:** README, `hw/` docs, `STATUS.json` and `report_pyflate.txt` all say 39.9 MHz; both
Conclusions state a hardware bottom line; every MUST row is applied or explicitly declined.

## Phase H — Hardware follow-ups from the reading pass (Y)

- [x] H0 **Correction:** huffman Fmax is **39.9 MHz**, not 25.1 (hold slack misread as setup
      slack; found while preserving evidence). Fixed in ppa.md, integration.md, STATUS.json,
      hardware_report.md, README, REPORT_DELTAS, this file. Chain clock is now mtf-limited (37.6).
- [ ] H0b `signoff_tight` (27 ns) confirmation run → record in ppa.md §3.1 when it lands; read
      **`max.rpt` only** for setup slack.
- [x] H0c Evidence preserved in tracked `hw/<module>/synth/evidence/` (timing + power reports);
      `synth/runs/` is gitignored so graders could not see the sources before.
- [x] H0d Block diagrams regenerated (generator bug + stale grape/huffman content); toolchain
      table added to hardware_report §0.1; citation audit: 63 paths checked.

- [x] H1 Chain co-simulation: `hw/pyflate_accel/` wrapper + test — byte-exact 336,184 B,
      159,303 cycles, also under back-pressure (reproduced firsthand 2026-09-19).
- [x] H2 grape power statement corrected (≈ 19.2 mW indicative; was "not obtained").
- [ ] H3 grape area re-measured on the final netlist (`make -C hw/grape_pipeline area`, running).
      Then: update `ppa.md`, `hardware_report.md`, `STATUS.json`; send the two numbers to Matan
      (R13) so the "pre-prefix area" hedge (R7) can be deleted.
- [ ] H4 Before committing: `git checkout hw/grape_pipeline/synth/yosys.log` (the re-run is
      overwriting this tracked log — 47 MB, must NOT be committed) and delete `area_rerun.log`.
- [ ] H5 Commit + push the reading-pass work: REPORT_DELTAS (R1–R21 + triage), hw docs,
      `hw/pyflate_accel/`, this tracker. Send Matan the link.

**Gate H:** `git status --porcelain | grep -v synth/formal` empty; no file > 5 MB in the commit.

## Phase D — Reproducibility (B, ~30 min, mostly waiting)

- [ ] D1 Read `README.md` top to bottom as a stranger: repo structure + how to run (§8).
- [ ] D2 `bash -n script_nbody.sh script_pyflate.sh` — both parse.
- [ ] D3 Optional real run on the VM: `tools/vm_launch.sh start nbody`, then `status` / `fetch`.
- [ ] D4 Hardware sanity (doubles as the §9 live-demo candidate later):
      `make -C hw/mtf_cam sim` → 16/16 PASS, and `make -C hw/pyflate_accel sim` → 2/2 PASS
      (the whole pyflate chain, byte-exact, 30 s — the best live demo).
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
  high-fanout net; post-CTS buffering gives the real 39.9 MHz (same class as grape's pre-PnR net).
  (An interim 25.1 MHz was MY error: a hold slack misread as setup — corrected, evidence in
  `hw/huffman_engine/synth/evidence/`.)
- Why does the nbody accelerator lose to the 9.53 ms native software? [Y+M] — compute-bound at
  19.46 MHz (127 ms); the win is gated on timing closure, not the interface.
- Why is the Huffman speedup ~2× at any clock? [Y] — Amdahl-fraction-bound (f ≈ 0.50), not
  clock-bound.
- What does "post-CTS" mean and why isn't it silicon? [Y] — placed cells + real clock tree, but
  no detailed routing / GDS; net RC would still move it.
- Why is it called `mtf_cam` if nothing is content-addressed? [Y] — the decode path reads the
  list by rank; the name follows the MTF list structure (the encoder searches by content).
- Did the hardware beat the software? [Y] — nbody: ties optimized Python, ≈15× slower than Rust.
  pyflate: ≈28× over the Python symbol loop, ≈1.3× slower than the Rust kernel (parity at 50 MHz),
  end-to-end tie — the stage is ≈2 % of what remains; BWT sets the floor.
- Same clock or CDC between huffman and mtf? How tested? [Y] — one shared clock, no CDC
  (37.6 MHz, mtf-limited); rate difference is cycles/symbol, absorbed by `tready`
  back-pressure. Each side verified standalone vs the same beat contract + golden stream, AND
  the chain is co-simulated (`make -C hw/pyflate_accel sim`): byte-exact 336,184 B, 159,303
  cycles, also under 50 % output back-pressure. Live-demo candidate: runs in 30 s.
- Why these two benchmarks? [M] — complementary hardware boundaries (streaming symbol pipeline
  vs stateful force loop).
- How were the 7% / 4.00× / 6.61× numbers measured? [M] — course VM, pyperf, 120 values,
  pinned CPU, canonical run `vm_canonical_20260910_2c8c754` (Appendix A7).
- Why no MDP? [M] — retired to focus the two-benchmark scope (commit `4abb512`).
