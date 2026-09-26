# Slide B10 (BACKUP)

Layout: "Title and body". Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    How we used AI: a stage-gated flow, prompt.txt as the log, and the decisions humans made

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Decision | Options came from | Decided by | Where recorded |
|---|---|---|---|
| FP64 in the benchmark's order, no FMA | agent research + uArch review finding R1 | Yuval, ADR-0002 / ADR-0007, uArch checkpoint | hw/docs/adr, review_uarch.md |
| 3 add + 3 mul unit mix | agent schedule-model sweep | Yuval at the uArch checkpoint | uarch.md §7 |
| Boundary: whole advance() on-chip, MMIO only | PRD grilling interview | Yuval at the PRD and MAS checkpoints | prd.md §4, ADR-0001 |
| Keep K1 ≤ 128 rather than renegotiate to 162 | agent offered both at sign-off | Yuval at the DV sign-off checkpoint | ppa.md |
| Accept the 50 MHz miss and report 19.46 MHz with caveats | PPA stage | Yuval | ppa.md §7 framing |
| Retire the MDP benchmark | scope review | Matan | CLOSEOUT.md |

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   Accelerate   ·   **Trade-offs**

Speaker notes (exact text, paste into the notes pane):

    The agent, Claude Code, drafted RTL, testbenches, flow documents and report text; every prompt is in prompt.txt, hand-written at first and auto-logged by a hook afterwards, 220 dated entries over the project. What kept it honest was the flow: ten stages with gates, four of them human checkpoints, and an agent pre-review before each checkpoint whose findings table the human read before approving. Yuval directed the hardware flow and reviewed each gate; Matan designed and measured the software ladder and ran the course-VM measurements. The table lists the decisions a grader may ask about and who made them. The pattern is the same each time: the agent produced options and evidence, the human chose, and the choice is written in an ADR, a checkpoint approval or a close-out record.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Trade-offs", and the notes are saved. Reply with a screenshot of
the slide in edit view.
