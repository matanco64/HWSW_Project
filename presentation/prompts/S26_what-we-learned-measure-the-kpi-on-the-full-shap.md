# Slide S26 (27 of 27)

Layout: "Title and body". Insert after slide S25.

Title (exact text, do not shorten or rephrase):

    What we learned: measure the KPI on the full-shape workload early, and the next experiment is a native inverse BWT and a timing confirmation run

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Lesson or next step | Where it came from |
|---|---|
| Lesson: measure the KPI on the full-shape workload at bring-up | grape read 162 cycles per step at sign-off; the fix landed at 124 |
| Lesson: removing the interpreter and building a fast datapath are different problems | software took almost all of nbody's gain; the accelerator ties optimized Python |
| Lesson: the platform you report on decides the ranking | the pyflate ablation ordered its three changes one way on the dev machine, the other on the VM |
| Next: a native inverse BWT with an isolated timer and a working-set sweep | 137.7 ms is the floor for both the Rust and the hardware route |
| Next: matched phase timing and a routed timing run | the residuals are assumptions; the clocks are post-CTS estimates |

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   Accelerate   ·   **Trade-offs**

Speaker notes (exact text, paste into the notes pane):

    Three things we would tell ourselves at the start. First, measure the KPI on the full-shape workload at bring-up: grape read 162 cycles per step at sign-off after every earlier gate was green, because the smoke test used two pairs; the fix landed at 124. Second, removing interpreter overhead and building a fast physical datapath are different problems: software captured almost all of nbody's gain, and the accelerator ties optimized Python. Third, the platform you report on decides the ranking: the pyflate ablation ordered its three changes differently on the development machine and on the VM. Two next experiments: a native inverse BWT with an isolated timer and a working-set sweep, because its 137.7 ms is the floor for both routes; and matched phase timing plus a routed timing run, replacing assumed residuals, post-CTS clocks and the unmeasured interface time.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Trade-offs", and the notes are saved. Reply with a screenshot of
the slide in edit view.
