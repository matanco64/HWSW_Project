# Readback: export the deck as plain text

Run this whenever a prompt or the human asks for a readback (normally after every batch of five
slides, and after each setup prompt if asked).

1. In the deck: File → Download → Plain Text (.txt).
2. Save the file as `deck_export.txt` in

       \\wsl.localhost\Ubuntu\home\yuvalk\HWSW\HWSW_Proj\presentation\verify

   overwriting the previous one. If the browser saves to Downloads instead, move it there.
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
    deviations: none | <anything unusual about the export>
    screenshot: not taken: readback only

Do not edit the export and do not edit any slide during a readback.
