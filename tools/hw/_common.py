"""Shared helpers for tools/hw/*_hook.py. Hooks must never crash a session."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
HW = ROOT / "hw"


def payload() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def rel(path: str) -> str:
    """Path relative to repo root with forward slashes ('' if outside the repo)."""
    if not path:
        return ""
    p = pathlib.Path(path)
    if not p.is_absolute():
        p = ROOT / p
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return ""


def file_path(p: dict) -> str:
    ti = p.get("tool_input") or {}
    tr = p.get("tool_response") or {}
    return ti.get("file_path") or ti.get("notebook_path") or (tr.get("filePath") if isinstance(tr, dict) else "") or ""
