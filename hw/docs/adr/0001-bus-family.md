---
status: accepted
---
# Bus family: AXI-Lite control on every module, AXI-Stream only for bulk data

All three accelerators are modelled as memory-mapped peripherals on the same SoC as the CPU.
Control, configuration and small state (≤ a few hundred bytes per invocation) go through a
32-bit AXI4-Lite slave on every module; modules that move bulk byte streams (`huffman_engine`,
`mtf_cam`) add AXI4-Stream ports. `grape_pipeline` needs only AXI-Lite (~340 B in, ~260 B out per
invocation). Alternatives (64-bit AXI-Lite, a DMA engine for every module, a custom bus) buy
nothing for the benchmarks' data volumes and cost verification effort; AXI has an off-the-shelf
verification agent (`cocotbext-axi`) so the bus itself is checked, not just the datapath.

Settled at MAS (2026-08-30): AXI-Lite data width is **32 bits** (the shared `axi_lite_regs.sv`
cell and the `cocotbext-axi` agent exist; FP64 values are two words; configuration traffic is
< 0.5 % of every module's block cycles). A 64-bit variant stays a documented improvement option
for the report. Bulk inputs are AXI-Stream (`huffman_engine` `s_bits`, `s_sel`), no descriptor ring.
