# Hardware accelerator designs

Verilog/SystemVerilog accelerators for the two profiled benchmarks (logically consistent, non-tapeout):
`grape_pipeline` (nbody pair-force pipeline), `huffman_engine` (pyflate canonical-Huffman decode),
`mtf_cam` (pyflate move-to-front CAM). Each module is verified with a pyuvm/cocotb testbench
against a frozen Python golden model wrapping `benchmarks/bm_*`, and sized with Yosys + sky130.

- [FLOW.md](FLOW.md) — the flow contract: stages, gates, skills, hooks, make targets, STATUS.json schema
- [PLAN.md](PLAN.md) — concrete step list (to be written)
- [PROGRESS.md](PROGRESS.md) — generated from `STATUS.json`, never hand-edited
- Algorithm research: [../research/hw-algorithms-nbody.md](../research/hw-algorithms-nbody.md),
  [../research/hw-algorithms-pyflate.md](../research/hw-algorithms-pyflate.md)
- Shared library: `common/rtl` (skid buffer, FIFO, AXI-Lite regs), `common/tb` (pyuvm base test/env,
  stream + AXI-Lite agents, scoreboard, vcd2csv), `common/Makefile.cocotb`

Quick start:

```sh
./hw/setup.sh && source hw/env.sh && make -C hw/common lint sim cov area
```

## Software-only teammates

The first Claude Code session in a fresh clone asks once whether the checkout is used for the
hardware flow. Answer "Software only" and every hardware hook stays silent (`/hw-mode on` to change
later). The answer lives in `hw/.advisor/mode`, which is gitignored.
