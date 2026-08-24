---
name: log-prompt
description: Append a prompt to this project's prompt.txt AI-usage log (course requirement §10), tagged with its source. Use when the user says "log this prompt", "add this to prompt.txt", or wants to record an AI interaction that happened outside this Claude Code session (ChatGPT, Copilot, a teammate's session) -- prompts sent inside this session are already auto-logged by a UserPromptSubmit hook, so this skill is for everything the hook can't see.
---

# Log Prompt

Append an entry to `prompt.txt` at the project root. This is the manual
complement to the automatic `UserPromptSubmit` hook (`tools/log_prompt_hook.py`),
which already logs every prompt sent inside this Claude Code session. Use
this skill for prompts issued somewhere the hook has no visibility into:
another AI tool, a teammate's session, or something worth logging
retroactively.

## Input

The user will give you either:
- Raw prompt text to log, or
- A prompt plus which tool/model it was sent to (e.g. "log this ChatGPT
  prompt: ...").

If they don't say which tool, ask -- "which AI" is part of the disclosure.

## What to do

1. Read `prompt.txt` (Edit requires a prior Read).
2. Append an entry matching the hook-generated style, with an explicit source:

   ```
   <UTC timestamp, e.g. 2026-08-24T19:15:00Z> — <tool name> (manual)
   Prompt: "<prompt text, verbatim>"
   ```

3. If the user also says what the AI's answer was used for, add a
   `Result: ...` line after the prompt (the dated sections at the top of
   `prompt.txt` use the same Prompt/Result convention).
4. Don't summarize or shorten the prompt text itself -- this file is the
   verbatim backing record for the course's AI-usage requirement.
