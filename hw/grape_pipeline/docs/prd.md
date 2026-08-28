# grape_pipeline — PRD (Product Requirements Document)

Status: **approved** 2026-08-28 (PRD checkpoint). Stage 1 of `hw/FLOW.md`.
Vocabulary: `hw/CONTEXT.md`. Decisions: ADR-0001 (bus family, proposed), ADR-0002 (FP64 datapath +
tolerance oracle, accepted). Research: `research/hw-algorithms-nbody.md`.
Interview record: `prompt.txt` 2026-08-26/28 (grilling rounds Q1–Q23).

## 1. Purpose and workload slice

`grape_pipeline` is a memory-mapped pairwise-gravity accelerator that executes the entire
`advance(dt, n)` kernel of the pyperformance `nbody` benchmark (`benchmarks/bm_nbody/run_benchmark.py:74-93`):
for `n` consecutive steps, walk a software-defined pair list applying the gravitational velocity
update of every pair in FP64, then advance every position by `dt·v`. Software loads the body state
once, rings one doorbell, and reads the state back.

**Workload slice** (`results/`): one benchmark loop = `report_energy(); advance(0.01, 20000);
report_energy()`. Baseline 229 ms median per loop (`results/baseline_nbody_stats.txt:19`) ⇒
**11.45 µs = ~45,000 CPU cycles per step**. The profile is interpreter-bound: `_PyEval_EvalFrameDefault`
44.49 % self (`results/perf_report_nbody.txt:12`), `binary_op1` 5.75 % (l.123), `PyFloat_FromDouble`
3.78 % (l.142), `float_mul` 3.66 % (l.149), `list_ass_item` 2.83 % (l.154), `float_dealloc` 2.76 %
(l.159); the actual math (`__ieee754_pow_fma` 1.48 % l.212, `float_pow` 0.75 % l.343, `float_add`/`float_sub`
1.80/1.70 % l.189/194) is < 10 %. `report_energy` is 2 calls × 10 pairs per 200,000 pair-updates:
< 0.02 % of the loop. Hence the slice moved to hardware is **≈ 100 % of the timed region**
(Amdahl bound: everything except two `report_energy` calls and the driver's register traffic).

## 2. KPIs

| KPI | Unit | Requirement | Stretch | Measured by |
|---|---|---|---|---|
| K1 cycles per step (NSTEPS = 20000, benchmark bodies and pair list) | cycles/step | **≤ 128** | ≤ 64 | `CYCLES / STEPS_DONE` registers, `test_full_benchmark` |
| K2 clock frequency, sky130_fd_sc_hd tt_025C_1v80 | MHz | **≥ 50** | 100 (reported design point) | `make ppa` STA report |
| K3 end-to-end speed-up vs baseline, SoC-peripheral model (ADR-0001) | × | ≥ 4 (derived: 128 cycles × 20000 / 50 MHz = 51 ms + driver ≪ 1 ms vs 229 ms) | ≥ 18 @ 64 cycles, 100 MHz | `test_driver` cycle model + `docs/integration.md` |
| K4 numerical fidelity vs golden model | — | see PRD-F4/F5 | — | `test_full_benchmark` |
| K5 standard-cell area (no macros) | mm² | soft ceiling 1.0 (flagged, not gating) | — | `make area` (Yosys + Liberty), OpenLane |
| K6 power | mW | report only | — | OpenLane |

K1 rationale: at N = 5 the 10 pair forces of a step are independent (positions constant within the
step) but the 20,000 steps are serially dependent, so latency of the rsqrt chain + pair-list walk +
position update sets cycles/step; pipeline count does not (research §5). Budget (to be confirmed at
uArch; FP64 latencies from research §3 and FPnew-class units): pair-walk issue 10 + sub 3 +
square/sum 3×(4+4) ≈ 11 (pipelined, counted once) + sqrt ≈ 30 (SRT, 2 bits/cycle) + reciprocal ≈ 12
(ROM seed + 2 NR) + mul chain (d3, mag, b1m/b2m, 3 FMAs) ≈ 5×4 = 20 + ordered accumulate into the
same body's velocity (dependent adds, 10 pairs × 4) ≈ 40 worst case, overlapped with the pipeline
tail ≈ +12 + position update 4 + step FSM 4 ⇒ ≈ 106 cycles ≤ 128. The stretch (≤ 64) needs a
fused low-latency rsqrt and a 2-cycle accumulate. K1 may be revised at MAS if the register
interface changes the per-invocation model (Yuval, Q1). CYCLES definition: PRD-F14.

## 3. Functional requirements

| Id | Statement | Measurable KPI (unit) | Acceptance test | Source |
|---|---|---|---|---|
| PRD-F1 | One invocation executes exactly NSTEPS steps of `advance()` semantics: per step, every pair in pair-list order updates both bodies' velocities, then every body's position is advanced by dt·v. The ordering is *semantic* (defined by F2/F3 bit-exactness): pair forces may be computed concurrently and sub-phases pipelined as long as the committed state is identical. | STEPS_DONE == NSTEPS after completion (count) | `test_smoke`, `test_random` | `run_benchmark.py:74-93` |
| PRD-F2 | All arithmetic is IEEE-754 binary64, RNE, in the benchmark's operation order; r⁻³ᐟ² is computed as `s=sqrt(dsq); d3=dsq·s; rcp=1/d3; mag=dt·rcp`. | bit-exact match to `golden/emulation.py` on every state word, every step (0 mismatching bits); NaN rule: hardware emits the canonical quiet NaN 0x7FF8000000000000 and the scoreboard canonicalises the emulation model's NaNs before comparing, so any NaN matches any NaN and everything else is bit-exact | `test_smoke`, `test_random` (scoreboard) | ADR-0002, research §4 |
| PRD-F3 | Pair-list order is semantically significant: velocity accumulation happens in the programmed order. | bit-exact vs emulation model for ≥ 100 random pair orders | `test_random` | ADR-0002 |
| PRD-F4 | Energy fidelity: `report_energy` of the hardware final state vs of the golden model's final state after the same number of steps. | \|E_hw − E_gold\|/\|E_gold\| ≤ 1e-12 at completion of NSTEPS = 20000 (calibrated: 1.7e-14 at completion, 1.9e-14 max over 1000-step checkpoints ⇒ ≥ 50× margin) | `test_full_benchmark` | `golden/calibrate.py`, ADR-0002 |
| PRD-F5 | Trajectory fidelity: per-body deviation from the golden model, ‖r_hw − r_gold‖₂ / max(‖r_gold‖₂, 1e-300) and likewise for v. | ≤ 2e-9 (r) and ≤ 5e-11 (v) for every body **at completion of the NSTEPS = 20000 invocation** (hardware-observable); the same bounds at every intermediate step hold transitively by F2 bit-exactness + `golden/calibrate.py` (emulation vs golden, every step, run in the test's software preamble). A testbench-internal per-step probe is permitted but not required. Calibrated maxima 1.06e-10 / 2.64e-12 (≈ 19× margin). | `test_full_benchmark` | `golden/calibrate.py` |
| PRD-F6 | Capacity: 5 bodies and up to 10 pairs; `N_BODIES` and `N_PAIRS_MAX` are SystemVerilog parameters (defaults 5/10) but only the defaults are verified. | NBODIES = 5, NPAIRS ∈ [0,10] accepted (count) | `test_random`, `test_corner` | Q4/Q14 |
| PRD-F7 | Programmable per invocation: DT (FP64), NSTEPS (32-bit unsigned), per-body mass, positions, velocities, NPAIRS and the pair list (body indices i ≠ j). | all fields round-trip through the register interface (0 mismatches) | `test_driver`, `test_random` | Q13 |
| PRD-F8 | NSTEPS = 0 completes immediately with the state unchanged. | DONE asserted; 0 state words changed; CYCLES ≤ 4 | `test_corner` | Q9 |
| PRD-F9 | Doorbell, and any write to DT / NSTEPS / NPAIRS / pair list / state window, while BUSY is ignored and sets sticky ERR_BUSY (W1C). | ERR_BUSY = 1; running invocation's result bit-exact to the emulation model with the pre-doorbell configuration | `test_driver` | Q15 |
| PRD-F10 | State-window reads while BUSY return the last committed state (the state at the most recent accepted doorbell, completion or abort). | read value == committed value for 100 % of reads during BUSY | `test_driver` | Q16 |
| PRD-F11 | ABORT stops at the next step boundary: ABORTED flag and IRQ (as for DONE) within K1 + 8 cycles of the write; STEPS_DONE reports the completed steps; state committed at the boundary and bit-exact to the emulation model at that step count. ABORT while idle is a no-op; DOORBELL and ABORT in the same write: ABORT wins (no invocation starts). If the boundary reached is step NSTEPS, the invocation completes normally: DONE asserts and ABORTED does not. | ABORTED ≤ K1 + 8 cycles after the write; STEPS_DONE ≤ NSTEPS; state bit-exact at STEPS_DONE | `test_driver` | Q17 |
| PRD-F12 | Completion (DONE) or abort (ABORTED) is signalled by a status bit and one level interrupt; both bits and the interrupt are cleared by write-1-to-clear. All sticky flags (ERR_*, FP_*) are W1C and reset-cleared; an accepted doorbell does not clear them. | IRQ asserted within 2 cycles of DONE/ABORTED; deasserted the cycle after W1C | `test_driver` | Q6 |
| PRD-F13 | IEEE special values propagate (Inf/NaN, e.g. coincident bodies dsq = 0 → divzero+invalid, velocities NaN); sticky FP_INVALID / FP_DIVZERO / FP_OVERFLOW / FP_UNDERFLOW flags, W1C; no traps, no clamping. Reference: `golden/emulation.py` (numpy float64, returns the IEEE flag set). Subnormal handling per §8 open question. | flags == emulation-model flag set; state bit-exact vs emulation (F2 NaN rule) on dsq = 0, NaN and Inf inputs | `test_corner` | Q8 |
| PRD-F14 | Read-only CYCLES (64-bit) and STEPS_DONE (32-bit). CYCLES counts from the cycle the doorbell is accepted up to and including the cycle DONE/ABORTED asserts; it cannot overflow (2³² steps × K1 ≪ 2⁶⁴) and holds until the next accepted doorbell. | CYCLES == testbench count between those two edges (exact); STEPS_DONE == steps committed | `test_driver`, `test_full_benchmark` | Q18 |
| PRD-F15 | Reset (synchronous, active-low) in any state, including mid-invocation, returns the module to idle: every register takes its MAS reset value (all zero: state window, pair list, DT, NSTEPS, NPAIRS, CYCLES, STEPS_DONE, flags), so software must reload the state. | idle within 1 cycle after reset release; all registers read 0 | `test_driver` | Q9 |
| PRD-F16 | Control and state go through a 32-bit AXI4-Lite slave (FP64 as two words); the bus is verified by an independent protocol agent, not only through datapath results. | 0 AXI protocol violations (cocotbext-axi checks) across all tests | `test_driver` (all tests use the agent) | ADR-0001, Q5 |
| PRD-F17 | Parameter validation at the doorbell: any pair index ≥ N_BODIES or NPAIRS > N_PAIRS_MAX rejects the doorbell: sticky ERR_PARAM only — no BUSY, no DONE/ABORTED, no IRQ; state, CYCLES and STEPS_DONE hold their previous values (F14 counts accepted doorbells only). i == j is legal and behaves per F13 (dsq = 0). DT and NSTEPS accept any value (DT any FP64 incl. 0/negative/NaN; NSTEPS any 32-bit). | ERR_PARAM = 1 and 0 state words changed for every invalid case; every valid case bit-exact to the emulation model | `test_corner` | review R4 |

Calibration platform for F4/F5: Linux x86-64 (WSL2), glibc 2.39 `pow`, CPython 3.12.3
(`golden/calibrate.py` prints it); the golden side depends on libm (`pow` ≤ 0.54 ulp), so re-run the
calibration when the platform changes.

## 4. HW/SW split

| Function (benchmark) | HW / SW | Data crossing per invocation (bytes) |
|---|---|---|
| `offset_momentum` (once per run) | SW | — |
| `report_energy` (2 × per loop) | SW (reads state back) | 240 B state read-back |
| body state load: 5 × (3 pos + 3 vel + 1 mass) × 8 B | SW → HW | 280 B |
| pair list: 10 × (i, j) | SW → HW | 40 B (one 32-bit word per pair) |
| DT, NSTEPS, doorbell | SW → HW | 16 B |
| `advance()`: pair loop, r⁻³ᐟ², velocity update, position update | **HW** | — |
| status/IRQ, CYCLES, STEPS_DONE | HW → SW | 16 B |
| Barnes–Hut / FMM tree walk producing pair lists at large N (stretch) | SW | — |

Per invocation ≈ 590 B ≈ 150 32-bit AXI-Lite transactions. Assumptions for K3 (inputs to the
`test_driver` cycle model, all to be replaced by measurements): ~4 bus cycles per AXI-Lite
transaction (to be measured with cocotbext-axi at MAS) ⇒ ≈ 600 bus cycles, < 0.03 % of a
2.56 M-cycle invocation; the driver's Python-side cost (~150 MMIO accesses from CPython, plus the
two `report_energy` calls) is modelled at ≤ 1 ms, and the host CPU is taken as the baseline
machine (229 ms measured there), i.e. speed-up = 229 ms / (HW time + driver time). Invoking per step (NSTEPS = 1) would make
the bus traffic ~5× the compute — recorded as an anti-pattern for the report, allowed by PRD-F7.

## 5. Interfaces (PRD level; detail in MAS)

- Bus: 32-bit AXI4-Lite slave (ADR-0001). Register groups: control (DOORBELL, ABORT, DT, NSTEPS,
  NPAIRS), status (BUSY, DONE, ABORTED, ERR_BUSY, ERR_PARAM, FP flags; W1C IRQ), counters (CYCLES, STEPS_DONE),
  body-state window (5 × 7 × 64 bit), pair list (10 × 32 bit). Exact offsets, reset values and
  access types: MAS.
- One clock domain; synchronous active-low reset. Clock target K2.
- Interrupt: one level-sensitive output.
- Data volume: §4.
- System model: peripheral on the CPU's SoC bus (Q7); PCIe is discussed in the report only.

## 6. Non-goals

- `report_energy`, `offset_momentum`, benchmark orchestration — software.
- Softening ε, jerk / Hermite integrators, other time steppers — not supported.
- Barnes–Hut / FMM in hardware — software may feed the pair list (stretch demo, report discussion).
- GRAPE-style FP32/LNS pairs with wide fixed accumulate — PPA comparison variant only (ADR-0002).
- Replicated pipelines — latency-bound at N = 5; a single pair pipeline.
- Bit-exact reproduction of CPython's libm `pow` — not a target (ADR-0002).
- Live (mid-step) state snooping, DMA, 64-bit bus — not required (Q16, ADR-0001).

## 7. Acceptance tests (names reused by `hw-dv-testplan`)

| Test | Checks | Requirements |
|---|---|---|
| `test_smoke` | 1 step, benchmark bodies and pairs, bit-exact vs emulation model | F1, F2 |
| `test_random` | random bodies (magnitudes 1e-5…1e2), random pair lists and orders, NPAIRS ∈ [0,10], DT ∈ [1e-4, 1], NSTEPS ≤ 64; bit-exact vs emulation model | F1, F2, F3, F6, F7 |
| `test_full_benchmark` | NSTEPS = 20000 on the benchmark state; K1 from CYCLES/STEPS_DONE; F4 energy oracle; F5 per-step bounds vs golden model | K1, F4, F5, F14 |
| `test_driver` | register protocol through cocotbext-axi: doorbell, BUSY reads, writes while BUSY (ERR_BUSY), ABORT (idle, running, same cycle as doorbell), IRQ W1C, reset mid-run (all registers 0), CYCLES/STEPS_DONE edges, all fields round-trip | F7–F12, F14–F16 |
| `test_corner` | NSTEPS = 0; dsq = 0 (i == j and coincident bodies); NaN/Inf inputs; NPAIRS = 0; index ≥ N_BODIES and NPAIRS > N_PAIRS_MAX (ERR_PARAM); NSTEPS = 2³² − 1 aborted after a few steps (counter width) | F6, F8, F11, F13, F17 |

## 8. Open questions (carried to MAS / uArch)

1. Subnormal inputs/results: full IEEE support vs flush-to-zero with a sticky FP_DENORMAL flag —
   decide with the FP-unit choice at uArch (benchmark magnitudes never reach subnormals).
2. FP64 unit sourcing: own SystemVerilog vs imported open-source leaf cells (e.g. FPnew,
   Apache-2.0) — sizing spike at uArch; constraint: correctly rounded RNE add/mul/sqrt/div, licence
   compatible with the course report, leaf cells declared as imported (rubric §7).
3. AXI-Lite data width (32 vs 64) — MAS; ADR-0001 stays `proposed` until then.
4. K1 may move if the MAS register model changes the per-invocation cost (Q1).

## 9. Review findings

See `docs/review_prd.md`.
