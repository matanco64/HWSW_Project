# Hardware-flow lessons

Appended by `hw-advisor` after each gate; one entry per lesson (date, module/stage, friction, fix).

## 2026-08-28 — grape_pipeline/prd

- **Skill invocation bug** — `hw-prd` step 2 says "run the interview with `grill-with-docs`", but
  that skill is `disable-model-invocation: true`; the Skill tool refused it (session 2026-08-28).
  Fix: `hw-prd` (and `hw-mas`/`hw-uarch` if they say the same) should invoke `grilling` +
  `domain-modeling` directly and keep the paper trail itself (`hw/CONTEXT.md`, `hw/docs/adr/`).
- **Golden-model convention discovered late** — `golden/README.md` requires the golden model to
  *wrap* `benchmarks/bm_*` (import + instrument), never re-implement; the first draft of
  `nbody_ref.py` was a copy and had to be rewritten (friction.jsonl 2026-08-28T12:04:00Z). The
  convention lives only in the per-module README. Fix: state it in `hw-prd` (the stage that first
  touches `golden/`) and in FLOW.md "Conventions".
- **Tolerances need a calibration step** — the PRD's fidelity bounds (F4/F5) could not be written
  without first running emulation-vs-golden in Python (`golden/calibrate.py`): the naïve
  "|ΔE/E| ≤ 1e-12 energy conservation" was wrong by 8 orders of magnitude (the integrator itself
  drifts 4e-4). Fix: `hw-prd` gets an explicit "calibrate any numeric tolerance in software before
  writing the number" step; same lesson applies to `huffman_engine` throughput claims.
- **`source hw/env.sh` is cwd-relative** — failed when the shell was inside `hw/<module>/golden`
  (friction 12:04:00Z). Fix: skills say `source "$(git rev-parse --show-toplevel)/hw/env.sh"`.
- **Friction-hook noise** — two "failures" (exit 2) were `ls` of a not-yet-existing directory
  inside read-only inspection commands; not friction. Consider ignoring exit codes from commands
  whose first word is `cat`/`ls`/`grep`/`head` in `friction_hook.py`.
