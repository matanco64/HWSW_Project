---
name: hw-rtl
description: Implement an accelerator module's synthesizable SystemVerilog from its approved uArch (stage 4 of hw/FLOW.md), lint-clean and Yosys-synthesizable. Use when hw-flow reaches the rtl stage or the user asks to write, fix, or refactor RTL under hw/.
---

# hw-rtl — stage 4, RTL

Inputs: approved `docs/uarch.md` (block list = file list), `docs/mas.md` (ports, register map),
`hw/common/rtl/` shared cells (skid buffer, `axi_lite_regs.sv`, valid/ready FIFO). Output:
`hw/<module>/rtl/*.sv`, one file per uArch block, `<module>_top.sv` as the top. Style and tool
rules: `claude-skill-verilog` (invoke it first; `always_ff` holds simple non-blocking assignments
only, logic in `always_comb`, Q-notation comments, sized literals, Yosys-synthesizable subset).

## Procedure

1. `python3 tools/hw/status.py set <module> rtl in_progress`.
2. Invoke `claude-skill-verilog`. Copy port lists from `mas.md` verbatim (name, width, direction);
   copy formats from `uarch.md §Number formats` into signal comments.
3. Build leaf blocks first, top last. For each block use `superpowers:test-driven-development`
   where a cheap check exists: write the cocotb smoke test under `tb/unit/test_<block>.py`
   (reset, one transaction, one boundary value — `gf-cocotb` template) before the RTL, watch it
   fail, then implement. Blocks with no cheap oracle (FP64 datapath) get the golden-model
   comparison at `hw-dv-bringup` instead; say so in the block header.
4. After every `.sv` edit the PostToolUse hook runs `verilator --lint-only -Wall` on the file;
   fix warnings before the next edit. Verkor lesson: write each `always_ff` as "what the flops
   hold next cycle", never as a sequence of steps — a `for` loop with a data dependency inside
   `always_ff` is a design error, not a style nit.
5. `make -C hw/<module> lint` (whole module, `-Wall`, zero warnings) and
   `make -C hw/<module> area` (Yosys `synth` over `synth/yosys.ys`; succeeds and writes
   `synth/area.txt`). Read the cell count against the uArch memory sizing; a 10× surprise means a
   memory inferred as flops or a loop unrolled — fix in RTL.
6. Every FSM: enum type, `default` arm, reset state; every memory: uArch depth × width with the
   inference template from `claude-skill-verilog`.
7. `hw-review` RTL mode (includes `superpowers:requesting-code-review` and the hardware
   checklist); resolve every `must`.
8. Record gate rows; set `done` (agent-review gate, no human checkpoint).

## Rules

- `rtl/` holds RTL only: no testbench constructs, no `initial` outside reset-free memories, no
  `$display` in synthesizable paths (guard with `` `ifdef SIMULATION``).
- Parameters for every design-point knob the PPA stage will sweep (pipeline depth, NR iterations,
  table count, CAM width) — `PROGRAPE`-style parametrised modules.
- A change to the register map or ports goes back to `mas.md` first (user decision), then RTL.

## Gate (FLOW.md row 4)

| Criterion | Evidence |
|---|---|
| `make lint` clean (`verilator --lint-only -Wall`) | `make -C hw/<module> lint → 0 warnings` |
| Yosys `synth` succeeds (synthesizable subset) | `make -C hw/<module> area → synth/area.txt` (cell count line) |
| agent code review resolved | `docs/review_rtl.md: N findings, 0 must open` |

```
cd "$(git rev-parse --show-toplevel)"
python3 tools/hw/status.py gate <module> rtl "<criterion>" pass "<evidence>"   # ×3
python3 tools/hw/status.py metric <module> ppa.cells <n>
python3 tools/hw/status.py set <module> rtl done
```
