#!/usr/bin/env python3
"""Render hw/STATUS.json -> hw/PROGRESS.md (generated; never hand-edit). Idempotent."""

import datetime
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import status as S  # noqa: E402

OUT = S.HW / "PROGRESS.md"
EMOJI = {"todo": "⬜", "in_progress": "🔵", "review": "🟠", "done": "✅", "blocked": "⛔"}
COLOR = {"todo": "fill:#e0e0e0,stroke:#9e9e9e,color:#333",
         "in_progress": "fill:#bbdefb,stroke:#1976d2,color:#0d47a1",
         "review": "fill:#ffe0b2,stroke:#f57c00,color:#e65100",
         "done": "fill:#c8e6c9,stroke:#388e3c,color:#1b5e20",
         "blocked": "fill:#ffcdd2,stroke:#d32f2f,color:#b71c1c"}
LABEL = {"prd": "PRD", "mas": "MAS", "uarch": "uArch", "rtl": "RTL", "dv_testplan": "DV testplan",
         "dv_bringup": "DV bring-up", "dv_coverage": "DV coverage", "dv_signoff": "DV sign-off",
         "ppa": "PPA", "integration": "Integration"}


def mermaid(module: str, stages: dict, order: list) -> str:
    lines = ["```mermaid", "flowchart LR"]
    for s in order:
        label = LABEL.get(s, s)
        # checkpoints (human approval) get a hexagon; other stages a rounded box
        node = f"{s}{{{{{label}}}}}" if s in S.CHECKPOINTS else f"{s}({label})"
        lines.append(f"    {node}")
    lines.append("    " + " --> ".join(order))
    for st, style in COLOR.items():
        lines.append(f"    classDef {st} {style}")
    for st in COLOR:
        members = [s for s in order if stages[s]["state"] == st]
        if members:
            lines.append(f"    class {','.join(members)} {st}")
    lines.append("```")
    return "\n".join(lines)


def render(data: dict) -> str:
    order = data["stages"]
    mods = data["order"]
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out = ["# Hardware-flow progress",
           "",
           f"<!-- GENERATED from hw/STATUS.json by tools/hw/render_progress.py at {ts}. "
           "Do not edit; update via tools/hw/status.py. -->",
           f"_Generated {ts} from `hw/STATUS.json` — **do not edit**; see `hw/FLOW.md`._",
           ""]

    out.append("## Stage flow")
    out.append("")
    for m in mods:
        out.append(f"### `{m}`")
        out.append("")
        out.append(mermaid(m, data["modules"][m]["stages"], order))
        out.append("")
    out.append("Hexagon = checkpoint (human approval). Colours: grey todo, blue in progress, "
               "orange review, green done, red blocked.")
    out.append("")

    out.append("## Module × stage")
    out.append("")
    out.append("| Module | " + " | ".join(LABEL.get(s, s) for s in order) + " |")
    out.append("|---|" + "---|" * len(order))
    for m in mods:
        cells = [EMOJI[data["modules"][m]["stages"][s]["state"]] for s in order]
        out.append(f"| `{m}` | " + " | ".join(cells) + " |")
    out.append("")
    out.append("⬜ todo · 🔵 in_progress · 🟠 review · ✅ done · ⛔ blocked")
    out.append("")

    out.append("## Next up")
    out.append("")
    for m in mods:
        s, st, cp = S.next_stage(data, m)
        if s is None:
            out.append(f"- `{m}`: all stages done")
        else:
            tag = " (checkpoint — needs human approval)" if cp else ""
            out.append(f"- `{m}`: **{LABEL.get(s, s)}** — {st}{tag}")
    out.append("")

    out.append("## Gates")
    out.append("")
    for m in mods:
        out.append(f"### `{m}`")
        out.append("")
        any_stage = False
        for s in order:
            st = data["modules"][m]["stages"][s]
            if st["state"] == "todo":
                continue
            any_stage = True
            span = f" (started {st['started']}" + (f", finished {st['finished']}" if st.get("finished") else "") + ")" if st.get("started") else ""
            out.append(f"#### {LABEL.get(s, s)} — {EMOJI[st['state']]} {st['state']}{span}")
            if st.get("reason"):
                out.append(f"> {st['reason']}")
            out.append("")
            for crit, g in st["gate"].items():
                box = "[x]" if g.get("result") == "pass" else "[ ]"
                mark = " ⛔" if g.get("result") == "fail" else ""
                ev = g.get("evidence") or ""
                out.append(f"- {box} {crit}{mark}" + (f" — {ev}" if ev else ""))
            out.append("")
        if not any_stage:
            out.append("_No stage started yet._")
            out.append("")

    out.append("## Metrics")
    out.append("")
    out.append("| Module | Line cov % | Toggle cov % | Func cov % | Tests (pass/run) | Formal | Cells | Area µm² | Fmax MHz | Power mW |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    for m in mods:
        dv = data["modules"][m]["metrics"]["dv"]
        ppa = data["modules"][m]["metrics"]["ppa"]
        out.append(f"| `{m}` | {dv.get('line_cov', 0)} | {dv.get('toggle_cov', 0)} | {dv.get('func_cov', 0)} | "
                   f"{dv.get('tests_pass', 0)}/{dv.get('tests_run', 0)} | {dv.get('formal', 'n/a')} | "
                   f"{ppa.get('cells', 0)} | {ppa.get('area_um2', 0)} | {ppa.get('fmax_mhz', 0)} | {ppa.get('power_mw', 0)} |")
    out.append("")
    return "\n".join(out)


def main() -> None:
    data = S.load()
    OUT.write_text(render(data), encoding="utf-8")
    print(f"wrote {OUT.relative_to(S.ROOT)}")


if __name__ == "__main__":
    main()
