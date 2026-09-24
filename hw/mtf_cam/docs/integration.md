# mtf_cam — Integration (stage 10)

HW/SW interface of the finished accelerator: the Python driver model, the software patch
points in the pyflate/bzip2 decode, and the cycle-accurate speedup estimate against the
measured baseline. Numbers are cited by file; the operating frequency from `docs/ppa.md`
(post-CTS STA, ≈ 37.5 MHz) is carried through honestly alongside the PRD-target 50 MHz.
Reference templates: `hw/grape_pipeline/docs/integration.md`, `hw/huffman_engine/docs/integration.md`.

## 1. HW/SW interface (APIs, driver, MMIO, DMA)

- **Transport (MAS §1/§5, ADR-0001):** control is **memory-mapped** over one 4 KB AXI4-Lite
  window; the two data paths are **AXI4-Stream moved by DMA** — `s_sym` (symbol beats in) and
  `m_l` (L-vector bytes out, W = 8 lanes). mtf_cam is therefore **not MMIO-only**: registers
  carry the used map, limits, doorbell and counters; the L-vector never crosses the register
  bus. In the chained `pyflate_accel` wrapper `s_sym` is fed on chip from `huffman_engine.m_sym`
  (no DMA on the symbol side); standalone, `s_sym` is a DMA replay of the golden symbol trace.
  Per block ≈ **14 AXI-Lite transactions** (8 used-map words + ~6 control/counter words) ≈ **56
  bus cycles** (MAS §5) — < 0.04 % of the compute; the L-vector streams out concurrently.
- **Driver model:** `driver/mtf_cam_driver.py`.
  - Register offsets/fields generated one-for-one from MAS §4 — `driver/check_regmap.py` parses
    `docs/mas.md` §4 **and** the `rtl/mtf_regs.sv` word decode and verifies them: **0 differences**
    (18 register rows incl. the `USED[w]` window; `ID_VALUE = 0x4D544631` ASCII `MTF1`).
  - `MMIO` abstract async bus (`read32`/`write32`); `AccelDriver` base (`status`, `start`,
    `abort`, `wait_done`, `clear`, `read_counters` — the ADR-0005 control-plane contract);
    `MtfDriver` with the MAS §6 API (`configure(used_map, symbol_limit, bytes_limit)`, `caps`,
    `load_used_map`, `read_list` via DBG_SEL/DBG_DATA, `start`, `wait_done`, `read_counters`,
    `expand_block(symbols, used_map)`). `used_map` accepts 256 bools, a 32-byte bitmap, or the
    list of present byte values.
  - `ModelBus`: a standalone functional + cycle model of the register block (no RTL, no
    simulator). It honours the invocation protocol (doorbell → BUSY → DONE, W1C,
    ERR_PARAM/ERR_BUSY), and for an accepted block computes the L-vector, counters and BYTES_OUT
    through the **frozen golden predictor** `golden/list_model.expand` (MAS §9 F15) and `CYCLES`
    from `golden/list_model.cycles` (the signed-off cycle model, K3). It lets the driver + speedup
    model run under `asyncio`, no Verilator.
  - `SimBackend`: the RTL-cosim adapter — it drives the **same register constants** through the
    pyuvm `axi_lite_agent` sequencer (`hw/common/tb/axi_lite_agent.py`) so the identical driver
    runs against the DUT in cocotb; the L-vector is checked on the `m_l` sink by the scoreboard.
- **Tests:**
  - `driver/test_driver.py` (standalone, `python3 hw/mtf_cam/driver/test_driver.py`) →
    **ALL 5 DRIVER-MODEL TESTS PASS**: register-map consistency (0 diffs), ID/CAPS
    (`0x01000808` = W 8 / D 8 / N_LIST 256), a full `expand_block` of the smoke block
    (`used {65,66,67,68}`, `RUNA,RUNA,MTF,MTF,MTF,EOB` → L-vector `65,65,65,66,67,66`,
    BYTES_OUT = 6, SYMBOLS_IN = 6, MAX_RUN = 3, INIT_CYCLES = 4, DONE then W1C-cleared), the
    ERR_PARAM reject (N_USED = 0) and the ERR_BUSY (config-write-while-BUSY) paths.
  - `tb/test_driver_model.py` (RTL cosim, `make -C hw/mtf_cam sim MODULE=test_driver_model`) →
    the same driver drives the smoke block **through the DUT** via `SimBackend`; the scoreboard
    reports `PASS: compared 6 items over 1 block(s), 0 mismatches (golden=list_model.expand)` and
    the driver reads back BYTES_OUT = 6, SYMBOLS_IN = 6, MAX_RUN = 3. It is a **separate cocotb
    module** so the default `make -C hw/mtf_cam sim` stays **16/16** and does not collide with the
    directed `test_driver` already in `tb/test_mtf_cam.py`.

## 2. Software changes (pyflate/bzip2 decode)

`benchmarks/bm_pyflate/run_benchmark.py` decodes `data/interpreter.tar.bz2`. The bzip2 symbol
loop runs Huffman decode → **move-to-front → RUNA/RUNB run expansion** to produce the L-vector
(`report_pyflate.txt:20,36`). mtf_cam owns the move-to-front + run-expansion stage (PRD §4 HW/SW
split, prd.md:14 — it replaces `move_to_front` and the run/MTF part of `decode_huffman_block`,
`dev/pyflate/t0_stock.py:411-429,274`). Patch points:

- **Standalone:** software parses the block's symbol map to the 256-bit `used` map, then calls
  `MtfDriver.expand_block(symbols, used)` once per bzip2 block (the symbols are the
  `huffman_engine` beat values 0/1 runs, 2..N_USED MTF, N_USED+1 EOB). The driver programs
  `USED[0..7]` + `SYMBOL_LIMIT`/`BYTES_LIMIT`, doorbells, waits for DONE and returns the L-vector
  (== BYTES_OUT). This replaces the pure-Python `move_to_front` + run-expansion in the symbol loop.
- **Chained (`pyflate_accel`, the intended on-chip path, MAS §1):** the wrapper driver
  `decode_bzip2_block(data, start_bit, lengths, selectors, used)` doorbells `mtf_cam` **first**
  then `huffman_engine`; `huffman_engine.m_sym` feeds `mtf_cam.s_sym` on chip, so both the Huffman
  decode and the MTF stage leave software in one call.
- **Stays in Python** (the `1 − f` residual): the `used`-map parse (it writes the 256-bit map),
  the **inverse BWT** (ADR-0003, non-target), **RLE4** expansion and **MD5/CRC**, plus the pyperf
  harness (prd.md:15-16).
- **Marshalling per block:** ~14 AXI-Lite writes/reads for config + counters (≈ 56 cycles,
  MAS §5); the L-vector (336,184 bytes for the benchmark block) streams out on `m_l` by DMA,
  overlapped with the decode — not on the serial critical path.

## 3. Speedup estimate (vs `results/baseline_pyflate_stats.txt`)

Inputs, all cited by file:

| Symbol | Value | Source |
|---|---|---|
| Baseline `T` (original Python) | **1.12 s** (Mean ± 0.01 s) | `results/baseline_pyflate_stats.txt` ("Mean +- std dev: 1.12 sec") |
| Accelerated fraction `f` (MTF stage) | **0.1344** (`move_to_front` self-time share) | `results/profile_functions.txt` (pyflate original, `move_to_front` 13.44 %); `results/pyspy_pyflate_stock_full.svg`; `report_pyflate.txt:75` |
| HW cycles / benchmark block | **158,441** (148,271 symbols, K3 = 1.0686) | `tb/test_mtf_cam.py::test_full_benchmark` (DUT `CYCLES`); model 157,560 / K3 1.063 in `docs/ppa.md §3.1`, `docs/testplan.md §2` |
| **Achievable clock (Fmax)** | **≈ 37.5 MHz** (post-CTS STA, tt; 27 ns constraint met, +0.31 ns slack) | `docs/ppa.md §3.1` (`synth/evidence/tight27_ws.max.rpt`) |
| PRD-target clock | 50 MHz (20 ns) | `docs/prd.md` K4; `docs/mas.md §3` |
| Driver/bus overhead | ≈ 56 bus cyc/block; `m_l` DMA overlapped | `docs/mas.md §5` |

HW compute time `t_hw = 158,441 / f_clk`; new total `= (1 − f)·T + t_hw + overhead`; Amdahl
`S = T / new_total = 1 / ((1 − f) + t_hw/T)`.

At the achievable **37.5 MHz**: `t_hw = 158,441 / 37.5e6 = ` **4.225 ms**; bus overhead
`56 / 37.5e6 = ` 1.5 µs (negligible).

| Clock | `t_hw` | Non-accel (86.56 % of T) | New total | **Speedup S** | Ideal 1/(1−f) |
|---|---:|---:|---:|:--:|:--:|
| **37.5 MHz (achievable)** | **4.225 ms** | 969.5 ms | 973.7 ms | **≈ 1.150×** | 1.155× |
| 50 MHz (PRD target) | 3.169 ms | 969.5 ms | 972.7 ms | **≈ 1.151×** | 1.155× |

- **Ideal bound** `1/(1 − f) = 1.155×` (infinite-speed accelerator; the 86.6 % software residual —
  Huffman decode, iBWT, RLE4, MD5 — caps it). At either clock the accelerator sits **right at the
  bound**: `t_hw` (≈ 4 ms) is negligible against the ~150 ms of software move-to-front it removes.
- **Key finding — fraction-bound, clock-insensitive.** Like `huffman_engine` and unlike `grape`
  (compute-bound), mtf_cam standalone is **Amdahl-fraction-bound**: S moves only 1.150 → 1.151
  between 37.5 MHz and 50 MHz, so the ppa timing miss (37.5 vs 50 MHz, ppa.md §3.1) **does not gate
  the end-to-end result** — the fraction `f` does.
- **Sensitivity — `f`:** the profiler cleanly attributes only `move_to_front` (13.44 %); the
  RUNA/RUNB run-expansion mtf_cam also owns is folded into `decode_huffman_block` self-time and not
  separately broken out (report_pyflate.txt:36). Crediting part of it pushes `f → ~0.16`
  (ideal 1.19×, S ≈ 1.19×); the strict cProfile self-time (9.3 %, prd.md:24) gives `f = 0.093`
  (ideal 1.10×, S ≈ 1.10×). Honest range **~1.10–1.19×**, central **1.15×**. The result is
  fraction-driven.
- **Sensitivity — bus latency:** doubling the per-transaction cost (4 → 8 cyc, ~112 bus cyc/block)
  adds ~3 µs at 37.5 MHz — negligible vs the ~970 ms software residual; insensitive.
- **Sensitivity — DMA bandwidth:** `t_hw` already assumes the `m_l` sink sustains **≥ W = 8
  bytes/cycle** (≈ 300 MB/s at 37.5 MHz), so the 336,184-byte L-vector drains inside the 158,441
  decode cycles (as `test_full_benchmark` does with an always-ready sink). If the DMA sink stalls
  to W/2 bytes/cycle the drain-bound portion roughly doubles `t_hw` to ~8.4 ms — S still
  ≈ 1.145×. Bandwidth-insensitive.

### Reconciliation with PRD K5 (≈ 25×)

PRD K5 (`prd.md:37`) is a **stage-level** target, not the end-to-end number: the HW MTF-stage time
vs the **isolated original MTF** time — "157,560 cycles @ 50 MHz = 3.15 ms vs the original MTF alone:
80.4 ms (FINDINGS §1e micro-benchmark) / 110 ms `move_to_front` tottime (cProfile) ⇒ ≈ 25×".

- **At 50 MHz** with the DUT 158,441-cycle block (3.169 ms): stage speedup = 80.4 / 3.169 =
  **25.4×** — **meets K5 ≈ 25×** (34.7× against the 110 ms cProfile baseline).
- **At the achievable 37.5 MHz** (4.225 ms): stage speedup = 80.4 / 4.225 = **19.0×** (80.4 ms
  micro-bench) or 110 / 4.214 = **26.1×** (cProfile) — still ~20–26×, in the K5 band.
- **Consistency with the end-to-end S:** a ~25× stage speedup on a 13.44 % slice gives, by Amdahl,
  `1/((1 − 0.1344) + 0.1344/25) = ` **1.148×** — i.e. the whole-benchmark **S ≈ 1.15×** and the
  stage-level **K5 ≈ 25×** are the *same* result expressed at two altitudes. K5 is large because
  the stage itself is ~25× faster in hardware; S is small because that stage is only 13.4 % of the
  pyflate benchmark.
- **Bigger picture:** chaining `mtf_cam` with `huffman_engine` on chip (`pyflate_accel`, MAS §1)
  removes both the Huffman decode (49.6 %, huffman integration §3) **and** the MTF stage (13.4 %)
  from software — combined `f ≈ 0.63`, ideal ceiling **≈ 2.7×** — the intended two-block pipeline.

> **How this relates to the delivered software (added 2026-09-19).** The speedups in this section
> are projections against *original* Python. Against the delivered Python + Rust path (170.01 ms) the
> comparison is made at the matched boundary instead: the `huffman_engine → mtf_cam` chain,
> co-simulated in 159,303 cycles (≈ 4.25 ms at the shared 37.5 MHz clock), against the Rust
> kernel's 3.30 ms — end to end a tie (≈ 171 ms). See `hw/docs/hardware_report.md §3.8`.

## 4. Rubric map (project_instructions.md §7)

| §7 bullet | File / section |
|---|---|
| Hardware description (Verilog/SV) | `rtl/*.sv` (mtf_cam, mtf_list, mtf_ctrl, mtf_run, mtf_expand, mtf_pack, item_fifo, mtf_regs) + `../common/rtl/axi_lite_if.sv` |
| Inputs & outputs, widths, interfaces, frequency | `docs/mas.md §2` (I/O table + widths), §3 (clock/reset); Fmax `docs/ppa.md §3.1` (37.5 MHz) |
| Hardware architecture (datapath + control) | `docs/uarch.md` (CAM, FSMs, item FIFO, packer, timing budget) |
| HW/SW interface (APIs, drivers, MMIO, DMA) | `docs/mas.md §5/§6` + `driver/mtf_cam_driver.py` (this stage; §1 above) |
| Acceleration justification + estimate | `docs/prd.md` §KPI (K5) + `docs/integration.md §3` (Speedup) |
| Block diagram | `docs/mas.md §7` / `docs/block_diagram.svg` |
| Performance / area / power trade-offs | `docs/ppa.md` (Yosys 0.187 mm², 18,814 cells; W-sweep trade-off; post-CTS STA 37.5 MHz, 10.2 mW) |

## 5. Text for `report_pyflate.txt` §5

> The bzip2 move-to-front stage is offloaded to `mtf_cam`, a memory-mapped move-to-front +
> RUNA/RUNB run-expansion accelerator (18,814 sky130 cells, 0.187 mm²; docs/ppa.md). Software
> writes the block's 256-bit used map and rings a doorbell over a 4 KB AXI4-Lite window; the
> symbol beats arrive on an AXI4-Stream input (`s_sym`, on chip from `huffman_engine` or by DMA
> replay) and the L-vector streams out on `m_l` by DMA. The driver model
> (`hw/mtf_cam/driver/mtf_cam_driver.py`) is verified register-for-register against the
> architecture spec **and** the RTL decode (0 differences), and drives a full block both through a
> golden-backed register model and — via `SimBackend` — through the RTL in cocotb (scoreboard:
> 0 mismatches, BYTES_OUT/SYMBOLS_IN/MAX_RUN read back exact). The engine sustains 1 symbol/cycle
> through a 256-entry shift-register CAM (K3 = 1.07 cyc/sym; a 148,271-symbol block in 158,441
> cycles). Against the 1.12 s original-Python baseline, of which **13.44 %** is `move_to_front`
> (results/profile_functions.txt), Amdahl gives **≈ 1.15× end-to-end** — essentially the ideal
> 1.155× bound, because the ~4 ms of hardware MTF is negligible against the ~150 ms of software
> move-to-front it removes. At the **stage** level this is the PRD-K5 ~25× (3.17 ms @ 50 MHz vs
> 80.4 ms original MTF); the two figures are the same result at different altitudes. Like the Huffman
> engine the speedup is **clock-insensitive** (1.150× at 37.5 MHz vs 1.151× at the 50 MHz target):
> it is limited by the software residual (Huffman decode, iBWT, RLE4, MD5), not by timing closure.
> Chaining `mtf_cam` behind `huffman_engine` on chip (`pyflate_accel`) removes both stages from
> software, lifting the accelerated fraction to ~0.63 and the ceiling to ~2.7×.
