#!/usr/bin/env python3
"""PostToolUse + PostToolUseFailure (Bash) hook: log failed commands under hw/ to
hw/.advisor/friction.jsonl as {ts, cmd, exit, tail}.

Contract (code.claude.com/docs/en/hooks): the Bash tool_response is
{stdout, stderr, interrupted, isImage} -- there is NO exit-code field documented -- and a
command exiting non-zero is delivered to PostToolUseFailure with a top-level
`error: "Exit code N\\n..."` string. So this hook is wired to both events and derives the
exit code from `error`, falling back to any exit_code/exitCode/returncode field or an
"Exit code N" marker in stderr/stdout.
"""
import datetime
import json
import re
import sys

from _common import HW, ROOT, payload

LOG = HW / ".advisor" / "friction.jsonl"
EXIT_RE = re.compile(r"[Ee]xit code[: ]+(\d+)")


def exit_code(p: dict):
    tr = p.get("tool_response")
    tr = tr if isinstance(tr, dict) else {}
    for k in ("exit_code", "exitCode", "returncode", "code"):
        if isinstance(tr.get(k), int):
            return tr[k]
    for text in (p.get("error") or "", tr.get("stderr") or "", tr.get("stdout") or ""):
        m = EXIT_RE.search(str(text))
        if m:
            return int(m.group(1))
    if p.get("hook_event_name") == "PostToolUseFailure":
        return 1
    return 0


def main() -> None:
    p = payload()
    if p.get("tool_name") != "Bash":
        return
    cmd = (p.get("tool_input") or {}).get("command") or ""
    cwd = p.get("cwd") or ""
    in_hw = "hw/" in cmd or cwd.startswith(str(HW))
    code = exit_code(p)
    if not in_hw or code == 0:
        return
    tr = p.get("tool_response")
    tr = tr if isinstance(tr, dict) else {}
    tail = str(tr.get("stderr") or p.get("error") or tr.get("stdout") or "")[-1000:]
    entry = {"ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "cmd": cmd[:500], "exit": code, "tail": tail}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
