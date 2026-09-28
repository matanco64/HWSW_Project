# Build verification log

One row per prompt executed by the desktop agent (step 5 of `../STRATEGY.md`). Filled in by the
verifying Claude Code session, never by the desktop agent.

Protocol per slide:
1. The desktop agent runs `prompts/<id>_*.md` and replies with a screenshot and a STATUS block as
   text (format in `prompts/README_AGENT.md`). The human pastes the STATUS text into the message to
   the verifier, who saves it as `verify/<id>.status`. Exports land in Windows Downloads; the human
   moves them to this folder as `deck_export.pptx` / `deck_export.txt`.
   After 00a the human also saves the `deck_url` line to `presentation/SLIDES_URL.txt`.
2. The verifier runs `python3 tools/presentation/check_status.py presentation/verify/<id>.status`,
   which diffs the block against `deck.md` (title_as_typed, body kind, position, tracker stage,
   notes opening words, gemini_used, deviations, slide_url). Then the text readback: preferred, the
   Slides file read through the Google Drive connector (needs the deck's Google account connected);
   the deck's Google account cannot be connected (Technion Workspace policy), so the readback is the
   agent running `prompts/RB_export.md` (File → Download → .pptx and .txt into this folder) and the
   verifier running `python3 tools/presentation/check_pptx.py presentation/verify/deck_export.pptx --through <id>`,
   which checks per slide: title verbatim, picture present or table cells present, notes opening words,
   footer tracker, and fonts. `check_export.py` does the same on the .txt as a cross-check.
3. The verifier views the screenshot: visual present, no overflow, tracker highlights the stage.
4. A deviation is fixed by re-issuing the same prompt (or a one-line correction prompt), never by
   editing `deck.md` to match what the agent produced.

Screenshots are saved here as `<id>.png`/`.jpg` (git-ignored); STATUS blocks as `<id>.status` (committed); the latest exports as `deck_export.pptx` / `deck_export.txt` (git-ignored, overwritten each readback). The table below is committed.

| id | status block | text diff | screenshot | date | note |
|---|---|---|---|---|---|
| 00a | done-with-deviation; 4 deviations reviewed, all accepted (four layouts correct; pre-created deck renamed; title box 1.3 in; slide 1 temporarily Title-and-body) | not possible yet: deck is on the Technion account, not visible to the verifier's Drive | theme builder + blank slide viewed: four layouts, dark title, body placeholder, # bottom-right | 2026-09-26 | fonts and transitions not visible in screenshots; 00b status asked to report fonts |
| 00b | done; fonts reported Roboto/Roboto | pptx: tracker text on TITLE_AND_BODY and SECTION_HEADER layouts, Roboto on both, slide-number placeholder present | blank slide shows grey tracker + slide number 1 | 2026-09-26 | readback RB: agent blocked on Chrome's Save dialog, files moved by hand from Downloads; procedure updated |
| 00c | first attempt blocked (WSL path); done after the Windows mirror: 16 files, none missing | n/a | n/a | 2026-09-26 | assets now served from C:\Users\Kogan\HWSW_presentation |
| 00d | done-with-deviation: eight layouts named exactly as specified; slide 1 back to Title slide (wanted) | pending: highlighted word per stage layout to be confirmed from the batch-1 pptx | not saved to verify | 2026-09-26 | layout fix would propagate to all slides, so batch 1 not blocked |
| S00 | done-with-deviation (subtitle box enlarged; accidental Gemini chip click cancelled) | no export yet (RB blocked: extension disconnected) | title + 5 lines + notes correct; title slide layout | 2026-09-28 | accepted |
| S01 | done-with-deviation (3-line title; table font forced to Roboto; autocorrect off) | no export yet | table 4x3 correct, tracker Analyze | 2026-09-28 | accepted; 3-line title fixed by 00e |
| S02 | done-with-deviation (image 5.70 x 3.20 in) | no export yet | figure far too small: padded 16:9 PNG shrunk to half width | 2026-09-28 | REDO via fix_S02 after 00e; asset re-rendered without padding |
| S03 | done-with-deviation (image 5.70 x 3.20 in) | no export yet | three stacked panels unreadable | 2026-09-28 | REDO via fix_S03 with print_nbody_stock_slide.png (overview + panel 1) |
| S04 | done-with-deviation (3-line title; image 5.34 x 3.00 in) | no export yet | figure unreadable | 2026-09-28 | REDO via fix_S04 with print_nbody_opt_slide.png |
| RB-1 | blocked: Chrome extension not connected | — | — | 2026-09-28 | re-run after the fixes |
