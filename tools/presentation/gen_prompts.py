#!/usr/bin/env python3
"""Render presentation/prompts/ from presentation/deck.md.

One file per slide plus three setup prompts. Each prompt is self-contained and small enough
for a desktop agent driving Google Slides to execute without further context.
Re-running on an unchanged deck produces no diff.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deckspec import Slide, parse  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PRES = ROOT / "presentation"
OUT = PRES / "prompts"
STAGES = ["Analyze", "Profile", "Optimize", "Accelerate", "Trade-offs"]
ASSETS_WIN = r"\\wsl.localhost\Ubuntu\home\yuvalk\HWSW\HWSW_Proj\presentation\assets"

BRIEFING = f"""# Standing briefing for the slide-building agent

You are building a Google Slides deck for a Technion course presentation from a numbered queue of
prompts in this folder. Read this once; every prompt assumes it.

1. **Exactness.** Titles, table cells and speaker notes are quoted from a verified spec. Type them
   exactly as given: no rewording, no "improvements", no added bullets, no extra slides, no
   changed numbers. If something cannot be done as written, stop and say so instead of adapting.
2. **One prompt, one result.** Do only what the prompt says. Do not touch other slides. If you
   notice a problem elsewhere, report it; do not fix it.
3. **Images** are on this laptop at `{ASSETS_WIN}` (a WSL path). Insert via Insert → Image →
   Upload from computer. Never search the web for a figure or generate one.
4. **Gemini in Slides.** You may use the Gemini side panel inside Google Slides for mechanical
   formatting work (resize all tables, apply the theme, align boxes) when it is faster than menus.
   You may not let it write, summarize or "polish" any text, and you must check afterwards that
   nothing it touched changed the words or numbers. Never use it to create slides or images.
5. **Screenshots.** Every prompt ends with a screenshot request. Take it in edit view showing the
   whole slide and the notes pane if notes were set. The human saves it as `verify/<prompt id>.png`.
6. **Look.** Theme "Simple Light", font Roboto, accent #1F4E79, no transitions, no animations,
   no logos, no clip art. Footer tracker on every content slide as the setup prompt defines it.
7. **Order.** Run `INDEX.md` top to bottom: the three setup prompts first, then slides in the
   listed order, five at a time, pausing for verification after each batch when asked.
"""

SETUP = {
    "00a_theme.md": f"""# Setup 1 of 3: theme and master

Open the Google Slides file named in `presentation/SLIDES_URL.txt` (create it if missing:
File → New presentation, name "HWSW project — nbody & pyflate", 16:9).

1. Theme: keep the default "Simple Light". Set the theme font pair to Roboto (titles) and
   Roboto (body). Accent colour: #1F4E79 for title text and table header fill. No other colours.
2. Edit the master (View → Theme builder). On the TITLE AND BODY layout: title box across the
   top, 32 pt, left-aligned, dark grey #222222, allow two lines. One body box below it filling
   the remaining area with 0.4 in margins. Remove the slide-number placeholder from the body
   area; keep it bottom-right, 10 pt.
3. Delete every layout except: Title slide, Title and body, Section header, Blank.
4. Turn off all transitions (Slide → Transition → None, apply to all).

Done when: the master has the four layouts, Roboto fonts, the accent colour on titles, and no
transitions. Reply with a screenshot of the theme builder and one of a blank "Title and body"
slide.
""",
    "00b_footer.md": f"""# Setup 2 of 3: footer tracker

Still in the theme builder, on the TITLE AND BODY layout and on the SECTION HEADER layout, add
a footer text box across the bottom (0.3 in from the bottom edge, full width minus margins),
10 pt Roboto, medium grey #888888, centred, with this exact text:

    {"   ·   ".join(STAGES)}

This is the project-flow tracker. On each real slide the current stage word will be made bold
and coloured #1F4E79; on the master it stays plain grey. Do not add a logo or a date.

Done when: every new "Title and body" slide shows the grey tracker line at the bottom and the
slide number bottom-right. Reply with a screenshot of one blank slide.
""",
    "00c_images.md": f"""# Setup 3 of 3: images

The figures live on this laptop at:

    {ASSETS_WIN}

(Windows path into WSL. If Explorer cannot open it, use the path printed by `wslpath -w
presentation/assets` in the WSL terminal.)

Do nothing with them yet except confirm the folder opens and lists PNG/GIF files. Each slide
prompt names the exact file to insert via Insert → Image → Upload from computer.

Done when: you can see the folder listing. Reply with a screenshot of the folder in the file
picker.
""",
}


def slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:48].rstrip("-")


def footer(stage: str) -> str:
    return "   ·   ".join(f"**{x}**" if x == stage else x for x in STAGES)


def render(s: Slide, idx: int, total: int, prev_id: str | None) -> str:
    stage = s.fields.get("stage", "Trade-offs")
    visual = s.fields.get("visual", "")
    where = "at the end of the deck (backup section)" if s.is_backup else (
        f"after slide {prev_id}" if prev_id else "as the first slide")
    if visual == "title":
        rows = [r for r in s.table.splitlines()[2:] if r.startswith("|")]
        lines = [c.split("|")[2].strip() for c in rows]
        return f"""# Slide {s.id} (title slide)

Layout: "Title slide". This is the first slide of the deck.

Title (exact text): 

    {s.title}

Subtitle box, one line each, exactly:

    {(chr(10) + '    ').join(lines)}

No footer tracker on this slide. No images. Speaker notes (exact text):

    {s.notes}

Done when: title and the five lines match exactly and nothing overflows. Reply with a screenshot.
"""
    if visual.startswith("assets/"):
        body = (f"Body: Insert → Image → Upload from computer → `{ASSETS_WIN}\\{visual.split('/', 1)[1]}`.\n"
                "Fit it inside the body box, keep aspect ratio, centre it. No caption, no border.")
    elif visual == "table" and s.table:
        body = ("Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and "
                "white text, body rows 16 pt, columns auto-fit, no other formatting:\n\n" + s.table)
    else:
        body = f"Body: {visual}"
    notes = s.notes or "(none)"
    section = "BACKUP" if s.is_backup else f"{idx} of {total}"
    return f"""# Slide {s.id} ({section})

Layout: "Title and body". Insert {where}.

Title (exact text, do not shorten or rephrase):

    {s.title}

{body}

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    {footer(stage)}

Speaker notes (exact text, paste into the notes pane):

    {notes.replace(chr(10), chr(10) + '    ')}

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "{stage}", and the notes are saved. Reply with a screenshot of
the slide in edit view.
"""


def main() -> int:
    slides = parse(PRES / "deck.md")
    if not slides:
        print("no slides in deck.md")
        return 1
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    (OUT / "README_AGENT.md").write_text(BRIEFING, encoding="utf-8")
    for name, text in SETUP.items():
        (OUT / name).write_text(text, encoding="utf-8")
    main_slides = [s for s in slides if not s.is_backup]
    index = ["# Prompt queue", "", "Give the agent `README_AGENT.md` first, then run in this order, one prompt per message.", ""]
    for name in SETUP:
        index.append(f"- [ ] `{name}`")
    prev = None
    for i, s in enumerate(slides, 1):
        idx = main_slides.index(s) + 1 if s in main_slides else 0
        fname = f"{s.id}_{slug(s.title)}.md"
        (OUT / fname).write_text(render(s, idx, len(main_slides), prev), encoding="utf-8")
        index.append(f"- [ ] `{fname}` ({s.fields.get('owner', '?')}, {s.fields.get('seconds', '-')} s)")
        prev = s.id
    (OUT / "INDEX.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    print(f"wrote {len(slides)} slide prompts + {len(SETUP)} setup prompts to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
