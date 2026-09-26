# Slide B05 (BACKUP)

Layout: "Title and body". Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    mtf_cam in full: K3 1.0686 measured against a 1.063 model, 0.187 mm² with 5.3× headroom, 37.5 MHz from a run that met 27 ns, and list invariants proven unbounded at 16 entries

Body: Insert → Image → Upload from computer → `\\wsl.localhost\Ubuntu\home\yuvalk\HWSW\HWSW_Proj\presentation\assets\mtf_block_diagram.png`.
Fit it inside the body box, keep aspect ratio, centre it. No caption, no border.

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   Accelerate   ·   **Trade-offs**

Speaker notes (exact text, paste into the notes pane):

    The block diagram: a 256-entry shift-register list with a 256:1 rank read mux and a registered parallel move, an item FIFO with a 2-wide write port, the RUNA/RUNB run counter, the run expander and the W = 8 lane packer behind an AXI4-Lite register block. Numbers: 158,441 cycles for the benchmark block, K3 = 1.0686 on the DUT against the 1.063 model, the delta being the FIFO's 2-slot reservation; 18,814 cells, 0.187 mm², 5.3× under the 1.0 mm² soft ceiling with the list at 68 %; Fmax 37.5 MHz from a post-CTS run whose 27 ns constraint was met (+0.3066 ns worst setup slack), the 20 ns run having failed by 6.5964 ns; power ≈ 10.2 mW at that operating point, default activity, indicative only. Formal: the three list invariants (permutation preserved, lookup returns the pre-shift byte at rank r, the moved byte lands at rank 0) are proven unbounded by k-induction at N_LIST=16; at the production 256 the general check is bounded to depth 6 and a fill-abstracted run shows 24 consecutive moves preserve the permutation. An unbounded proof at 256 was tried with smtbmc k-induction, ABC PDR and rIC3, all timing out at 900 s: a SAT wall, stated as such.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Trade-offs", and the notes are saved. Reply with a screenshot of
the slide in edit view.
