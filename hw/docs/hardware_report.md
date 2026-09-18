# Hardware Acceleration — Consolidated Report

*Standalone hardware writeup for the HWSW project. Self-contained: every quantitative
claim cites a file under `hw/` or `results/`. This document is the hardware companion to
`report_nbody` (grape) and `report_pyflate` (huffman + mtf); it is written to stand on its
own under grilling, so evidence stages are labeled explicitly and nothing is stated more
strongly than its source supports.*

Author: Yuval Kogan (hardware). Software benchmarks & report prose: Matan Cohen.
Date: 2026-09-17.

---

## 0. Scope and evidence discipline

Three accelerators were designed, verified and synthesized, each targeting the measured
hot boundary of one benchmark:

| Module | Benchmark | Offloaded boundary | Report |
|---|---|---|---|
| `grape_pipeline` | nbody | the whole `advance(dt, n)` integration kernel | `report_nbody` §5 |
| `huffman_engine` | pyflate (bzip2) | bit-reader + canonical-Huffman symbol decode | `report_pyflate` §5 |
| `mtf_cam` | pyflate (bzip2) | move-to-front + RUNA/RUNB run expansion | `report_pyflate` §5 |

`huffman_engine` → `mtf_cam` form the intended on-chip `pyflate_accel` chain producing the
same L-vector as the software symbol loop; `grape_pipeline` is standalone.

**Evidence-stage legend (used for every Fmax below).** OpenLane physical estimates come
at different depths of the flow, and they are *not* interchangeable. Per
`project_instructions.md §7` ("you are not expected to synthesize"), full GDS sign-off is
**bonus**, not required — the requirement is a trade-off discussion with a **defined
operating frequency**, which each module has.

| Stage tag | What it is | Optimism |
|---|---|---|
| **pre-placement STA** | STA on the synthesized netlist with an ideal clock network and estimated net RC | most optimistic; upper bound |
| **post-CTS STA** | STA after floorplan + placement + clock-tree synthesis (real placed clock tree) | closer to real; still no detailed-route RC |
| **GDS sign-off** | fully routed, DRC/LVS-clean | ground truth — **not reached** by any module |

No module reached GDS (no die shot). Post-CTS power was obtained for `mtf_cam` (13.7 mW) and
`huffman_engine` (283 mW), both at post-CTS with **default switching activity** (indicative, not
workload power); grape did not reach post-CTS power.

---

## 1. grape_pipeline (nbody)

### 1.1 Hardware description
FP64 pairwise-gravity accelerator executing a full `advance(dt, n)` on-device. SystemVerilog:
`rtl/grape_pipeline.sv` (top), `grape_force_pipe.sv` (scheduled datapath), `grape_accum.sv`
(accumulate/integrate, parallel-prefix picker), `grape_step_fsm.sv` (control), `fp64_*.sv`
(add/mul/sqrt/rcp units). Single clock domain, synchronous `rst_n`.

### 1.2 Inputs / outputs, widths, frequency
- **I/O** (`docs/mas.md §2`): 32-bit AXI4-Lite slave exposing FP64 (binary64) body state,
  `DT` (FP64), `NSTEPS` (32-bit), pair configuration, control/status, counters, IRQ.
- **Operating frequency:** design target **50 MHz** (`docs/mas.md §3`, `docs/prd.md` K-table).
  Achievable **≈ 19.46 MHz** — *post-CTS STA* on the parallel-prefix netlist
  (`docs/ppa.md` Addendum 2026-09-14; `synth/runs/grape_prefix2/35-openroad-stamidpnr-1/ws.max.rpt`,
  +98.6212 ns slack @ 150 ns period).

### 1.3 Architecture
`docs/uarch.md`: three FP64 add/sub, three multipliers, one sqrt (radix-4 SRT), one
reciprocal (2¹⁰×20b ROM seed + Newton refinement in Q1.57), sharing a scheduled
**290-operation step**. An ordered accumulation sequencer resolves body-component
dependencies (pairs sharing a body serialize their velocity updates) before positions
commit; steps stay serial. There is no FMA — multiply and accumulate round separately
(matches stock `pow`-free arithmetic contract, `docs/testplan.md §4`).

### 1.4 HW/SW interface
- MMIO only, no DMA (`docs/mas.md §5`, ADR-0001). ≈ 150 AXI-Lite transactions per
  invocation (70 body + 10 pair + 4 config in; 60 state + 3 counter out), **once per
  20,000-step invocation** — < 0.03 % of compute (`docs/integration.md §1`).
- Driver model `driver/grape_pipeline_driver.py` verified register-for-register vs
  `docs/mas.md §4` (`driver/check_regmap.py` → **0 differences**) and against a
  full-invocation cycle model (`driver/test_driver.py` → 4/4 pass; 2,480,000 cycles =
  124 × 20,000).

### 1.5 Acceleration justification + estimate
- **Baseline** `T` = **231.20 ms** (pyperf mean; median 229 ms), `results/baseline_nbody_stats.txt`.
- **Fraction** `f` = 0.95 (`advance` doubly-nested loop, `prd.md §4`).
- **HW cost** 2,480,000 cycles/invocation (K1 = **124** cyc/step, `docs/ppa.md`, measured
  bit-exact on the full 20,000-step benchmark).
- Amdahl `S = T / ((1−f)·T + t_hw)`:
  - **50 MHz** (target): t_hw = 49.6 ms → **~3.8–4.5×** (clears K3 ≥ 4× near the top of `f`).
  - **19.46 MHz** (achievable): t_hw = 127.4 ms → **≈ 1.66×** (compute-only upper bound
    1.81× vs stock / 1.12× vs the 143.13 ms optimized-Python tier). Does **not** beat the
    9.53 ms native-software tier. (`docs/integration.md §3`.)
- **Honest conclusion:** compute-bound; the end-to-end win is gated on timing closure, not
  the interface. The parallel-prefix rewrite already moved the accumulate-picker path
  off-critical (11.15 → 19.46 MHz, 1.75×, bit-exact K1 = 124); the current limiter is the
  integrate-multiplier operand path, whose pipelining is the documented next step.

### 1.6 Block diagram
`docs/mas.md §7` / `docs/block_diagram.svg` (and `report_nbody` fig `grape_report.svg`,
`pair_dependency.svg`).

### 1.7 Performance / area / power trade-offs
`docs/ppa.md`. Yosys+sky130 area **4.075 mm² / 584,454 cells**. Measured 2-point trade-off:

| Design point | Area | K1 cyc/step | Verdict |
|---|---:|---:|---|
| 1-wide accumulate, 1-port RF | 2.938 mm² | 162 | rejected (misses KPI) |
| **3-wide accumulate, 3-port RF** | **4.075 mm²** | **124** | **chosen** (+38.7 % area, −23.5 % cycles) |

Fmax **19.46 MHz** (post-CTS, parallel-prefix). Power / die shot: **not obtained** (OpenLane
died in global routing, GRT-0607; not §7-required, not invented).

---

## 2. huffman_engine (pyflate)

### 2.1 Hardware description
bzip2/DEFLATE canonical-Huffman decoder. SystemVerilog: `rtl/huffman_engine.sv` (top) +
`huff_aligner` (64-bit window + barrel shifter + FIFO), `huff_builder` (canonical table
build), `huff_decoder` (20-wide comparator cascade + priority encode), `huff_tables`
(symtab + 6 table register sets), `huff_regs` (length window + counters), `huff_selector`
(50-symbol table switch), `huff_ctrl`, `huff_deflate`, `huff_out`. Single clock, `rst_n`.

### 2.2 Inputs / outputs, widths, frequency
- **I/O:** 32-bit compressed stream + 8-bit selector stream in; 32-bit beats out carrying a
  9-bit symbol + type fields (`docs/mas.md §2`). 32-bit AXI4-Lite window holds `START_BIT`,
  lengths, counters for six tables and bzip2's 20-bit max code length.
- **Operating frequency:** target **50 MHz** (K3, `docs/mas.md §6`). Achievable
  **≈ 25.1 MHz** — *post-CTS STA*, near-critical at a 40 ns constraint, 0 setup violations
  (`synth/runs/signoff_confirm/31-openroad-stamidpnr-1/`, worst reg→reg slack +0.156 ns → 39.84 ns
  achievable). The initial 20 ns run was placement-non-convergent and gave only a pre-placement
  **8.9 MHz** — but that was a **high-fanout-net wireload artifact** (one register Q fanning out
  to thousands of pins, unbuffered pre-CTS; same class as grape's pre-PnR fanout net). Relaxing
  the clock to 40 ns (grape's lesson) let placement converge through CTS, and post-CTS the real
  timing is **faster** (25.1 MHz), not slower. huffman is therefore now **post-CTS** evidence,
  matching grape and mtf (`docs/ppa.md §3`).

### 2.3 Architecture
`docs/uarch.md`: a bit aligner feeds a canonical-code comparator/lookup datapath; a selector
controller changes the active table every 50 symbols with a **0-cycle switch** (six table
register sets pre-loaded). Decodes 1 symbol/cycle.

### 2.4 HW/SW interface
- Software parses each bzip2 block header and calls `HuffmanDriver.decode_block()` over a
  4 KB AXI4-Lite window; compressed bytes + selectors streamed by DMA (`docs/mas.md §5/§6`).
- Driver model `driver/huffman_engine_driver.py`, verified vs register map (0 diffs) and the
  signed-off cycle model (`docs/integration.md §1`).

### 2.5 Acceleration justification + estimate
- **Baseline** `T` = **1,123.49 ms** (≈ 1.12 s mean; median 1.12 s), `results/baseline_pyflate_stats.txt:18`.
- **Fraction** `f` = **0.496** (Huffman decode 12.0 % + bit reader 37.6 %, `prd.md §1`).
- **HW cost** 149,276 cycles for 148,271 symbols → **K1 = 1.0068** cyc/sym, trace-exact vs
  golden over every beat (`docs/ppa.md`, `docs/uarch.md §7`).
- Amdahl (residual 50.4 % of T = **566.2 ms**):
  - **50 MHz:** t_hw = 2.99 ms → **≈ 1.97×** (essentially the 1.98× ideal bound).
  - **8.9 MHz** (pre-PnR): t_hw = 16.8 ms → **≈ 1.93×**.
- **Key finding — clock-insensitive.** Unlike grape, huffman is **Amdahl-fraction-bound,
  not clock-bound**: S stays **1.89–1.97×** across a 10× clock range (even 5 MHz → 1.89×),
  because the software Huffman path is ~566 ms and the hardware decode is milliseconds. The
  realized clock does not gate the result; `f` does (`docs/integration.md §3`).

### 2.6 Block diagram
`docs/mas.md §7` / `docs/block_diagram.svg` (and `report_pyflate` fig `decode_report.svg`).

### 2.7 Performance / area / power trade-offs
`docs/ppa.md`. Yosys+sky130 **1.634 mm² / 151,058 cells**, **54.44 % sequential** — the
design is a *memory*, not a datapath (`huff_tables` + `huff_regs` = 95 % of area, the
decode comparator cascade only 1.3 %). Soft K5 ceiling 1.0 mm² **missed 1.63×**, a storage
miss: ~34 kbit of flops (no SRAM macro in the sky130 HD open flow). Documented area path:
move the 17.3 kbit symtab + 8.6 kbit length window into SRAM macros → projected ~0.75 mm²
std cells + 2 macros (**not synthesized**). Fmax **25.1 MHz** (post-CTS, near-critical).
Power **≈ 283 mW** post-CTS (default switching activity at the 40 ns constraint — indicative,
scales with clock, not workload power). Die shot: not obtained.

---

## 3. mtf_cam (pyflate)

### 3.1 Hardware description
Move-to-front + RUNA/RUNB run-expansion engine. SystemVerilog: `rtl/mtf_cam.sv` (top) +
`mtf_list` (256-entry shift-register CAM), `mtf_ctrl` (invocation/init-fill FSM), `mtf_run`
(RLE counter), `mtf_expand` (run→byte), `mtf_pack` (W-lane packer), `item_fifo`, `mtf_regs`.
Single clock, `rst_n`.

### 3.2 Inputs / outputs, widths, frequency
- **I/O:** input is a *rank*; the decoder indexes the alphabet, shifts preceding entries, and
  expands RUNA/RUNB groups through a buffered output packer **8 bytes wide** (`docs/mas.md §2`).
- **Operating frequency:** target **50 MHz** (uArch §6). Achievable **≈ 37.6 MHz** —
  *post-CTS STA* (tt, `synth/runs/signoff/31-openroad-stamidpnr-1/ws.max.rpt`, −6.5964 ns @
  20 ns). This is the **strongest-evidence** Fmax of the three: mtf_cam is the only module
  that drove OpenLane all the way through CTS + post-CTS STA (no GRT-0607). Missed 50 MHz by
  ~1.33×.

### 3.3 Architecture
`docs/uarch.md`: a 256×8 shift-register CAM with a 256:1 rank read-mux and a parallel
registered move-to-front shift (every entry writable each cycle, so no RAM). Run expansion
feeds a W=8-lane packer. K3 = **1.063** cyc/sym (model) / **1.0686** measured on the DUT.

### 3.4 HW/SW interface
- Ranks in / L-vector bytes out; output DMA drains **336,184** L-vector bytes
  (`docs/integration.md`). Driver `driver/mtf_cam_driver.py`, register-map verified (0 diffs),
  RTL-cosim 16/16 pass.

### 3.5 Acceleration justification + estimate
- **Baseline** `T` = **1.12 s** (mean), `results/baseline_pyflate_stats.txt`.
- **Fraction** `f` = **0.1344** (`move_to_front` self-time share, `prd.md`, `report_pyflate` §2).
- **HW cost:** DUT-measured **158,441 cycles** (K3 = 1.0686) → **≈ 4.19 ms** @ 37.6 MHz;
  model 157,560 cycles (K3 = 1.063) at W=8 (`docs/ppa.md §3.1`, `docs/integration.md`). Both
  cycle figures are disclosed; the DUT number carries implementation overhead over the model.
- Standalone end-to-end: **≈ 1.15×** (small stage share). The isolated-stage ratio (80.4 ms
  stock MTF microbench → 19.1× @ 37.6 MHz / 25.4× @ 50 MHz, PRD K5) is a **different
  experiment** from the whole-decoder profile and must not be substituted for it.

### 3.6 Block diagram
`docs/mas.md §7` / `docs/block_diagram.svg` (and `report_pyflate` fig `decode_report.svg`,
shared chain diagram).

### 3.7 Performance / area / power trade-offs
`docs/ppa.md`. Yosys+sky130 **0.187 mm² / 18,814 cells**; `mtf_list` CAM = **68 %** of area
and is **W-invariant**. Measured W-sweep:

| W | Area mm² | K3 cyc/sym | Verdict |
|---|---:|---:|---|
| 4 | 0.182 | 1.175 | fails K3 ≤ 1.10 |
| **8** | **0.187** | **1.063** | **chosen** (knee) |
| 16 | 0.208 | 1.023 | +10.9 % area for 3.8 % throughput — not needed |

Soft K5/K6 1.0 mm² ceiling **met 5.3×**. Fmax **37.6 MHz** (post-CTS, W-independent). Power
**≈ 13.7 mW** post-CTS (default switching activity — indicative, not workload power). Die
shot: not obtained.

---

## 4. Cross-module summary

| Metric | grape_pipeline | huffman_engine | mtf_cam |
|---|---:|---:|---:|
| Cells (sky130 HD) | 584,454 | 151,058 | 18,814 |
| Area | 4.075 mm² | 1.634 mm² | 0.187 mm² |
| Cyc/symbol or /step | 124 /step | 1.0068 /sym | 1.0686 /sym |
| **Fmax** | **19.46 MHz** | **25.1 MHz** | **37.6 MHz** |
| **Fmax evidence stage** | **post-CTS** | **post-CTS** | **post-CTS** |
| Power | not obtained | ≈ 283 mW (indic., 40 ns) | ≈ 13.7 mW (indic., 20 ns) |
| Directed + random tests | 9/9 | 17/17 | 16/16 |
| Line / toggle coverage | 91.7 % / 96.0 % | 90.4 % / 90.3 % | 92.0 % / 93.8 % |
| End-to-end estimate | ~1.66× (19.46 MHz) / ~3.8–4.5× (50 MHz) | ~1.9–2.0× (clock-insensitive) | ~1.15× |

**All three Fmax numbers are now post-CTS STA** (real placed clock tree) — the same evidence
stage — so they are comparable on that axis. None completed routed GDS sign-off (no die shot).
Power figures use **default switching activity** at each run's own clock constraint (283 mW @
40 ns, 13.7 mW @ 20 ns), so they are indicative and **not** comparable to each other or usable
as workload-energy numbers.

## 5. Honest limitations (self-declared)

- No module reached routed GDS → no die shot; post-CTS power for mtf_cam (13.7 mW) and
  huffman (283 mW), both default activity at different clocks — cannot support an
  energy-savings claim or a cross-module power comparison.
- Every end-to-end speedup is a **conditional projection** using a profiled fraction and a
  single benchmark input; the on-chip chain throughput and platform DMA/host-interface cost
  are **not measured** (module + driver tests do not exercise them).
- huffman's SRAM-macro sub-1 mm² path is **projected, not synthesized**.
- mtf_cam's formal move-to-front invariants are proven **unbounded @ N_LIST=16** and
  **bounded depth-24 @ N_LIST=256** (general unbounded-256 is SAT-intractable — honestly a
  wall, not skipped).
- grape and huffman miss 50 MHz (2.6× and 2.0× respectively, post-CTS); documented RTL follow-ups
  (pipeline the integrate-multiply path; pipeline the table build + register the symtab mux)
  are datapath changes deferred beyond the PPA stage.

## 6. Rubric coverage (project_instructions.md §7)

Every §7 bullet is answered for every module (section refs above):

| §7 bullet | grape | huffman | mtf |
|---|:--:|:--:|:--:|
| Hardware description (Verilog/SV) | §1.1 | §2.1 | §3.1 |
| Inputs/outputs, widths, frequency | §1.2 | §2.2 | §3.2 |
| Hardware architecture | §1.3 | §2.3 | §3.3 |
| HW/SW interface | §1.4 | §2.4 | §3.4 |
| Acceleration justification + estimate | §1.5 | §2.5 | §3.5 |
| Block diagram | §1.6 | §2.6 | §3.6 |
| Performance/area/power trade-offs | §1.7 | §2.7 | §3.7 |
