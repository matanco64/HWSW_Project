# Slide S24 (25 of 27)

Layout: "Title and body". Insert after slide S23.

Title (exact text, do not shorten or rephrase):

    We ran a ten-stage flow with four human checkpoints: agents pre-reviewed, humans decided

Body: Insert → Image → Upload from computer → `\\wsl.localhost\Ubuntu\home\yuvalk\HWSW\HWSW_Proj\presentation\assets\hw_flow.png`.
Fit it inside the body box, keep aspect ratio, centre it. No caption, no border.

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   Accelerate   ·   **Trade-offs**

Speaker notes (exact text, paste into the notes pane):

    The picture is the flow every module went through: PRD, architecture spec, micro-architecture, RTL, then verification in four stages, PPA and integration, ten stages in all. Each stage has an exit gate with recorded evidence; across three modules that is 136 gate criteria in the status file. Four of the gates are human checkpoints: PRD, MAS, uArch and DV sign-off. Before each checkpoint an agent pre-reviewed the artifact and wrote a findings table; counting the rows of those tables gives about 350 findings, 126 of them rated must, all resolved before the gate closed. The division of labour was fixed: agents draft and pre-review, the human reads the findings and approves or sends it back. The K1 decision on the previous slides is one such checkpoint.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Trade-offs", and the notes are saved. Reply with a screenshot of
the slide in edit view.
