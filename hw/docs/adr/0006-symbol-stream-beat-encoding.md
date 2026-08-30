---
status: accepted
---
# Symbol-stream beat encoding shared by huffman_engine (m_sym) and mtf_cam (s_sym)

One fixed 32-bit AXI-Stream beat carries every decoded item of either mode, so `mtf_cam` and the
DMA sink see the same format and no width depends on MODE: `TDATA[8:0]` = value, `TDATA[11:9]` =
TYPE (0 = bzip2 symbol — RUNA/RUNB/MTF index, never the EOB value; 1 = DEFLATE literal byte; 2 = DEFLATE
length+distance with `length[8:0]` in `TDATA[8:0]` and `distance[15:0]` in `TDATA[27:12]`; 3 = EOB,
both modes — the beat carries the EOB value in [8:0], ALPHABET−1 for bzip2 / 256 for DEFLATE,
and 0 in [27:12]), `TDATA[31:28]` reserved 0; TLAST on the EOB beat. `mtf_cam` consumes TYPE 0 and 3 and
raises ERR_RANK on any other TYPE (PRD-F1/F10 of mtf_cam). Alternatives rejected: 9-bit beats
with a mode-dependent sideband (two formats to verify), 64-bit beats (wasteful for the 148 k
bzip2 symbols per block).
