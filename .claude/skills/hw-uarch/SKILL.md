---
name: hw-uarch
description: Write the micro-architecture spec (pipeline, FSMs, number formats, memories, timing budget) for an accelerator module through a grilling interview (stage 3 of hw/FLOW.md). Use when hw-flow reaches the uarch stage or the user asks how a module works internally.
---

# hw-uarch — stage 3, uArch

Inputs: approved `docs/prd.md` and `docs/mas.md`, `hw/CONTEXT.md`, ADRs,
`research/hw-algorithms-<bench>.md` (option tables). Output: `hw/<module>/docs/uarch.md`.
Modules proceed one at a time from here (`grape_pipeline` → `huffman_engine` → `mtf_cam`).

## Procedure

1. `python3 tools/hw/status.py set <module> uarch in_progress`.
2. Invoke `grilling` and `domain-modeling` directly (`grill-with-docs` is user-invocation only and the Skill tool refuses it); agenda below. Each design-point choice (rsqrt method, table
   count, CAM style) is an ADR with the rejected options and their cost.
3. Write `docs/uarch.md` sections: Block list (one per RTL module, with file name under `rtl/`);
   Pipeline diagram (Mermaid, stage per column, register boundary marked); FSMs (states,
   transitions, outputs; Mermaid `stateDiagram`); Number formats (IEEE-754 or `Qm.n` per signal,
   `claude-skill-verilog` notation); Memories (name, depth × width, ports, flop vs OpenRAM);
   Timing budget (per stage: logic depth estimate, target ns at the MAS clock); Latency and
   throughput derivation; Hazards and stalls; Reset and CDC statement; Traceability to `PRD-Fn`.
4. Derive latency/throughput with a schedule *simulation* over the full op graph (one node per
   reference-visible rounding — the graph doubles as the fusion audit; see
   grape_pipeline/docs/schedule_model.py), never a stage-sum; the gate row cites the script and
   its printed sweep. A KPI mismatch is fixed here, not in RTL.
5. `hw-review` spec mode (concurrency and complexity checks matter most here); resolve `must`.
6. Record gate rows; set `review`.

## Agenda (module-specific)

**grape_pipeline** — rsqrt option table (research §3): ROM seed + NR reciprocal, magic constant +
NR, SRT sqrt + divider, LNS — choose on latency (cycles/step is the KPI) vs FP64 fidelity; FP64
adder/multiplier/FMA pipeline depths; operation order fixed to the benchmark's
(`dx²+dy²` then `+dz²`); step FSM (pair loop, velocity update, position update, done); register
file for 5 bodies; how the 10 pairs are sequenced through one pipeline and where the loop-carried
dependency stalls.
**huffman_engine** — bit aligner (64-bit shift register, 32-bit FIFO, `peek 20 / consume n`,
bit-reverse mode for DEFLATE, research §5); comparator cascade (20 parallel comparators,
priority encoder, symtab RAM, 2–3 stages, research §1); table builder FSM (counts → first_code →
base → symtab, ~300 cycles); selector FSM (50-symbol counter, 6 register sets); DEFLATE extra-bits
path; pipeline hazards between consume and refill.
**mtf_cam** — MTF CAM structure: 256 × 8-bit shift-register file with per-entry compare/enable
(research §2) vs indexed RAM + shift; read-mux depth; RUNA/RUNB accumulator width
(`run += (1|2) << k`) and burst writer; back-pressure from the output DMA.

## Gate (FLOW.md row 3)

| Criterion | Evidence |
|---|---|
| pipeline/FSM diagrams | `docs/uarch.md §Pipeline`, `§FSMs` Mermaid blocks |
| number formats fixed | `§Number formats` — every datapath signal has a format |
| memories sized | `§Memories` table |
| per-stage timing budget | `§Timing budget` table |
| latency/throughput derived and matches PRD KPI | `§Latency` calculation vs `prd.md` KPI row |
| `hw-review` resolved | `docs/review_uarch.md: N findings, 0 must open` |

```
cd "$(git rev-parse --show-toplevel)"
python3 tools/hw/status.py gate <module> uarch "<criterion>" pass "<evidence>"   # ×6
python3 tools/hw/status.py set <module> uarch review
```
