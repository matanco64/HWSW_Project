#!/usr/bin/env python3
"""UserPromptSubmit hook: append every prompt sent in a Claude Code session
rooted in this repo to prompt.txt (course requirement §10, AI-tool prompt log).

Wired up in .claude/settings.json via a *relative* path so it works on every
teammate's machine (an absolute path silently broke this in HW2).
"""

import datetime
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG = ROOT / "prompt.txt"
MAX_LEN = 4000
# Slash commands are not prompts, and neither is anything the harness injects
# into the prompt stream on the user's behalf: background-task notifications,
# system reminders and local-command transcripts are machine output, and
# logging them buried the authors' own prompts under them (they were 71% of
# this file before they were stripped).
SKIP_PREFIXES = (
    "/",
    "<task-notification>",
    "<system-reminder>",
    "<local-command",
    "<command-name>",
)


def main() -> None:
    payload = json.load(sys.stdin)
    prompt = (payload.get("prompt") or "").strip()
    if not prompt or prompt.startswith(SKIP_PREFIXES):
        return

    if len(prompt) > MAX_LEN:
        prompt = prompt[:MAX_LEN] + f"\n... [truncated, {len(prompt)} chars total]"

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = f"\n{ts} — Claude Code session (auto-logged)\nPrompt: \"{prompt}\"\n"

    with open(LOG, "a", encoding="utf-8") as f:
        f.write(entry)


if __name__ == "__main__":
    main()
