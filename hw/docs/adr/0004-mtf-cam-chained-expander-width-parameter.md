---
status: accepted
---
# mtf_cam: one module = shift-register MTF list + run expander, chained on-chip after huffman_engine, output width W as a parameter (default 8)

On the benchmark block 73 % of the 336,184 L-vector bytes come from 34,664 RUNA/RUNB run groups
(p50 length 2, max 8,157) and only 27 % from the 89,837 MTF lookups (rank p50 3, max 144, never 0).
So the throughput risk of this stage is the run expander, not the CAM: with 1 byte/cycle the
output side needs 2.27× the input cycles; W = 8 bytes/cycle is the first width at which the
output no longer bottlenecks the 1-symbol/cycle input (144,533 vs 148,271 cycles), W = 16 buys
10 % margin and wider buys nothing (floor 124,501). We decided: (1) MTF list and expander form
one module fed directly by `huffman_engine.m_sym` on chip (no DMA round trip for 148 k symbols),
emitting the L-vector on a W-byte AXI-Stream to platform DMA; (2) W is a SystemVerilog parameter,
default 8 (a 64-bit beat), swept 4/8/16 at PPA as the module's design-point study; (3) the list is
initialised in hardware from the 256-bit `used` map (mirrors pyflate `favourites`); (4) the MTF list
is a 256-entry shift-register CAM (parallel rank select, one-cycle shift) whose permutation
invariant is proven with SymbiYosys. Considered and rejected: separate MTF and expander modules
(two more stream interfaces, nothing gained); RAM + rank counters (multi-cycle updates); MTF in
software after a hardware Huffman decode (11 % of stock pyflate stays on the CPU). Inverse BWT
remains a software non-target (ADR-0003).
Sources: `golden/calibrate.py`; research/hw-algorithms-pyflate.md §2; dev/pyflate/FINDINGS.md §0, §1e.
