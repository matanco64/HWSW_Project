# huffman_engine — PPA (stage 9)

Method, tools and corner, then the three gate artefacts: the Yosys+Liberty area
(fast gate), the OpenLane 2 outcome (or the STA fallback, honestly reported like
grape), and the design-point trade-off study. Every number cites its file.

## 0. Method

- **Fast gate:** Yosys (OSS CAD Suite nightly 2026-08-26) `synth -top huffman_engine
  -flatten`, `dfflibmap` + `abc -liberty`, `stat -liberty` against **sky130_fd_sc_hd,
  tt corner, 25 °C, 1.80 V** (`hw/tools/pdk/sky130_fd_sc_hd__tt_025C_1v80.lib`).
  Command: `make -C hw/huffman_engine area` → `synth/area.txt`.
- **Per-module attribution:** a second, non-flattened `synth -top huffman_engine`
  + `stat -liberty` per submodule → `synth/area_permodule.txt` (each block is
  instantiated once under the top, so local areas sum to the design).
- **Sign-off (bonus):** OpenLane 2.3.10 via Nix, `synth/config.json`, CLOCK_PERIOD
  20.0 ns (MAS K3 = 50 MHz), SYNTH_HIERARCHY_MODE deferred_flatten (grape OOM lesson).
- **Clock target:** MAS §6 timing budget, K3 ≥ 50 MHz (20 ns period).
- Requirement source (project_instructions.md §7 / hw-ppa): a trade-off **discussion
  with a defined operating frequency**; OpenLane GDS sign-off is bonus, not a gate.

## 1. Yosys + sky130 Liberty — area and cell counts (fast gate)

Source: `synth/area.txt` (`make area`, flattened, Liberty-mapped).

| Metric | Value | Source line |
|---|---|---|
| Cells | **151,058** | `Number of cells` |
| Chip area | **1,634,516 µm² = 1.634 mm²** | `Chip area for module '\huffman_engine'` |
| Sequential fraction | **54.44 %** (889,783 µm²) | `used for sequential elements` |
| Flip-flops | 33,228 (`dfxtp_1` 10,791 + `edfxtp_1` 22,437) | cell histogram |

`ppa.cells = 151058`, `ppa.area_um2 = 1634516`. The design is **storage-dominated**:
over half the area is registers (the symtab + table register sets + length window,
uArch §5, ≈ 34 kbit of flops), matching the "control/storage-heavy comparator
cascade" characterisation.

### 1.1 Area by module (trade-off axis)

Source: `synth/area_permodule.txt` (non-flattened; hierarchical total 1,733,396 µm²
— ~6 % above the flattened 1.634 mm² because cross-module optimisation is disabled
in this attribution pass).

| Module | Area µm² | % of design | Seq. % | Role |
|---|---:|---:|---:|---|
| `huff_tables` | **1,163,561** | **67.1 %** | 61 % | symtab (1,728×10b) + 6 table register sets + active-set mux |
| `huff_regs` | **483,470** | **27.9 %** | 41 % | length window (6×288×5b = 8.6 kbit) + counters + config + FSM regs |
| `huff_builder` | 28,780 | 1.7 % | 71 % | PREFIX/FILL build datapath |
| `huff_decoder` | 22,420 | 1.3 % | **0 %** | 20×21b comparator cascade + priority encode (pure combinational) |
| `huff_aligner` | 14,643 | 0.8 % | 29 % | 64b window + barrel shifter + FIFO |
| `huffman_engine` (glue) | 10,460 | 0.6 % | 34 % | top wiring, stall fan-out, SVAs |
| `axi_lite_if` | 3,278 | 0.2 % | 89 % | AXI4-Lite → register bus |
| `huff_deflate` | 2,919 | 0.2 % | 35 % | DEFLATE resolve + extra bits |
| `huff_out` | 2,506 | 0.1 % | 68 % | output skid, withdrawal |
| `huff_selector` | 748 | <0.1 % | 51 % | 50-symbol selector FSM |
| `huff_ctrl` | 611 | <0.1 % | 43 % | invocation FSM |

**Finding.** `huff_tables` + `huff_regs` = **95 % of the design**, and both are
storage. The actual decode logic — the comparator cascade `huff_decoder` — is only
**1.3 %** and carries **zero** sequential area. This is the whole PPA story of a
canonical-Huffman engine: it is a memory, not a datapath.

## 2. Trade-off study (design points)

Knob: **how the per-table/symbol storage is realised** — the dominant area axis
identified in §1.1. The RTL bakes six table register sets + a flop symtab
(`SYMTAB_DEPTH = 1728`, `huff_tables.sv`) for the signed-off **0-cycle selector
switch** (PRD-F1, uArch §3.3); the K1 = 1.0068 throughput is invariant across these
points (storage organisation, not the decode loop). Point 1 is fully measured;
points 2–3 are projections from the measured per-module storage area.

| # | Design point | Area | K1 cyc/sym | K5 (≤1.0 mm²) | Verdict |
|---|---|---:|---:|:--:|---|
| **1** | **As-built:** flop symtab + 6 register sets, sky130_fd_sc_hd | **1.634 mm²** (measured, §1) | **1.0068** (`decode_model.py`) | **miss** (1.63×) | signed-off; 0-cycle switch, no macros needed |
| 2 | Symtab (17.3 kbit) + length window (8.6 kbit) in **SRAM macros** | ≈ **0.75 mm²** std cells + 2 SRAMs (proj.) | 1.0068 (symtab read already a registered C1 stage) | **meets** | needs an SRAM compiler — **not in the sky130 HD open flow** |
| 3 | **2** table register sets instead of 6 (re-derive on switch) | ≈ 1.53 mm² (proj.; −~0.1 mm² of table-set flops) | **>1.1** (build stall per 50-symbol switch) | miss | **rejected** — breaks the K1 KPI and PRD-F1 0-cycle switch |

### 2.1 K5 soft-ceiling discussion (1.0 mm²)

The PRD carries a **soft** K5 area target of 1.0 mm²; the design lands at **1.634 mm²
(1.63×)**. This is expected and it is a *storage* miss, not a logic miss:

- **54.44 % of the area is sequential** (889,783 µm²). The combinational decode
  datapath is negligible (`huff_decoder` 1.3 %, 0 % seq).
- The storage is (uArch §5): symtab **1,728 × 10 b = 17.3 kbit**, length window
  **6 × 288 × 5 b = 8.6 kbit**, six table register sets (limit_la/first_code/base/
  eob) **≈ 6.4 kbit**, count bins **1.1 kbit** — ≈ **34 kbit of flip-flops**. At
  sky130 HD (~20–30 µm² per flop bit) that alone is ~0.7–1.0 mm².
- **What it would take to hit 1.0 mm²:** move the symtab (17.3 kbit) and the length
  window (8.6 kbit) — the two large, single-port-friendly arrays — out of standard-
  cell flops into **compiled SRAM macros** (point 2). On a target with an SRAM
  compiler or FPGA BRAM they become one/two small dense blocks and the standard-cell
  budget drops to the decode + control + the six table register sets (kept as flops
  for the 0-cycle active-set mux), projecting **under 1.0 mm²**.
- **Why we did not:** **sky130_fd_sc_hd in this open flow has no BRAM/SRAM macro** —
  the flow is standard cells only, so every array is flops. The 1,728×10b symtab +
  6×20-entry table params therefore consume the standard-cell budget by construction.
  K5 is a *soft* ceiling for exactly this trade-off discussion; the achievable path
  (SRAM macros) is documented above and is the concrete area-reduction follow-up.

## 3. OpenLane 2 — sign-off attempt (bonus)

OpenLane 2.3.10 (`synth/config.json`, CLOCK_PERIOD 20.0 ns, deferred_flatten) was given
**one time-boxed attempt** on this 24 GB WSL host. Unlike grape (which OOM'd in synthesis
until `deferred_flatten` and then hit OpenROAD **GRT-0607** three times), huffman at 151 k
cells is ~4× smaller: **synthesis completed cleanly**, all yosys/netlist checkers passed,
and the flow reached **OpenROAD pre-PnR STA** and **global placement** before it was killed.
The one config adjustment was `RUN_LINTER: false` — OpenLane's bundled Verilator 5.018
rejects a `BLKLOOPINIT` construct (delayed array write in a for-loop) that the project's
pinned Verilator ≥ 5.036 accepts (the RTL-stage `make lint` is clean); the design RTL was
unchanged.

**Why it was closed before GDS.** The **pre-PnR STA is already decisive**: the design misses
20 ns by a wide margin, and global placement was **non-convergent** — 2,200+ Nesterov
iterations with the overflow stuck at ~0.29 (needs < 0.1) while the timing-driven resizer
bloated HPWL from 5→8.8×10⁹ upsizing cells to chase the critical path. That is exactly the
repair-bloat → congestion trajectory that drove grape into GRT-0607; pushing routing would
sink hours for a near-certain router failure. Per project_instructions.md §7 (OpenLane
sign-off is **not** required — a trade-off discussion with a defined operating frequency
suffices), the run is closed on the real STA below.

### 3.1 Operating frequency — OpenROAD pre-PnR STA

Worst setup slack at the 20 ns target, `Fmax = 1/(period − ws)`. Source:
`synth/runs/signoff2/08-openroad-staprepnr/<corner>/max.rpt`.

| Corner | Worst setup slack | Achievable period | **Fmax** |
|---|---:|---:|:--:|
| **nom_tt_025C_1v80** (sign-off) | **−91.886 ns** | 111.886 ns | **≈ 8.9 MHz** |
| nom_ss_100C_1v60 (slow) | −172.237 ns | 192.237 ns | ≈ 5.2 MHz |
| nom_ff_n40C_1v95 (fast) | −53.062 ns | 73.062 ns | ≈ 13.7 MHz |

- **Caveat:** these are **pre-placement** STA (ideal clock network, estimated/unbuffered
  net RC), so they are *optimistic on the clock tree* and would drop after CTS + routing —
  ~8.9 MHz (tt) is an upper bound on this netlist, not a signed-off number.
- **Critical path:** startpoint `u_regs._86212_` (a `huff_regs` count/length register) →
  endpoint `u_tab._163476_` (a `huff_tables` set flop), data arrival **111.5 ns** through a
  `sky130_fd_sc_hd__mux2` chain in `u_tab` — i.e. the **canonical-table build recurrence +
  the wide symtab/table-set write mux**, *not* the decode comparator cascade. This matches
  §1.1: the area *and* the timing are dominated by `huff_tables`/`huff_regs` storage.
- **Fmax vs K3 (≥ 50 MHz).** The netlist misses 50 MHz by ~5.6× (tt). The documented RTL
  follow-up is to **pipeline the table build** (the first_code/base recurrence over lengths
  1..20) and **register the symtab read-mux path** into stages — a datapath change deferred
  to a future RTL iteration, not a PPA-stage fix. This is the same block (`huff_tables`) that
  dominates area, so the area and timing follow-ups coincide.

### 3.2 Power

- **Not a signoff figure.** OpenROAD `report_power` at pre-PnR (tt) reports ≈ **0.90 W**
  (`08-openroad-staprepnr/nom_tt_025C_1v80/power.rpt`: 92 % combinational), but with **no
  clock tree and default switching activity** this is indicative only — a real power number
  needs post-CTS/GDS, which the time-boxed run did not reach. Per the task, **no power number
  is invented**; `ppa.power_mw` is left unrecorded (0).
- **Die shot:** not obtained — no GDS was produced (run closed before detailed routing).

### 3.3 Honest status summary

| Deliverable | Status |
|---|---|
| Yosys+Liberty area + cell counts | **done** (§1: 151,058 cells, 1.634 mm²) |
| OpenLane synthesis | **done** (clean; passed all checkers) |
| Fmax | **pre-PnR STA only** — ≈ 8.9 MHz tt (§3.1); post-CTS not reached (placement non-convergent) |
| Area (OpenLane placed) | not reported — use Yosys 1.634 mm² (§1) |
| Power / die shot | **not obtained** (no GDS; not §7-required, not invented) |

## 4. Report §7 mapping

| project_instructions.md §7 bullet | This document |
|---|---|
| Performance / area / power trade-offs | §1 (1.634 mm², 151,058 cells), §1.1 (per-module), §2 (trade-off table + K5), §3 (OpenLane/STA operating frequency) |

Performance (K1 = 1.0068 cyc/sym) is carried in `docs/uarch.md §7` and the speedup in
`docs/integration.md §3`; Fmax operating point in §3 here.
