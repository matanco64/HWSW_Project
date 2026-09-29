# OVERNIGHT: finish the deck autonomously

You are finishing a Google Slides deck while the human sleeps. Nobody will answer questions until
morning. Work through the tasks below in order, verify your own work with the checklist, record
what you could not do, and never stop to ask. Everything you need is in this folder
(`C:\Users\Kogan\HWSW_presentation\prompts`) and its `fix\` subfolder; the figures are in
`..\assets`. `README_AGENT.md` still applies in full.

## Step 0: ask for everything once, then never again

Before touching the deck, send the human ONE message listing what you need, wait for a single
"go", and then do not ask anything until the final report. Ask for:

1. Browser control and computer use pre-approved for this whole conversation, for the Chrome
   profile signed into yuval.kogan@campus.technion.ac.il, including opening, reloading and closing
   tabs, and opening `chrome://downloads`.
2. Site permission for `docs.google.com` and `drive.google.com`, granted "always" rather than per
   action.
3. The folder `C:\Users\Kogan\HWSW_presentation` attached to this session, so you can read
   `prompts\` and upload from `assets\`.
4. Chrome Downloads set to save automatically to the Downloads folder, with "Ask where to save each
   file" OFF. The plain-text export downloads fine; the .pptx one has been held as a .tmp file,
   probably by Chrome's download scanning. Ask the human whether Safe Browsing is on "Enhanced
   protection" (Settings → Privacy and security → Security) and, if so, to switch to "Standard"
   for the night; if they decline, the .txt export is enough.
5. The laptop kept awake: sleep and screen lock disabled for the night, lid open, on mains power.
6. Confirmation that no one will use the mouse or keyboard until the final report.
7. Permission to insert one extra slide, a Section header titled "Backup slides", before B01.

Once you have "go", run a five-minute preflight and record its result in your notes for the final
report: open the deck URL, count the slides (expected 13), then trigger File → Download → Plain Text
(.txt) and check within two minutes whether a file appears in Downloads. The .txt export is the
required readback and is known to work; run it after every task. The .pptx export is a bonus:
attempt it once at the end (T7), do not wait for it, and do not retry.

## The per-slide checklist (the verification cycle)

Run this on every slide you create or fix, immediately after finishing it, by reading the rendered
slide and its Format options, never from memory:

- C1 Layout: the slide uses "Title and body · <stage>" named in its prompt (title slide: "Title
  slide"; the backup divider: "Section header").
- C2 Title: character for character equal to the prompt's title. Re-read it from the slide.
- C3 Title fit: at most three lines; the text does not extend below y = 1.45 in.
- C4 Body: an image at x = 0.4 in, y = 1.6 in, width 9.2 in or height ≤ 3.4 in, aspect kept; or
  a table at x = 0.4 in, y = 1.6 in, width 9.2 in, bottom edge ≤ 5.0 in, every cell present and
  no header word broken mid-word; or, for S00, the five subtitle lines.
- C5 No overlap: nothing crosses y = 5.0 in except the layout's tracker and the slide number;
  nothing overlaps the title box.
- C6 Notes: present, and their first six words equal the prompt's.
- C7 Fonts: everything Roboto; body rows 16 pt, or 14 pt / 12 pt only where the table needed it.
- C8 Clean: the layout's empty body placeholder deleted; no stray shapes, no leftover text boxes,
  no second image.

A slide passes when all eight hold. If one fails, fix it within the rules (position, size, font
size, column widths, layout, deleting strays) and re-run the checklist. You may never change any
word or number of a title, table cell or note; if the text itself cannot be made to fit, leave it
as close as possible and record it as a deviation.

## Tasks, in order, each with its definition of done

**T1 Repairs on the existing 13 slides.**
Run `fix\fix_S05.md`, `fix\fix_S10.md`, `fix\fix_S12.md` (shortened tables). Then on slide 10
(S09) set column widths so "K1 cycles/step" does not break, and on slide 12 (S11) widen the
"vs original" and "Evidence" columns so their cells are one line. Then run the checklist on all
13 slides and fix whatever fails.
Done when: 13 slides, every one passes C1–C8.

**T2 Batch S13–S20.** Run `batch_S13-S20.md` exactly, checklist after each slide.
Done when: the deck has 21 slides and slides 14–21 pass C1–C8.

**T3 Batch S21–S26.** Run `batch_S21-S26.md`. Slide 22 (S21) carries an animated GIF; insert it
like any image, it only has to display its first frame in edit view.
Done when: 27 slides, slides 22–27 pass.

**T4 Backup divider and B01–B06.** Insert a new slide after slide 27 with the "Section header"
layout, title exactly `Backup slides`, no body, no notes. Then run `batch_B01-B06.md`; the backup
slides go after the divider, in order.
Done when: 34 slides, slide 28 is the divider, slides 29–34 pass.

**T5 Batch B07–B12.** Run `batch_B07-B12.md`.
Done when: 40 slides, slides 35–40 pass.

**T6 Full verification pass.** Walk slides 1 to 40 and run the checklist on each, including the
ones built earlier tonight. Also confirm: exactly 40 slides; slides 2–27 use the five stage layouts
in the order Analyze (2–3), Profile (4), Optimize (5–7), Accelerate (8–10), Trade-offs (11–13),
Analyze (14–15), Profile (16), Optimize (17–18), Accelerate (19–22), Trade-offs (23–27); no slide
carries a transition; the slide number shows on every slide but the first.
Done when: the checklist table in your final report has a pass mark for every slide, or a named
deviation.

**T7 Evidence and report.** File → Download → Plain Text (.txt), then one attempt at .pptx;
leave both in Downloads. Take grid-view screenshots (View → Grid view) that together show all 40 slides. Then
write the final report and stop.

## If something breaks

- A slide cannot be completed: leave it as far as you got, mark it `blocked` in the report, and
  continue with the next slide. Never delete a slide except a stray one you created by mistake.
- The tab or extension drops: reopen the deck URL in a new tab, count the slides to find where you
  were, and continue. Do not rebuild slides that already exist.
- A dialog you cannot drive appears: press Escape, record it, and continue.
- Gemini's "Enhance" chip or any redesign suggestion: never click it; if opened by accident, cancel
  before it changes anything and re-run the checklist on that slide.
- You are unsure whether an action changes text: don't do it.

## Final report (your last message; the human reads it in the morning)

1. Preflight result: slide count found, exports working or not, anything odd.
2. A table with one row per slide 1–40: `pos | id | layout stage | title ok | body (image name or
   table RxC, size, bottom y) | notes ok | font pt | deviations`.
3. Blocked items and exactly what the human must do about each.
4. `STATUS RB` block for the final export attempt, and the names of the files in Downloads if any.
5. Anything you changed that a prompt did not ask for.
