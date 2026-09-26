# Build verification log

One row per prompt executed by the desktop agent (step 5 of `../STRATEGY.md`). Filled in by the
verifying Claude Code session, never by the desktop agent.

Protocol per slide:
1. The desktop agent runs `prompts/<id>_*.md` and replies with a screenshot and a STATUS block
   (format in `prompts/README_AGENT.md`). The human pastes the STATUS block into `verify/<id>.status`.
   After 00a the human also saves the `deck_url` line to `presentation/SLIDES_URL.txt`.
2. The verifier runs `python3 tools/presentation/check_status.py presentation/verify/<id>.status`,
   which diffs the block against `deck.md` (title_as_typed, body kind, position, tracker stage,
   notes opening words, gemini_used, deviations, slide_url). Then the text readback: preferred, the
   Slides file read through the Google Drive connector (needs the deck's Google account connected);
   fallback, the agent runs `prompts/RB_export.md` (File → Download → Plain text into this folder) and
   the verifier runs `python3 tools/presentation/check_export.py presentation/verify/deck_export.txt --through <id>`,
   which confirms titles verbatim and in order, notes present, and table cells present.
3. The verifier views the screenshot: visual present, no overflow, tracker highlights the stage.
4. A deviation is fixed by re-issuing the same prompt (or a one-line correction prompt), never by
   editing `deck.md` to match what the agent produced.

Screenshots are saved here as `<id>.png`/`.jpg` (git-ignored); STATUS blocks as `<id>.status` (committed); the latest plain-text export as `deck_export.txt` (committed, overwritten each readback). The table below is committed.

| id | status block | text diff | screenshot | date | note |
|---|---|---|---|---|---|
| 00a | done-with-deviation; 4 deviations reviewed, all accepted (four layouts correct; pre-created deck renamed; title box 1.3 in; slide 1 temporarily Title-and-body) | not possible yet: deck is on the Technion account, not visible to the verifier's Drive | theme builder + blank slide viewed: four layouts, dark title, body placeholder, # bottom-right | 2026-09-26 | fonts and transitions not visible in screenshots; 00b status asked to report fonts |
| 00b | | | | | |
| 00c | | | | | |
