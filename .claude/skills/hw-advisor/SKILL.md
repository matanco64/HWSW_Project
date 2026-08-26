---
name: hw-advisor
description: Mine friction from the last hardware-flow stage and turn it into lessons and skill fixes. Use after every gate evaluation (called by hw-flow and the Stop hook), or when the user says "what went wrong", "lessons", or "improve the hw skills".
---

# hw-advisor — lessons and skill improvement

Input: `<module> <stage>`. Sources, read in this order:

1. `hw/.advisor/friction.jsonl` — one JSON line per failed command/lint/sim under `hw/`
   (`ts`, `cmd`, `exit`, `tail`). Consider entries since the stage's `started` timestamp
   (`python3 tools/hw/status.py show <module>`).
2. The stage's artifacts (FLOW.md table) and `hw/<module>/docs/review_<stage>.md` findings.
3. `git diff` and `git diff --stat` of `hw/` — churn (files edited many times, reverts) is friction
   that never failed a command.

## Procedure

1. **Cluster** the friction: same command failing repeatedly, same lint warning class, same
   review finding type, same file re-edited. Ignore one-off typos.
2. For each cluster write a **lesson**: what went wrong (observable), root cause (the missing
   instruction, wrong assumption, or tool quirk), which skill should change (`hw-*`, or a
   third-party skill's project-local overlay), and the evidence lines.
3. **Append** to `hw/docs/lessons.md` under a heading `## <date> — <module>/<stage>`; one bullet
   per lesson; keep earlier entries untouched. No cluster → append `no friction` with the counts.
4. **Propose skill diffs.** For each lesson naming a skill, draft the concrete SKILL.md edit as a
   unified diff, written under `writing-for-agents` discipline (positive phrasing, one source of
   truth, completion criteria checkable). Prefer sharpening an existing step over adding one;
   keep each SKILL.md within 140 lines.
5. **Ask before applying.** Present the diffs; apply only those the user accepts. Third-party
   skills (`claude-skill-verilog`, `gf-cocotb`, `tb-best-practices`) are vendored copies — an
   accepted change there is also noted at the top of that SKILL.md as a project overlay.
6. **Log.** Each applied change is an AI-shaped edit to the process: append to `prompt.txt` via
   `log-prompt` with source `hw-advisor`, the lesson, and the file changed (course §10).

## Output

Lessons appended (count), diffs proposed / applied, and a one-line risk note for the next stage
("the same X will bite `hw-dv-bringup` unless ...").
