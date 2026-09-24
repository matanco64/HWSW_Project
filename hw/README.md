# Hardware accelerator designs

Verilog/SystemVerilog accelerators for the two profiled benchmarks (logically consistent, non-tapeout):
`grape_pipeline` (nbody pair-force pipeline), `huffman_engine` (pyflate canonical-Huffman decode),
`mtf_cam` (pyflate move-to-front CAM). Each module is verified with a pyuvm/cocotb testbench
against a frozen Python golden model wrapping `benchmarks/bm_*`, and sized with Yosys + sky130.

- The stage-gate flow contract, its step list and the generated progress board live in the
  public repository only (FLOW.md, PLAN.md, PROGRESS.md, STATUS.json); they are
  development scaffolding and are left out of the submission archive.
- Algorithm research: [../research/hw-algorithms-nbody.md](../research/hw-algorithms-nbody.md),
  [../research/hw-algorithms-pyflate.md](../research/hw-algorithms-pyflate.md)
- Shared library: `common/rtl` (skid buffer, FIFO, AXI-Lite regs), `common/tb` (pyuvm base test/env,
  stream + AXI-Lite agents, scoreboard, vcd2csv), `common/Makefile.cocotb`

Quick start:

```sh
./hw/setup.sh && source "$(git rev-parse --show-toplevel)/hw/env.sh" && make -C hw/common lint sim cov area
```

## Software-only teammates

The first Claude Code session in a fresh clone asks once whether the checkout is used for the
hardware flow. Answer "Software only" and every hardware hook stays silent (`/hw-mode on` to change
later). The answer lives in `hw/.advisor/mode`, which is gitignored.
