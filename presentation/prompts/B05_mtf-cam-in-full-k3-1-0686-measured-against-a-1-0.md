# Slide B05 (BACKUP)

Layout: "Title and body · Trade-offs" (Slide → Apply layout). Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    mtf_cam in full: K3 1.0686 measured against a 1.063 model, 0.187 mm² with 5.3× headroom, 37.5 MHz from a run that met 27 ns, and list invariants proven unbounded at 16 entries

Body: insert the image `C:\Users\Kogan\HWSW_presentation\assets\mtf_block_diagram.png` with your direct upload tool.
Size it to fill the body box: width 9.2 in, or height 3.4 in if that binds first, keeping the
aspect ratio; place it at x = 0.4 in, y = 1.6 in and centre it horizontally in the body box.
It must not overlap the title or the footer tracker. No caption, no border, no crop.

Do not touch the footer tracker: the layout already highlights "Trade-offs".

Speaker notes (exact text, paste into the notes pane):

    The block diagram: a 256-entry shift-register list with a 256:1 rank read mux and a registered parallel move, an item FIFO with a 2-wide write port, the RUNA/RUNB run counter, the run expander and the W = 8 lane packer behind an AXI4-Lite register block. Numbers: 158,441 cycles for the benchmark block, K3 = 1.0686 on the DUT against the 1.063 model, the delta being the FIFO's 2-slot reservation; 18,814 cells, 0.187 mm², 5.3× under the 1.0 mm² soft ceiling with the list at 68 %; Fmax 37.5 MHz from a post-CTS run whose 27 ns constraint was met (+0.3066 ns worst setup slack), the 20 ns run having failed by 6.5964 ns; power ≈ 10.2 mW at that operating point, default activity, indicative only. Formal: the three list invariants (permutation preserved, lookup returns the pre-shift byte at rank r, the moved byte lands at rank 0) are proven unbounded by k-induction at N_LIST=16; at the production 256 the general check is bounded to depth 6 and a fill-abstracted run shows 24 consecutive moves preserve the permutation. An unbounded proof at 256 was tried with smtbmc k-induction, ABC PDR and rIC3, all timing out at 900 s: a SAT wall, stated as such.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the slide uses the "Title and body · Trade-offs" layout, and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for B05 (expected: position end of deck, body image mtf_block_diagram.png,
notes_set yes, tracker Trade-offs via layout).
