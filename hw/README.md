# Hardware accelerator designs

Planned modules (Verilog/SystemVerilog, logically consistent, non-tapeout):

- `huffman_engine/` — pyflate: fixed-function canonical-Huffman decode engine
  (bit aligner, comparator cascade, symbol RAM, selector FSM; MMIO + DMA descriptor interface).
- `mtf_cam/` — pyflate: 256-entry move-to-front shift-register CAM (fused pipeline stage).
- `grape_pipeline/` — nbody: GRAPE-style pairwise gravity pipeline
  (rsqrt Newton-Raphson datapath, FMA accumulate, step-count FSM; MMIO register file).

Each module ships with a testbench checked against a Python golden model
(pyflate: symbol-stream trace diff; nbody: trajectory/energy diff).
