---
status: proposed
---
# Bus family: AXI-Lite control on every module, AXI-Stream only for bulk data

All three accelerators are modelled as memory-mapped peripherals on the same SoC as the CPU.
Control, configuration and small state (≤ a few hundred bytes per invocation) go through a
32-bit AXI4-Lite slave on every module; modules that move bulk byte streams (`huffman_engine`,
`mtf_cam`) add AXI4-Stream ports. `grape_pipeline` needs only AXI-Lite (~340 B in, ~260 B out per
invocation). Alternatives (64-bit AXI-Lite, a DMA engine for every module, a custom bus) buy
nothing for the benchmarks' data volumes and cost verification effort; AXI has an off-the-shelf
verification agent (`cocotbext-axi`) so the bus itself is checked, not just the datapath.

Trade-offs to revisit at MAS (per Yuval, 2026-08-28): 32- vs 64-bit data width, and whether the
`huffman_engine` bit-stream input is AXI-Stream or a DMA descriptor ring.
