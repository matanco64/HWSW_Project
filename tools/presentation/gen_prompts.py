#!/usr/bin/env python3
"""Render presentation/prompts/ from presentation/deck.md.

One file per slide plus four setup prompts. Each prompt is self-contained and small enough
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
VERIFY_WIN = r"C:\Users\Kogan\HWSW_presentation\verify"
ASSET_NAMES = sorted(p.name for p in (PRES / "assets").glob("*") if p.suffix in (".png", ".gif"))
ASSETS_WIN = r"C:\Users\Kogan\HWSW_presentation\assets"   # mirror kept by tools/presentation/sync_win.sh

BRIEFING = f"""# Standing briefing for the slide-building agent

You are building a Google Slides deck for a Technion course presentation from a numbered queue of
prompts in this folder. Read this once; every prompt assumes it.

1. **Exactness.** Titles, table cells and speaker notes are quoted from a verified spec. Type them
   exactly as given: no rewording, no "improvements", no added bullets, no extra slides, no
   changed numbers. If something cannot be done as written, stop and say so instead of adapting.
2. **One prompt, one result.** Do only what the prompt says. Do not touch other slides. If you
   notice a problem elsewhere, report it; do not fix it.
3. **Images** are on this laptop at `{ASSETS_WIN}`, a folder attached to your session. Insert them
   with your direct file-upload tool into the Slides image-upload input (Insert → Image → Upload
   from computer opens a native picker you cannot drive). Never search the web for a figure or
   generate one.
4. **Gemini in Slides.** You may use the Gemini side panel inside Google Slides for mechanical
   formatting work (resize all tables, apply the theme, align boxes) when it is faster than menus.
   You may not let it write, summarize or "polish" any text, and you must check afterwards that
   nothing it touched changed the words or numbers. Never use it to create slides or images.
5. **Screenshots.** Every prompt ends with a screenshot request. Take it in edit view showing the
   whole slide and the notes pane if notes were set. The human saves it as `<prompt id>.png` in
   `{VERIFY_WIN}`.
6. **Look.** Theme "Simple Light", font Roboto, accent #1F4E79, no transitions, no animations,
   no logos, no clip art. Footer tracker on every content slide as the setup prompt defines it.
7. **Order.** Run `INDEX.md` top to bottom: the four setup prompts first, then slides in the
   listed order, five at a time, pausing for verification after each batch when asked.
8. **STATUS as text.** Write the STATUS block as plain text in your reply (not as an image), so
   the human can copy it. **Export on request.** When asked for a readback, follow `RB_export.md`: download the deck as
   .pptx (and .txt). Chrome saves to the Downloads folder; you cannot drive the native Save
   dialog, so leave the files there and say so in the STATUS block. A sync script collects them. Never edit slides during a readback.
9. **STATUS block.** Every prompt ends with a STATUS block. Fill it in completely, in this exact
   shape, as the last thing in your reply. A verifier on the other side diffs it against the spec
   and against the deck read back through the Drive API; a missing or paraphrased field counts as
   a failure, and "title_as_typed" must be copied from the slide, not from the prompt.

    STATUS <prompt id>
    result: done | done-with-deviation | blocked
    deck_url: <full URL of the presentation>
    slide_url: <URL with #slide=id.… while this slide is selected> | n/a
    position: <index> of <total slides now in the deck> | n/a
    title_as_typed: "<copied from the slide>" | n/a
    body: image <file name> | table <rows>x<cols> | title-lines <n> | n/a
    notes_set: yes (<first six words>) | no | n/a
    tracker: <stage> via layout | none | n/a
    gemini_used: no | yes: <what for>
    deviations: none | <one line each>
    screenshot: taken | not taken: <why>
"""

READBACK = f"""# Readback: export the deck as plain text

Run this whenever a prompt or the human asks for a readback (normally after every batch of five
slides, and after each setup prompt if asked).

1. In the deck: File → Download → Microsoft PowerPoint (.pptx).
2. Then File → Download → Plain Text (.txt). Both land in the Windows Downloads folder; if
   Chrome asks, answer Keep. Do not try to drive the Save dialog; leave them in Downloads, a sync
   script on the WSL side collects the newest export.
3. Reply with this block only:

    STATUS RB
    result: done | blocked
    deck_url: <URL>
    slide_url: n/a
    position: <total slides now in the deck> of <same>
    title_as_typed: n/a
    body: n/a
    notes_set: n/a
    tracker: n/a
    gemini_used: no
    deviations: the two file names as saved in Downloads | <anything unusual>
    screenshot: not taken: readback only

Do not edit the export and do not edit any slide during a readback.
"""

STAGE_LAYOUTS = "\n".join(f'    "Title and body · {s}"' for s in STAGES)
SETUP = {
    "00a_theme.md": f"""# Setup 1 of 4: theme and master

Create a new Google Slides presentation (File → New presentation), name it
"HWSW project — nbody & pyflate", 16:9. Copy its URL: it goes in the STATUS block, and the human
will save it to `presentation/SLIDES_URL.txt`. Every later prompt uses that same file.

1. Theme: keep the default "Simple Light". Set the theme font pair to Roboto (titles) and
   Roboto (body). Titles and body text dark grey #222222. The accent colour #1F4E79 is used
   only for table header fills and the highlighted word in the footer tracker. No other colours.
2. Edit the master (View → Theme builder). On the TITLE AND BODY layout: title box across the
   top, 32 pt, left-aligned, dark grey #222222, allow two lines. One body box below it filling
   the remaining area with 0.4 in margins. Remove the slide-number placeholder from the body
   area; keep it bottom-right, 10 pt.
3. Delete every layout except: Title slide, Title and body, Section header, Blank.
4. Turn off all transitions (Slide → Transition → None, apply to all).

Done when: the master has the four layouts, Roboto fonts, the accent colour on titles, and no
transitions. Reply with a screenshot of the theme builder and one of a blank "Title and body"
slide, then the STATUS block for 00a with `deck_url` filled in, `position: 1 of 1`, and under
`deviations` the list of layouts that remain (must be exactly the four named above).
""",
    "00b_footer.md": f"""# Setup 2 of 4: footer tracker

Still in the theme builder, on the TITLE AND BODY layout and on the SECTION HEADER layout, add
a footer text box across the bottom (0.3 in from the bottom edge, full width minus margins),
10 pt Roboto, medium grey #888888, centred, with this exact text:

    {"   ·   ".join(STAGES)}

This is the project-flow tracker. On the master it stays plain grey; setup prompt 00d
makes one layout copy per stage with that stage's word highlighted. Do not add a logo or a date.

Then turn slide numbers on for the deck (Insert → Slide numbers → On, apply to all).

Done when: every new "Title and body" slide shows the grey tracker line at the bottom and the
slide number bottom-right. Reply with a screenshot of one blank slide, then the STATUS block for
00b with `tracker: none highlighted`, `title_as_typed` set to the tracker text as it reads on the
master, and under `deviations` the title and body font names the theme currently uses
(Slide → Edit theme → click the title box → font menu), even if they are Roboto as requested.
""",
    "00d_stage_layouts.md": f"""# Setup 4 of 4: one layout per tracker stage

The footer tracker lives on the layout, so the current stage is chosen by picking a layout, never by
editing text on a slide. Create five copies of the "Title and body" layout, one per stage.

1. View → Theme builder. Right-click the "Title and body" layout → Duplicate layout. Repeat until
   there are five copies. Rename them (Rename button at the top of the editor) exactly:

{STAGE_LAYOUTS}

2. In each copy, edit only the footer tracker text box: make the layout's own stage word bold and
   coloured #1F4E79; leave the other four words plain grey #888888. Nothing else changes.
3. Delete the original unrenamed "Title and body" layout, so the layouts are exactly: Title slide,
   Section header, Blank, and the five above (eight in total).
4. Close the theme builder.

Done when: Slide → Apply layout lists the eight layouts, and each stage layout shows its own word
highlighted. Reply with one screenshot of the layout picker showing all eight, then the STATUS block
for 00d with `deviations` listing the eight layout names as they appear.
""",
    "00e_title_size.md": f"""# Setup correction 00e: two-line titles, full-width figures

Batch 1 showed that claim titles wrap to three lines at 32 pt on the 10 x 5.63 in page and leave
too little room for the figure. Fix it once, on the layouts, so every slide inherits it.

1. View → Theme builder. On EACH of the five "Title and body · <stage>" layouts and on the
   Section header layout: set the title placeholder to 26 pt, left-aligned, dark grey #222222,
   box from y = 0.25 in to y = 1.35 in (two lines of 26 pt fit; a third must not be needed).
   Turn OFF autofit/shrink on the title box (Format options → Text fitting → Do not autofit).
2. On the same layouts: the body placeholder spans x = 0.4 in to 9.6 in and y = 1.5 in to 5.0 in.
   The footer tracker stays where it is (bottom 0.3 in); the slide number stays bottom-right.
3. Close the theme builder. Check slides 2 to 5: their titles must now be at most two lines. If any
   title still wraps to three lines, report it under deviations with the slide number; do not
   edit the title text.

Done when: the six layouts have the 26 pt two-line title box and the 9.2 x 3.5 in body box, and
slides 2 to 5 show two-line titles. Reply with a screenshot of slide 5 and the STATUS block for 00e,
listing under deviations any slide whose title still needs three lines.
""",
    "00f_three_line_titles.md": f"""# Setup correction 00f: three-line titles at 22 pt

Half of the claim titles need three lines even at 26 pt. Settle it on the layouts once more:

1. View → Theme builder. On EACH "Title and body · <stage>" layout and on Section header: title
   placeholder 22 pt, left-aligned, #222222, box from y = 0.25 in to y = 1.45 in, autofit OFF
   (three lines of 22 pt fit with room to spare).
2. Same layouts: body placeholder from y = 1.6 in to y = 5.0 in, x = 0.4 in to 9.6 in.
3. Close the theme builder. On slides 3, 4 and 5 move the existing image down so its top is at
   y = 1.6 in (keep its size). Nothing else changes.

Done when: slide 5's title fits in its box with no overlap, and slides 3 to 5 show the image
starting at y = 1.6 in. Reply with a screenshot of slide 5 and the STATUS block for 00f.
""",
    "00c_images.md": f"""# Setup 3 of 4: images

The figures live on this laptop at:

    {ASSETS_WIN}

This folder is attached to your session by the human ("Add folder" in the desktop app). Do nothing
with the files yet except list the folder. Each slide prompt names the exact file to insert with
your direct file-upload tool.

Done when: you can list the folder. Reply with the STATUS block for 00c with `deviations` listing the number of files you see and
any of these names that are missing: {", ".join(sorted(ASSET_NAMES))}.
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

Layout: "Title slide". Use the EXISTING slide 1 (set its layout to "Title slide"); do not insert a
new slide. After this prompt the deck still has exactly one slide.

Title (exact text): 

    {s.title}

Subtitle box, one line each, exactly:

    {(chr(10) + '    ').join(lines)}

No footer tracker on this slide. No images. Speaker notes (exact text):

    {s.notes}

Done when: title and the five lines match exactly and nothing overflows. Reply with a screenshot,
then the STATUS block for {s.id} (expected: position 1, body title-lines {len(lines)}, tracker none).
"""
    if visual.startswith("assets/"):
        body = (f"Body: insert the image `{ASSETS_WIN}\\{visual.split('/', 1)[1]}` with your direct upload tool.\n"
                "Size it to fill the body box: width 9.2 in, or height 3.4 in if that binds first, keeping the\n"
                "aspect ratio; place it at x = 0.4 in, y = 1.6 in and centre it horizontally in the body box.\n"
                "It must not overlap the title or the footer tracker. No caption, no border, no crop.")
    elif visual == "table" and s.table:
        body = ("Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and "
                "white text, body rows 16 pt, columns auto-fit, no other formatting:\n\n" + s.table)
    else:
        body = f"Body: {visual}"
    notes = s.notes or "(none)"
    section = "BACKUP" if s.is_backup else f"{idx} of {total}"
    pos = "end of deck" if s.is_backup else str(idx)
    if visual.startswith("assets/"):
        body_kind = f"image {visual.split('/', 1)[1]}"
    elif visual == "table" and s.table:
        rows = [r for r in s.table.splitlines() if r.startswith("|") and not set(r) <= set("|-: ")]
        body_kind = f"table {len(rows)}x{rows[0].count('|') - 1}" if rows else "table"
    else:
        body_kind = visual
    return f"""# Slide {s.id} ({section})

Layout: "Title and body · {stage}" (Slide → Apply layout). Insert {where}.

Title (exact text, do not shorten or rephrase):

    {s.title}

{body}

Do not touch the footer tracker: the layout already highlights "{stage}".

Speaker notes (exact text, paste into the notes pane):

    {notes.replace(chr(10), chr(10) + '    ')}

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · {stage}" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for {s.id} (expected: position {pos}, body {body_kind},
notes_set yes, tracker {stage} via layout).
"""


def expected_body_kind(s: Slide) -> str:
    rows = [r for r in s.table.splitlines() if r.startswith("|") and not set(r) <= set("|-: ")]
    return f"table {len(rows)}x{rows[0].count('|') - 1}" if rows else "table"


def render_fix(s: Slide, pos: int) -> str:
    visual = s.fields.get("visual", "")
    fname = visual.split("/", 1)[1] if visual.startswith("assets/") else ""
    if visual == "table":
        return f"""# Correction for slide {s.id} (deck slide {pos}): replace the table

Go to slide {pos}. Its title and speaker notes are correct; do not touch them. The table was too
tall; the spec table has been shortened. Replace it.

1. Delete the existing table.
2. Insert this table exactly (paste as a styled HTML table is fine): header row bold, fill #1F4E79,
   white text; body rows Roboto 16 pt (14 pt if 16 pt does not fit, 12 pt as the last resort):

{s.table}

3. Table at x = 0.4 in, y = 1.6 in, width 9.2 in; set column widths so that no header word breaks
   mid-word and the longest column gets the most width; bottom edge at or above y = 5.0 in.

Done when: the table's bottom edge is at or above 5.0 in, no cell text is cut, no header wraps
mid-word. Reply with the STATUS block for {s.id} (expected: position {pos}, body {expected_body_kind(s)}).
"""
    return f"""# Correction for slide {s.id} (deck slide {pos})

Go to slide {pos}. Its title and speaker notes are correct; do not touch them. The figure must be
replaced and resized after the 00e layout change.

1. Delete the existing image on the slide.
2. Insert `{ASSETS_WIN}\\{fname}` with your direct upload tool (it is a NEW file, re-upload it).
3. Size it to fill the body box: width 9.2 in, or height 3.4 in if that binds first, keeping the
   aspect ratio; place it at x = 0.4 in, y = 1.6 in and centre it horizontally in the body box.
   It must not overlap the title or the footer tracker. No crop, no border.

Done when: the new figure fills the body box width (or height) and nothing overlaps. Reply with a
screenshot of the slide in edit view, then the STATUS block for {s.id} (expected: position {pos},
body image {fname}, notes_set yes, tracker {s.fields.get('stage', '')} via layout).
"""


def render_batch(batch: list, all_main: list, total: int) -> str:
    first, last = batch[0].id, batch[-1].id
    parts = [f"""# Batch {first}–{last}: build {len(batch)} slides autonomously, then export

Work through the slides below in order without stopping between them. For each slide follow its
block exactly as if it were a single prompt. Do not take a screenshot per slide; instead, at the
end, (1) run the readback export (File → Download → .pptx, then .txt; leave them in Downloads),
(2) take ONE screenshot of the slide-sorter/grid view (View → Grid view) showing all slides, and
(3) reply with one STATUS block per slide, in order, followed by the STATUS RB block.

Rules that apply to every slide in this batch:
- Layout by name ("Title and body · <stage>"); never edit the footer tracker.
- Images: insert the named file from `{ASSETS_WIN}` with your direct upload tool, size to
  width 9.2 in (or height 3.4 in if that binds first), place at x = 0.4 in, y = 1.6 in, centred.
  Delete the layout's empty body placeholder afterwards.
- Tables: header row bold, fill #1F4E79, white text; body 16 pt Roboto (set it, the default is
  Arial); no other formatting. Table at x = 0.4 in, y = 1.6 in, width 9.2 in. Set column widths
  yourself: no header word may break mid-word, and the column with the longest text gets the most
  width. If the table does not fit above y = 5.0 in at 16 pt, use 14 pt, then 12 pt, then reduce
  cell padding; say which under deviations. Never drop, merge or reword cells.
- Titles and notes exactly as written. If a title needs three lines, keep it and report it under
  deviations with the slide id; do not shorten it.
- If a slide cannot be completed, leave it as far as you got, write `result: blocked` in its
  STATUS block, and continue with the next slide.
"""]
    for s in batch:
        idx = all_main.index(s) + 1 if s in all_main else 0
        prev = None
        pos_in_all = [x.id for x in all_main + [y for y in batch if y.is_backup]]
        parts.append("\n---\n\n" + render(s, idx, total, s_prev(s, all_main)))
    parts.append("\n---\n\n" + READBACK)
    return "".join(parts)


def s_prev(s: Slide, all_main: list):
    """id of the slide that precedes s in the deck order (None for the first)."""
    order = [x.id for x in parse(PRES / "deck.md")]
    i = order.index(s.id)
    return order[i - 1] if i > 0 else None


def main() -> int:
    slides = parse(PRES / "deck.md")
    if "--batch" in sys.argv:
        spec = sys.argv[sys.argv.index("--batch") + 1]          # e.g. S05-S09 or B01-B06
        first, last = spec.split("-")
        ids = [s.id for s in slides]
        batch = slides[ids.index(first): ids.index(last) + 1]
        all_main = [s for s in slides if not s.is_backup]
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / f"batch_{first}-{last}.md"
        path.write_text(render_batch(batch, all_main, len(all_main)), encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({len(batch)} slides)")
        return 0
    if "--fix" in sys.argv:
        ids = sys.argv[sys.argv.index("--fix") + 1].split(",")
        main_ids = [s.id for s in slides if not s.is_backup]
        (OUT / "fix").mkdir(parents=True, exist_ok=True)
        for s in slides:
            if s.id in ids:
                (OUT / "fix" / f"fix_{s.id}.md").write_text(render_fix(s, main_ids.index(s.id) + 1), encoding="utf-8")
        print(f"wrote {len(ids)} correction prompts to {OUT.relative_to(ROOT)}/fix")
        return 0
    if not slides:
        print("no slides in deck.md")
        return 1
    if OUT.exists():
        for f in OUT.glob("*.md"):
            if not f.name.startswith("batch_"):
                f.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "README_AGENT.md").write_text(BRIEFING, encoding="utf-8")
    ov = PRES / "src" / "OVERNIGHT.md"
    if ov.exists():
        (OUT / "OVERNIGHT.md").write_text(ov.read_text(encoding="utf-8"), encoding="utf-8")
    (OUT / "RB_export.md").write_text(READBACK, encoding="utf-8")
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
