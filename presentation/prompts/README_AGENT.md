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
7. **Order.** Run `INDEX.md` top to bottom: the three setup prompts first, then slides in the
   listed order, five at a time, pausing for verification after each batch when asked.
