# Standing briefing for the slide-building agent

You are building a Google Slides deck for a Technion course presentation from a numbered queue of
prompts in this folder. Read this once; every prompt assumes it.

1. **Exactness.** Titles, table cells and speaker notes are quoted from a verified spec. Type them
   exactly as given: no rewording, no "improvements", no added bullets, no extra slides, no
   changed numbers. If something cannot be done as written, stop and say so instead of adapting.
2. **One prompt, one result.** Do only what the prompt says. Do not touch other slides. If you
   notice a problem elsewhere, report it; do not fix it.
3. **Images** are on this laptop at `\\wsl.localhost\Ubuntu\home\yuvalk\HWSW\HWSW_Proj\presentation\assets` (a WSL path). Insert via Insert → Image →
   Upload from computer. Never search the web for a figure or generate one.
4. **Gemini in Slides.** You may use the Gemini side panel inside Google Slides for mechanical
   formatting work (resize all tables, apply the theme, align boxes) when it is faster than menus.
   You may not let it write, summarize or "polish" any text, and you must check afterwards that
   nothing it touched changed the words or numbers. Never use it to create slides or images.
5. **Screenshots.** Every prompt ends with a screenshot request. Take it in edit view showing the
   whole slide and the notes pane if notes were set. The human saves it as `verify/<prompt id>.png`.
6. **Look.** Theme "Simple Light", font Roboto, accent #1F4E79, no transitions, no animations,
   no logos, no clip art. Footer tracker on every content slide as the setup prompt defines it.
7. **Order.** Run `INDEX.md` top to bottom: the four setup prompts first, then slides in the
   listed order, five at a time, pausing for verification after each batch when asked.
8. **STATUS as text.** Write the STATUS block as plain text in your reply (not as an image), so
   the human can copy it. **Export on request.** When asked for a readback, follow `RB_export.md`: download the deck as
   .pptx (and .txt). Chrome saves to the Downloads folder; you cannot drive the native Save
   dialog, so leave the files there and say so in the STATUS block. The human moves them. Never edit slides during a readback.
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
