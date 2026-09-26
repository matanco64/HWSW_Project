# Slide S21 (22 of 27)

Layout: "Title and body". Insert after slide S20.

Title (exact text, do not shorten or rephrase):

    The chain reproduces the benchmark output byte-exact: 336,184 bytes in 159,303 cycles, with and without back-pressure

Body: Insert → Image → Upload from computer → `\\wsl.localhost\Ubuntu\home\yuvalk\HWSW\HWSW_Proj\presentation\assets\chain_cosim.gif`.
Fit it inside the body box, keep aspect ratio, centre it. No caption, no border.

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   **Accelerate**   ·   Trade-offs

Speaker notes (exact text, paste into the notes pane):

    The clip is `make -C hw/pyflate_accel sim`: Verilator builds a logic-free wrapper that wires huffman_engine's output stream straight into mtf_cam's input, the cocotb test programs both modules, doorbells mtf_cam first, streams the real benchmark block and compares the L-vector with the golden model; it runs in ~30 s and ends 2/2 PASS. Both runs are byte-exact over 336,184 bytes: 159,303 cycles with an always-ready sink, 189,448 under 50 % random output back-pressure. That is 0.54 % above the standalone mtf projection; the difference is the decoder's table-build start-up. The link statistics say who sets the pace: the decoder was stalled by mtf_cam on 10,013 cycles while mtf_cam starved on only 873, so the chain runs at mtf's 1.0686 cycles per symbol, not the decoder's 1.0068. One shared clock, no clock-domain crossing; the rate difference is absorbed by tready back-pressure.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Accelerate", and the notes are saved. Reply with a screenshot of
the slide in edit view.
