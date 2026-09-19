# Project close-out tracker

Trackable version of the close-out plan. Tick a box (`[ ]` → `[x]`), commit, move on.
Owner: **Y** = Yuval (hardware), **M** = Matan (software / reports), **B** = both.
Each step names the command or artifact that proves it is done — tick only with that in hand.

Progress: `grep -c '^- \[x\]' report/CLOSEOUT.md` done / `grep -c '^- \[ \]' report/CLOSEOUT.md` left.

**Current phase → F3b / F4** — a second local round (2026-09-20: software-side fixes, larger-N
projection) sits on top of pushed `20e8080`; Yuval: push again, then submit the new HEAD. Ownership change 2026-09-19: Yuval took over Phase C; rule applied — only the
hardware section, the Conclusion and the appendix hardware paragraph of the `.typ` files were
edited, software text is byte-identical (script-checked). Matan's note: `report/FOR_MATAN.md`.

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
- [x] B1m nbody software sections read as a grader (agent, 2026-09-20): every number re-derived
      from `results/`, no mismatch; 11 coverage/wording fixes applied (`report/FOR_MATAN.md`).
- [x] B2 `report_pyflate.pdf` — Y read §5 + Conclusion: findings R9–R12, R15–R18; math audit R17 all correct.
- [x] B2m pyflate software sections read the same way: no numeric mismatch; fixes applied incl. two
      provenance corrections (10 not 11 Rust tests on the VM; later commits not re-timed).
- [x] B3 `report_appendix.pdf` — optional deliverable (R19); A1–A7 map known; findings R14, R20, R21.
- [x] B4 `hw/docs/hardware_report.md` — agent grader-review (cold read vs the brief, 81 citations,
      number audit vs STATUS / evidence / `.typ`): timing and numerics confirmed from setup reports;
      13 findings fixed (K3 speedup claim 3.78× not "3.8–4.5×", MTF share 13.44 %, wrong section
      citations, SRAM wording, history removed, mtf interfaces, glossary). Yuval's own skim optional.
- [x] B5 REPORT_DELTAS triaged: MUST / SHOULD / NICE / no-action table at the top of the file
      (21 reading-pass items R1–R21 + C4).

**Gate B:** B4 read, and the triage table in REPORT_DELTAS is agreed with Matan.

## Phase C — Apply the reading-pass deltas (Y, done 2026-09-19)

Applied by Yuval under the hardware-only rule. Per-item status: `report/REPORT_DELTAS.md`.

- [x] C1 All **MUST** items applied (C4+R14, R5, R8, R11, R15, R18, R1, R9, R12).
- [x] C2 **SHOULD** (R10, R13, R16, R4, R7, R21, R22) and in-scope **NICE** (R3 in §5, B1, B3) applied.
      R2 **declined**: the global `style.typ` line re-flows a pyflate software page (+1 page); §5 uses
      local spacing. R20 and software-side R3 left to Matan. Pages: nbody 6→7, pyflate 7→8, appendix 5→6.
- [x] C3 Rebuilt: `nix shell nixpkgs#poppler-utils -c report/build.sh` — all table rows verified in the
      `.txt`; an unedited baseline build first reproduced the committed `.txt` byte for byte.
- [x] C4 Verified: "8.9 MHz" → 0, "39.9" → 3 in `report_pyflate.txt`; software part of every `.typ`
      and of both report `.txt` identical to the pre-edit baseline; `report/fig/`, `style.typ` unchanged.
- [x] C5 Committed locally (`c87cc74` + follow-ups). Push is F3.
- [x] C6 Independent judge vs `project_instructions.md`: no FAIL; 10 defects, all in-scope ones fixed
      (stale STATUS gate evidence, two pyflate framings reconciled, nbody tolerances now state the
      measured result, jargon, "measured" → "simulated", README names the `.txt` deliverables).
      Left to Matan: section titles differ from the brief's names (no "Performance Comparison"
      heading), "T3" undefined in pyflate §3.

**Gate C:** README, `hw/` docs, `STATUS.json` and `report_pyflate.txt` all say 39.9 MHz; both
Conclusions state a hardware bottom line; every MUST row is applied or explicitly declined.

## Phase H — Hardware follow-ups from the reading pass (Y)

- [x] H0 **Correction:** huffman Fmax is **39.9 MHz**, not 25.1 (hold slack misread as setup
      slack; found while preserving evidence). Fixed in ppa.md, integration.md, STATUS.json,
      hardware_report.md, README, REPORT_DELTAS, this file. Chain clock is now mtf-limited (37.6).
- [x] H0b `signoff_tight` (27 ns) landed: timing **met**, worst setup slack +1.685 ns (`ws.max.rpt`)
      → 39.5 MHz, confirms 39.9 within 1 %; hold met. In ppa.md §3.1 + `synth/evidence/tight27_*`.
- [x] H0c Evidence preserved in tracked `hw/<module>/synth/evidence/` (timing + power reports);
      `synth/runs/` is gitignored so graders could not see the sources before.
- [x] H0d Block diagrams regenerated (generator bug + stale grape/huffman content); toolchain
      table added to hardware_report §0.1; citation audit: 63 paths checked.

- [x] H1 Chain co-simulation: `hw/pyflate_accel/` wrapper + test — byte-exact 336,184 B,
      159,303 cycles, also under back-pressure (reproduced firsthand 2026-09-19).
- [x] H2 grape power statement corrected (≈ 19.2 mW indicative; was "not obtained").
- [x] H3 grape area re-measure: **closed without a result** — stopped after ~7 h in Yosys ABC
      (time limit). The one-sentence "area is from before the final rewrite" caveat is kept in the
      report, README, hardware_report and recorded in grape `ppa.md`.
- [x] H4 Done — before committing: `git checkout hw/grape_pipeline/synth/yosys.log` (the re-run is
      overwriting this tracked log — 47 MB, must NOT be committed) and delete `area_rerun.log`.
- [x] H5 Done (`54a738c`, pushed) — commit + push the reading-pass work: REPORT_DELTAS (R1–R21 + triage), hw docs,
      `hw/pyflate_accel/`, this tracker. Send Matan the link.

**Gate H:** `git status --porcelain | grep -v synth/formal` empty; no file > 5 MB in the commit.

## Phase D — Reproducibility (B, ~30 min, mostly waiting)

- [x] D1 README: hardware paragraph refreshed (no history, chain co-sim, how to reproduce the
      hardware checks, link to the hardware report); structure block now names `report_*.txt`.
- [x] D2 `bash -n script_nbody.sh script_pyflate.sh` — both parse.
- [x] D3 n/a — no software changed; the hardware is simulation and does not run on the VM.
- [x] D4 (run 2026-09-19: 16/16 and 2/2 PASS, byte-exact) Hardware sanity (doubles as the §9 live-demo candidate later):
      `make -C hw/mtf_cam sim` → 16/16 PASS, and `make -C hw/pyflate_accel sim` → 2/2 PASS
      (the whole pyflate chain, byte-exact, 30 s — the best live demo).
- [x] D5 (2026-09-19: all gates pass — unit tests, nbody bit-exactness oracles, text export,
      worked examples; native checks SKIP here because the Rust wheels are not installed on this
      host; archive lists reports `.txt`+`.pdf`, scripts, README, `prompt.txt`, `hw/`; needs
      `pyperf` importable — here `PYTHONPATH=<scratch> ./make_submission.sh`) `./make_submission.sh`; open the archive: reports, scripts, `hw/`, README,
      `prompt.txt` all inside.

**Gate D:** D2, D4, D5 pass on a fresh shell.

## Phase F — Final close & submit (B, ~20 min) — depends on A–D only

- [x] F1 Single prompt log: `promts.txt` merged verbatim into `prompt.txt` (delimited block),
      file removed, README + CHECKPOINT links updated (`3aff904`).
- [x] F2 `git log --oneline -30` read: a coherent development story; nothing squashed.
- [x] F3 (done 2026-09-19: `origin/main` = `20e8080`, no ahead/behind) **Yuval:** final push — `git pull --rebase --autostash origin main && git push origin main`;
      then `git status -sb` shows `main...origin/main` with no ahead/behind. (Local work is committed
      and the tree is clean; nothing has been pushed since `54a738c`.)
- [ ] F4 **Yuval:** submit per course instructions (repo URL; or the zip from `./make_submission.sh`
      if a URL is not accepted). First push (`20e8080`) done 2026-09-19; after the 2026-09-20 round push again and record the
      submitted `git rev-parse --short HEAD` here: `________`.

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
