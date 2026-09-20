# grape_pipeline — Integration (stage 10)

HW/SW interface of the finished accelerator: the Python driver model, the software
patch points in the nbody benchmark, and the cycle-accurate speedup estimate against the
measured baseline. Numbers are cited by file; the achievable clock from `docs/ppa.md`
(post-CTS STA) is carried through honestly alongside the PRD-target clock.

## 1. HW/SW interface (APIs, driver, MMIO, DMA)

- **Transport:** MMIO only, no DMA, no streams (MAS §5 / ADR-0001). A 4 KB AXI4-Lite
  window; per invocation ≈ 150 transactions ≈ 600 bus cycles (MAS §5), < 0.03 % of the
  compute time.
- **Driver model:** `driver/grape_pipeline_driver.py`.
  - Register offsets/fields generated one-for-one from MAS §4 — `driver/check_regmap.py`
    parses `docs/mas.md` §4 and verifies them: **0 differences** (15 register rows +
    `ID_VALUE = 0x47525031`).
  - `MMIO` abstract bus (`read32`/`write32`); `AccelDriver` base (`status`, `start`,
    `abort`, `wait_done`, `clear`, `counters` — shared ADR-0005 contract); `GrapeDriver`
    with the MAS §6 API (`load_bodies`, `load_pairs`, `configure`, `read_bodies`,
    `advance(dt, n, bodies, pairs)` in the benchmark's own signature — pairs resolved to
    indices by object identity).
  - `ModelBus`: a standalone functional + cycle model of the register block (no RTL, no
    physics) that honours the invocation protocol (doorbell → BUSY → DONE, W1C,
    ERR_PARAM/ERR_BUSY) and returns `CYCLES = K1·NSTEPS` with the measured **K1 = 124**
    (docs/ppa.md trade-off point 2). It lets the driver + speedup model run without a
    simulator. Bit-exact physics lives in the frozen golden model + RTL; wiring the same
    register constants to the pyuvm `axi_lite_agent` (SimBackend) is the RTL-cosim
    extension.
- **Tests:** `driver/test_driver.py` — `python3 hw/grape_pipeline/driver/test_driver.py`
  → **ALL 4 DRIVER TESTS PASS**: register-map consistency (0 diffs), ID/FP round-trip,
  a full `advance(0.01, 20000)` invocation (**cycles = 2,480,000 = 124 × 20000**,
  steps_done = 20000, DONE then W1C-cleared), and the ERR_PARAM reject path.

## 2. Software changes (nbody benchmark)

`benchmarks/bm_nbody/run_benchmark.py` executes the whole hot kernel `advance(dt, n)`
(`run_benchmark.py:74-93`) — HW per the PRD HW/SW split (prd.md §4, `advance()` row = **HW**).
Patch point:

- one `GrapeDriver.advance(dt, n, SYSTEM, PAIRS)` call replaces the pure-Python
  straight-line `advance()`; `SYSTEM`/`PAIRS` are the existing body lists and pair tuples,
  so `report_energy()` / `offset_momentum()` observe the same objects (identical to the
  software contract the partial-eval optimisation already relies on).
- **Stays in Python:** `report_energy()`, `offset_momentum()`, the loop harness (pyperf) —
  the ~5 % residual below.
- **Marshalling per invocation:** 70 body words + 10 pair words + 4 config words in, 60
  state + 3 counter words out ≈ 150 AXI-Lite transactions (MAS §5); **once per 20 000-step
  invocation**, so negligible against the compute.

## 3. Speedup estimate (vs `results/baseline_nbody_stats.txt`)

Inputs, all cited:

| Symbol | Value | Source |
|---|---|---|
| Baseline `T` (original Python) | **231.20 ms** (mean ± 8 ms; median 229 ms) | `results/baseline_nbody_stats.txt` (canonical VM run `vm_canonical_20260910_2c8c754`) |
| Accelerated fraction `f` | **0.95** (doubly-nested advance loop) | `benchmarks/bm_nbody/run_benchmark.py:71` header comment; PRD §4 (advance = HW) |
| HW cycles / invocation | **2,480,000** (124 cyc/step × 20 000) | `driver/test_driver.py` (K1 = docs/ppa.md point 2; `test_full_benchmark`) |
| PRD-target clock | 50 MHz | prd.md K-table; mas.md §3 |
| **Achievable clock** | **19.46 MHz** (post-CTS STA, parallel-prefix netlist) | `docs/ppa.md` Addendum (2026-09-14); `synth/runs/grape_prefix2/35-openroad-stamidpnr-1/ws.max.rpt` |
| Driver/bus overhead | ≈ 600 bus cyc/invocation (< 0.03 %) | mas.md §5 |

> **Baseline note.** `T` is the pyperf **mean** (231.20 ms), matching `report_nbody` §1 and
> the canonical VM suite. The **median** is 229 ms (what `prd.md`/`STATUS.json` quote for the
> KPI check); the two differ only by mean-vs-median on a right-skewed distribution
> (`baseline_nbody_stats.txt:16-19`). Speedups here use the mean; using the median moves every
> `S` below by ≈ 0.8 %.

> **Clock note.** The achievable clock is **19.46 MHz**, measured post-CTS on the
> **parallel-prefix** accumulate netlist (`grape_prefix2`, docs/ppa.md Addendum 2026-09-14).
> The earlier **11.15 MHz** figure was the *pre-rewrite* linear-scan netlist (`grape_relaxed`)
> whose critical path was the accumulate issue picker; the prefix rewrite dropped that path out
> of the critical path (bit-exact, K1 = 124 unchanged) and is superseded here. 11.15 MHz is kept
> only as history in `docs/ppa.md`.

HW compute time `t_hw = 2.48e6 / f_clk`; new total `= (1−f)·T + t_hw`; Amdahl `S = T / new_total`.

| Clock | `t_hw` | Non-accel (5 % of T) | New total | **Speedup S** | KPI K3 (≥ 4×) |
|---|---|---|---|---|---|
| 50 MHz (PRD target) | 49.6 ms | 11.56 ms | 61.16 ms | **3.78×** | ~ meets (4.45× at f = 0.99) |
| **19.46 MHz (achievable)** | **127.4 ms** | 11.56 ms | 139.0 ms | **≈ 1.66×** | **misses** |

- **Compute-only upper bounds** (residual → 0, the headline the report quotes): `t_hw` alone
  is 127.4 ms, so **231.20 / 127.4 = 1.81× vs the original** and **143.13 / 127.4 = 1.12× vs the
  143.13 ms optimized-Python tier** (`report_nbody` §1/§3). These bound `S` from above; the
  Amdahl rows include the 5 % residual.
- **Ideal bound** `1/(1−f) = 20×` (infinite-speed accelerator; the 5 % residual caps it).
- **Sensitivity — residual:** retaining 1–5 % of the original runtime gives **1.66–1.78×** at
  19.46 MHz (f = 0.99 → residual 2.3 ms → 1.78×; f = 0.95 → 1.66×). The conclusion is
  clock-driven, not residual-driven.
- **Sensitivity — `f` at target clock:** at 50 MHz, f = 0.99 gives **4.45×** (clears K3),
  f = 0.90 gives 3.3×.
- **Sensitivity — bus latency:** doubling the per-transaction cost (4 → 8 cycles ⇒ ~1,200
  bus cyc/invocation) adds ~60 µs at 19.46 MHz — negligible vs a 127 ms compute; the estimate
  is insensitive to the bus-latency assumption.

**Finding.** At the **PRD-target 50 MHz** the accelerator meets its intent (~3.8–4.5×,
clearing K3 ≥ 4× near the top of the `f` range). At the **achievable 19.46 MHz** — set now by
the **integrate-multiplier operand path** (`u_fsm → g_add[2].u_mul`, docs/ppa.md Addendum), the
new critical path after the prefix rewrite moved the old accumulate-picker path off-critical —
the accelerator is still **compute-bound (~1.66×, ~2.6× short of the target clock)** and does
not beat the 9.53 ms native-software tier. The documented, gating RTL follow-up is therefore to
**pipeline the integrate-multiply path** (the current limiter) to recover the clock toward
~45–50 MHz; K3 remains gated on timing closure, not on the interface. This is the same critical
path the latest PPA STA flags — the speedup story and the timing story point to one fix.

## 4. Rubric map (project_instructions.md §7)

| §7 bullet | File / section |
|---|---|
| Hardware description (Verilog/SV) | `rtl/*.sv` (grape_pipeline, grape_force_pipe, grape_accum, grape_step_fsm, fp64_*) |
| Inputs & outputs, widths, interfaces, frequency | `docs/mas.md` §2 (I/O table + widths), §3 (clock/reset) |
| Hardware architecture (datapath + control) | `docs/uarch.md` (pipeline, FSMs, memories, timing budget) |
| HW/SW interface (APIs, drivers, MMIO, DMA) | `docs/mas.md` §6 + `driver/grape_pipeline_driver.py` (this stage) |
| Acceleration justification + estimate | `docs/prd.md` §KPI + `docs/integration.md` §3 (Speedup) |
| Block diagram | `docs/mas.md` §7 / `docs/block_diagram.svg` |
| Performance / area / power trade-offs | `docs/ppa.md` (Yosys 4.075 mm², 584,454 cells; K1 trade-off table; post-CTS STA Fmax **19.46 MHz** parallel-prefix netlist, was 11.15 MHz linear-scan) |

## 5. Text for `report_nbody` §5

> The nbody `advance()` kernel is offloaded to `grape_pipeline`, a memory-mapped FP64
> pairwise-gravity accelerator (584,454 sky130 cells, 4.075 mm²; docs/ppa.md). Software
> programs the 5-body state and 10-pair list over a 4 KB AXI4-Lite window and rings a
> doorbell once per 20,000-step invocation; the driver model is
> `hw/grape_pipeline/driver/grape_pipeline_driver.py`, verified register-for-register
> against the architecture spec (0 differences) and against a full-invocation cycle model
> (2,480,000 cycles = 124 cyc/step × 20,000). Against the 231.20 ms original-Python baseline
> (mean; 95 % of it in advance), Amdahl gives **~3.8–4.5× at the 50 MHz design target**. The
> achievable clock from post-CTS static timing (the furthest the OpenLane 2 flow reached before
> the OpenROAD GRT-0607 router bug) is **19.46 MHz** on the parallel-prefix netlist
> (`grape_prefix2`; the earlier 11.15 MHz was the pre-rewrite linear-scan netlist), set now by
> the integrate-multiplier operand path — at which the end-to-end speedup is **~1.66×** and does
> not beat the 9.53 ms native-software tier. The concrete next step is to pipeline that
> integrate-multiply path to recover the clock toward the target; the architecture, driver and
> area are in place, and the speedup is gated on timing closure, not on the interface.
