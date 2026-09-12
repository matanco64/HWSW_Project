#!/bin/sh
# Run a repo Python script with whatever Python is called on this machine.
#
# Why this exists: every hook in .claude/settings.json used to invoke `python3`
# directly. On Windows that name resolves to the Microsoft Store stub, which
# prints "Python was not found" and exits non-zero -- and because the hooks were
# wired as `python3 ... 2>/dev/null || true`, they silently did nothing there.
# The casualty was prompt.txt: the course requires a log of every AI prompt
# (§10), and not one prompt sent from the Windows machine was being recorded.
# The failure was invisible precisely because the `|| true` was doing its job.
#
# `command -v python3` is not enough to detect this -- the Store stub *is* on
# PATH. The interpreter has to actually be run.
set -eu

if python3 -c "" >/dev/null 2>&1; then
    PY=python3
elif python -c "" >/dev/null 2>&1; then
    PY=python
else
    # No usable interpreter. Exit 0 so a missing Python cannot block edits;
    # the hooks that matter for correctness re-check on the machines that run
    # them (the VM and WSL both have python3).
    exit 0
fi

exec "$PY" "$@"
