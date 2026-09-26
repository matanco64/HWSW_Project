# Setup 1 of 3: theme and master

Create a new Google Slides presentation (File → New presentation), name it
"HWSW project — nbody & pyflate", 16:9. Copy its URL: it goes in the STATUS block, and the human
will save it to `presentation/SLIDES_URL.txt`. Every later prompt uses that same file.

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
slide, then the STATUS block for 00a with `deck_url` filled in, `position: 1 of 1`, and under
`deviations` the list of layouts that remain (must be exactly the four named above).
