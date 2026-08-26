---
name: hw-status
description: Read or update hardware-flow progress in hw/STATUS.json through tools/hw/status.py and render hw/PROGRESS.md. Use when a stage starts, finishes, blocks, or needs a gate result or metric recorded, or when asked "where are we" on a hardware module.
---

# hw-status — the only writer of `hw/STATUS.json`

Schema, states and stage names: `hw/FLOW.md` "Tracking". Every write goes through
`python3 tools/hw/status.py`; editing the JSON by hand or from another script breaks the evidence
trail. `hw/PROGRESS.md` is generated, never edited.

## Commands

| Command | Effect |
|---|---|
| `status.py next <module>` | prints `<stage> <state>` of the first stage not `done` (or `done done`) |
| `status.py show [<module>]` | prints the module's stage/gate/metric tree as JSON |
| `status.py set <module> <stage> <state> [--reason "<text>"]` | sets state; stamps `started` on `in_progress`, `finished` on `done`; `--reason` required for `blocked` |
| `status.py gate <module> <stage> "<criterion>" pass\|fail\|n/a "<evidence>"` | upserts one gate row; criterion text must match the FLOW.md table wording |
| `status.py metric <module> <dv\|ppa>.<key> <value>` | sets one metric (`dv.line_cov`, `ppa.fmax_mhz`, ...) |
| `status.py render` | regenerates `hw/PROGRESS.md` (also run by the PostToolUse hook) |

`make -C hw/<module> status` is an alias for `render`.

## State machine

`todo → in_progress → (review →) done`, with `blocked` reachable from `in_progress` and returning
to `in_progress` on retry. `review` exists only for checkpoints (`prd`, `mas`, `uarch`,
`dv_signoff`). `done` is terminal; re-opening a stage is a user decision and is recorded with
`set ... in_progress --reason "reopened: <why>"`.

## Evidence conventions

Evidence is a string a reader can re-run or open, never a summary of opinion:

- A command and its decisive output line: `make -C hw/mtf_cam lint → 0 warnings`.
- A file path plus locator: `hw/mtf_cam/docs/prd.md §3 table`.
- A number with its source: `line 93.4 % (tb/cov/coverage.txt)`.
- For `n/a`, the reason: `formal: no properties listed in testplan §5`.

Human approvals are evidence too: `approved by <user> in session <date>`.

## Typical sequences

Stage start: `set <m> <stage> in_progress`.
Stage end: one `gate` row per criterion in the FLOW.md table, `metric` rows where the stage
produces numbers, then `set` to `review`/`done`/`blocked`.
Query: `next` for the orchestrator, `show` for a human summary; quote `PROGRESS.md` when asked
about overall progress.
