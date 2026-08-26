---
name: hw-mode
description: Turn the hardware-flow mode of this checkout on or off (`/hw-mode on|off|status`). Use when the user wants to enable or silence the hw hooks and hw-* skills on this machine, or when a hardware skill finds the mode unset or off.
disable-model-invocation: true
---

# hw-mode — the explicit signal for hardware work

The hardware flow (hooks in `.claude/settings.json`, the `hw-*` skills) must not disturb a
software-only teammate. `hw/.advisor/mode` (gitignored, per machine) holds the answer:

| Mode | Effect |
|---|---|
| `unset` | first session asks once via AskUserQuestion (SessionStart hook injects the instruction) |
| `on` | `hw/PROGRESS.md` injected at session start; stop-time stale-sim reminder; `/hw-flow` allowed |
| `off` | every hardware hook silent; `/hw-flow` refuses and points here |

Path-scoped hooks (SV lint, golden guard, STATUS render, friction log) never fire outside `hw/`
and are not affected by the mode.

## Procedure

- `/hw-mode status` → run `python3 tools/hw/mode.py` and report.
- `/hw-mode on` / `/hw-mode off` → run `python3 tools/hw/mode.py on|off`, confirm, and say that
  session-start injection takes effect on the next session.
- No argument → ask with AskUserQuestion (header "HW flow", options "HW flow" / "Software only"),
  then set accordingly.

Never set the mode silently on the user's behalf from another skill: `hw-flow` asks first.
