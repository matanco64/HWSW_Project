# Build verification log

One row per prompt executed by the desktop agent (step 5 of `../STRATEGY.md`). Filled in by the
verifying Claude Code session, never by the desktop agent.

Protocol per slide:
1. The desktop agent runs `prompts/<id>_*.md` and replies with a screenshot.
2. The verifier reads the Slides file back through the Google Drive connector and checks that the
   slide's title and speaker notes from `deck.md` appear verbatim (text diff).
3. The verifier views the screenshot: visual present, no overflow, tracker highlights the stage.
4. A deviation is fixed by re-issuing the same prompt (or a one-line correction prompt), never by
   editing `deck.md` to match what the agent produced.

Screenshots are saved here as `<id>.png` (git-ignored). The table below is committed.

| id | text diff | screenshot | date | note |
|---|---|---|---|---|
| 00a | | | | |
| 00b | | | | |
| 00c | | | | |
