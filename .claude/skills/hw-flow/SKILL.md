---
name: hw-flow
description: Run the next hardware-flow stage for one accelerator module (`/hw-flow <module>`), evaluating its gate and stopping at human checkpoints.
disable-model-invocation: true
---

# hw-flow — orchestrator

Implements `hw/FLOW.md` "Orchestration". One invocation advances one module by at most one stage,
and stops at every checkpoint. `hw/FLOW.md` is the contract; read it before the first run in a
session. All `STATUS.json` writes go through `hw-status` (`tools/hw/status.py`).

## Input

`<module>` ∈ `order` of `hw/STATUS.json` (`grape_pipeline`, `huffman_engine`, `mtf_cam`). With no
argument, ask which module.

## Procedure

0. **Check the mode.** `python3 tools/hw/mode.py` must print `on`. If `off` or `unset`, do not
   proceed silently: ask with AskUserQuestion (header "HW flow") whether to enable hardware mode
   on this checkout; on yes run `python3 tools/hw/mode.py on`, otherwise stop (see `hw-mode`).
1. **Locate the stage.** `python3 tools/hw/status.py next <module>` prints `<stage> <state>` for the
   first stage not `done`. Stage ↔ skill ↔ gate come from the FLOW.md table; checkpoints are
   `prd`, `mas`, `uarch`, `dv_signoff`.
2. **Branch on state.**
   - `review` (checkpoint awaiting approval): present the artifact path, the gate table from
     `STATUS.json`, and the open `hw-review` findings. Ask for approval. On approval
     `status.py set <module> <stage> done`; on rejection record the objections as findings and
     `set ... in_progress`. Stop either way.
   - `blocked`: print the failing criterion and its evidence; ask whether to retry the stage
     (`set ... in_progress`, continue at step 3) or stop.
   - `todo` / `in_progress`: `set ... in_progress`, continue.
3. **Run the stage skill** via the Skill tool: `hw-prd`, `hw-mas`, `hw-uarch`, `hw-rtl`,
   `hw-dv-testplan`, `hw-dv-bringup`, `hw-dv-signoff` (for both `dv_coverage` and `dv_signoff`),
   `hw-ppa`, `hw-integrate`. The stage skill produces the artifacts and records its own gate rows.
4. **Evaluate the gate.** Re-run every evidencing command the stage skill names (`make -C hw/<module>
   lint|sim|cov|area|...`) and confirm each criterion has a `pass` or `n/a` row via
   `status.py gate`. A criterion with no row is a fail.
5. **Pre-review before checkpoints.** For `prd`, `mas`, `uarch` run `hw-review` in spec mode; for
   `dv_signoff` run it in RTL mode. Every finding of severity `must` is resolved (artifact edited,
   commands re-run) before the gate row `hw-review findings resolved` is set `pass`.
6. **Record the outcome.**
   - Any `fail` → `status.py set <module> <stage> blocked --reason "<criterion>"`. Stop.
   - All pass and stage is a checkpoint → `set ... review`. Stop with the summary in step 8.
   - All pass, not a checkpoint → `set ... done`; go to step 1 for the next stage, once at most
     (one non-checkpoint stage per invocation keeps the advisor loop tight).
7. **Advise.** After every gate evaluation, pass or fail, run `hw-advisor` for `<module> <stage>`.
8. **Summary for the human.** Stage, state, artifact paths, gate table (criterion → result →
   evidence), open findings, advisor proposals, and the exact next command.

## Rules

- Never set a gate row yourself without the command output in hand; never set `done` on a
  checkpoint without an explicit approval message from the user.
- Lockstep order (FLOW.md "Modules"): `mas` of any module may start only when `prd` of all three is
  `done`; `uarch` of `huffman_engine` only after `grape_pipeline` reaches `dv_signoff` `done`, and
  `mtf_cam` likewise after `huffman_engine`. Refuse and explain when the order is violated.
- Golden models (`hw/<module>/golden/`) are hook-protected; a stage needing a change there asks the
  user, it never edits.
