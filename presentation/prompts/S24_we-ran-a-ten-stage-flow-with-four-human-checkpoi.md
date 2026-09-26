# Slide S24 (25 of 27)

Layout: "Title and body · Trade-offs" (Slide → Apply layout). Insert after slide S23.

Title (exact text, do not shorten or rephrase):

    We ran a ten-stage flow with four human checkpoints: agents pre-reviewed, humans decided

Body: Insert → Image → Upload from computer → `C:\Users\Kogan\HWSW_presentation\assets\hw_flow.png`.
Fit it inside the body box, keep aspect ratio, centre it. No caption, no border.

Do not touch the footer tracker: the layout already highlights "Trade-offs".

Speaker notes (exact text, paste into the notes pane):

    The picture is the flow every module went through: PRD, architecture spec, micro-architecture, RTL, then verification in four stages, PPA and integration, ten stages in all. Each stage has an exit gate with recorded evidence; across three modules that is 136 gate criteria in the status file. Four of the gates are human checkpoints: PRD, MAS, uArch and DV sign-off. Before each checkpoint an agent pre-reviewed the artifact and wrote a findings table; counting the rows of those tables gives about 350 findings, 126 of them rated must, all resolved before the gate closed. The division of labour was fixed: agents draft and pre-review, the human reads the findings and approves or sends it back. The K1 decision on the previous slides is one such checkpoint.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Trade-offs" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for S24 (expected: position 25, body image hw_flow.png,
notes_set yes, tracker Trade-offs via layout).
