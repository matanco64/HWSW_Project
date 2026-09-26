# Slide S02 (3 of 27)

Layout: "Title and body". Insert after slide S01.

Title (exact text, do not shorten or rephrase):

    nbody is 5 bodies, 10 pairs and 20,000 steps of pure-Python float arithmetic

Body: Insert → Image → Upload from computer → `\\wsl.localhost\Ubuntu\home\yuvalk\HWSW\HWSW_Proj\presentation\assets\nbody_pairs.png`.
Fit it inside the body box, keep aspect ratio, centre it. No caption, no border.

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    **Analyze**   ·   Profile   ·   Optimize   ·   Accelerate   ·   Trade-offs

Speaker notes (exact text, paste into the notes pane):

    The state is the Sun and four gas giants: 35 Python floats in nested lists, a position, a velocity and a mass per body. pairs is a list of ten tuples aliasing those same lists, built once. One timed iteration evaluates the energy, calls advance(0.01, 20000), and evaluates the energy again. Every step visits the same ten pairs, forms dx, dy and dz, computes mag = dt * (dsq ** -1.5) and updates both bodies' velocities in place. Ten pairs times 20,000 steps is 200,000 pair-force evaluations, and between every one of them sits the interpreter. The physics is compact; the machinery around each calculation is what we go looking for.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Analyze", and the notes are saved. Reply with a screenshot of
the slide in edit view.
