#!/usr/bin/env python3
"""Mirror hw/STATUS.json to GitHub Issues via the gh CLI (FLOW.md, "Tracking").

One issue per module x stage, title "[hw][<module>] <STAGE>", labels hw, module:<m>, stage:<s>;
body = gate checklist; closed when the stage is done, open otherwise.
Exits 0 with a single line if gh is missing or not authenticated.
"""

import json
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import status as S  # noqa: E402


def gh(*args, check=True, capture=True):
    return subprocess.run(["gh", *args], check=check, text=True,
                          capture_output=capture, timeout=60)


def body_for(stage: dict) -> str:
    lines = [f"State: **{stage['state']}**"]
    if stage.get("reason"):
        lines.append(f"Reason: {stage['reason']}")
    lines.append("")
    for crit, g in stage["gate"].items():
        box = "[x]" if g.get("result") == "pass" else "[ ]"
        ev = f" — {g['evidence']}" if g.get("evidence") else ""
        lines.append(f"- {box} {crit}{ev}")
    lines.append("")
    lines.append("_Mirrored from hw/STATUS.json by tools/hw/gh_sync.py; edit via tools/hw/status.py._")
    return "\n".join(lines)


def ensure_label(name: str, color: str) -> None:
    gh("label", "create", name, "--color", color, "--force", check=False)


def main() -> None:
    if shutil.which("gh") is None:
        print("gh_sync: gh CLI not installed; skipping GitHub mirror")
        return
    if gh("auth", "status", check=False).returncode != 0:
        print("gh_sync: gh not authenticated; skipping GitHub mirror")
        return
    data = S.load()
    ensure_label("hw", "0e8a16")
    existing = json.loads(gh("issue", "list", "--label", "hw", "--state", "all", "--limit", "500",
                             "--json", "number,title,state").stdout or "[]")
    by_title = {i["title"]: i for i in existing}
    for m in data["order"]:
        ensure_label(f"module:{m}", "1d76db")
        for s in data["stages"]:
            ensure_label(f"stage:{s}", "5319e7")
            st = data["modules"][m]["stages"][s]
            title = f"[hw][{m}] {s.upper()}"
            body = body_for(st)
            want_closed = st["state"] == "done"
            issue = by_title.get(title)
            if issue is None:
                out = gh("issue", "create", "--title", title, "--body", body,
                         "--label", f"hw,module:{m},stage:{s}").stdout.strip()
                number = out.rsplit("/", 1)[-1]
            else:
                number = str(issue["number"])
                gh("issue", "edit", number, "--body", body, check=False)
            is_closed = (issue or {}).get("state") == "CLOSED"
            if want_closed and not is_closed:
                gh("issue", "close", number, check=False)
            elif not want_closed and is_closed:
                gh("issue", "reopen", number, check=False)
    print("gh_sync: mirrored")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never break the hook chain
        print(f"gh_sync: skipped ({e})")
