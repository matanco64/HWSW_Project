# Build verification log

One row per prompt executed by the desktop agent (step 5 of `../STRATEGY.md`). Filled in by the
verifying Claude Code session, never by the desktop agent.

Protocol per slide:
1. The desktop agent runs `prompts/<id>_*.md` and replies with a screenshot and a STATUS block
   (format in `prompts/README_AGENT.md`). The human pastes the STATUS block into `verify/<id>.status`.
   After 00a the human also saves the `deck_url` line to `presentation/SLIDES_URL.txt`.
2. The verifier runs `python3 tools/presentation/check_status.py presentation/verify/<id>.status`,
   which diffs the block against `deck.md` (title_as_typed, body kind, position, tracker stage,
   notes opening words, gemini_used, deviations, slide_url), and then reads the Slides file back through the Google
   Drive connector to confirm the title and speaker notes appear verbatim and in the right order.
3. The verifier views the screenshot: visual present, no overflow, tracker highlights the stage.
4. A deviation is fixed by re-issuing the same prompt (or a one-line correction prompt), never by
   editing `deck.md` to match what the agent produced.

Screenshots are saved here as `<id>.png` (git-ignored); STATUS blocks as `<id>.status` (committed). The table below is committed.

| id | status block | text diff | screenshot | date | note |
|---|---|---|---|---|---|
| 00a | | | | | |
| 00b | | | | | |
| 00c | | | | | |
