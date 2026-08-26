---
name: hw-review
description: Pre-review a hardware-flow artifact before its gate — spec mode for prd/mas/uarch/testplan documents, RTL mode for rtl/ and tb/. Use before any checkpoint, when asked to "review the spec", "review the RTL", or when a stage skill reaches its review step.
---

# hw-review — design pre-review

Output: a findings list, appended to `hw/<module>/docs/review_<stage>.md` and presented inline.
Each finding: `id | severity (must|should|nit) | location | problem | proposed fix`. Every `must`
is resolved before the gate row `hw-review findings resolved` (or `agent code review resolved`)
may be `pass`. Re-run after fixes; a finding is closed only with the edit that answers it named.

## Spec mode (`prd`, `mas`, `uarch`, `dv_testplan`)

Read the artifact plus `hw/CONTEXT.md` and the ADRs under `hw/docs/adr/`. Hunt, sentence by
sentence:

1. **Ambiguity** — a term with two readings, a term absent from `CONTEXT.md`, "fast", "large",
   "should", "typically".
2. **Unmeasurable requirements** — any requirement without a number, a unit, and the command or
   test that measures it. Verkor lesson: specs must be "extremely deliberate, tight, and
   verifiable/measurable"; an explicit cycles/step or symbols/cycle target, not "high throughput".
3. **Missing hardware facts** — for every signal, register and memory: width, reset value, access
   type, clock domain, endianness/bit order, valid range, behaviour on overflow.
4. **Missing error cases** — malformed input, out-of-range register writes, back-pressure on every
   `valid/ready` pair, DMA descriptor errors, mid-run abort, reset during operation.
5. **Concurrency** — Verkor lesson: agents reason about Verilog "as if it were sequential code".
   Flag any description that reads as a program (`then`, `after that`) without stating which
   events happen in the same cycle and which are pipelined.
6. **Complexity underestimate** — Verkor lesson: agents "underestimate the complexity of work".
   Flag stages whose latency/area claim has no derivation, and any block listed without its
   control (who starts it, who stalls it, who drains it).
7. **Traceability** — PRD KPI ↔ MAS interface ↔ uArch timing budget ↔ testplan feature; a link
   with no counterpart is a finding.

## RTL mode (`rtl`, `dv_bringup`, `dv_coverage`, `dv_signoff`)

Invoke `superpowers:requesting-code-review` on the diff of `hw/<module>/rtl` and `tb`, then apply
this hardware checklist to every module and note each item's verdict:

- **Reset** — every state-holding register has a defined reset value; reset polarity is `rst_n`;
  no logic depends on X before reset ends.
- **CDC** — any signal crossing clock domains passes a synchroniser or an async FIFO; none
  crosses through plain logic. Single-clock designs state so in the module header.
- **Width** — no implicit truncation or sign extension; all literals sized; Q-notation comments
  match declared widths (`claude-skill-verilog`).
- **X-propagation** — no `casez` with overlapping items, `default` on every `case`, every
  `always_comb` assigns every output on every path.
- **Handshake protocol** — `valid` never depends combinationally on `ready`; `valid` held until
  `ready`; data stable while `valid && !ready`; AXI-Lite responses always returned.
- **FSM completeness** — every state has an exit or is documented as terminal; illegal-state
  recovery; one-hot or enum with `default`.
- **Verkor sequential-reading check** — every `always_ff` reads only registered values of the
  previous cycle; `always_comb` blocks form no combinational loop (`verilator --lint-only -Wall`
  `UNOPTFLAT` is a finding).
- **Testbench honesty** — scoreboard compares against `golden/`, never against a copy of the RTL
  algorithm; checkers fail loudly (`assert`, not a log line).

## Recording

The caller records the gate row: `python3 tools/hw/status.py gate <module> <stage>
"hw-review findings resolved" pass "docs/review_<stage>.md: N findings, 0 must open"`.
