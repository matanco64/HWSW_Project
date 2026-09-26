# Readback: export the deck as plain text

Run this whenever a prompt or the human asks for a readback (normally after every batch of five
slides, and after each setup prompt if asked).

1. In the deck: File → Download → Microsoft PowerPoint (.pptx).
2. Then File → Download → Plain Text (.txt). Both land in the Windows Downloads folder; if
   Chrome asks, answer Keep. Do not try to drive the Save dialog. The human moves both files to

       \\wsl.localhost\Ubuntu\home\yuvalk\HWSW\HWSW_Proj\presentation\verify

   as `deck_export.pptx` and `deck_export.txt`.
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
