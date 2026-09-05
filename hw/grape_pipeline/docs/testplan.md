# grape_pipeline — DV testplan (stage 5)

Inputs: `docs/prd.md` (PRD-F1..F17), `docs/mas.md` §4/§8, `docs/uarch.md` §3/§8,
`rtl/` (N_BODIES=5, N_PAIRS_MAX=10, SCHED_STEP_CYCLES=123), `golden/emulation.py` (frozen).
Methodology: pyuvm on cocotb 2.0, Verilator primary, per `tb-best-practices` layering.
`--assert` is armed in `hw/common/scripts/cocotb_run.py`: the RTL's SVAs (issue-slot collision,
≤1 accumulate retire/cycle) are live checkers in every test.

## 1. Feature list

`F-01..F-17` map 1:1 to PRD-F1..F17. Added features: `F-20..F-24` (FSM transition coverage,
MAS §8 write-collision rows, hazards uarch §8), `F-30..F-33` (schedule/counter properties the
uArch model predicts and the RTL review made measurement-mandatory).

## 2. Matrix

| Feature | Test (directed / random sequence) | Covergroup + bins | Checker | Prio | Status |
|---|---|---|---|---|---|
| F-01 NSTEPS steps, both bodies updated per pair (PRD-F1) | `test_smoke` (NPAIRS=1..2, NSTEPS=1..2); `test_random` (`seq_rand_cfg`); extreme `cg_cfg` bins filled by `test_corner`/`test_abort`/`test_full_benchmark` (cg_cfg samples env-wide, union of all tests) | `cg_cfg`: NSTEPS {0,1,2,3..10,20000,2³²−1(aborted)}, NPAIRS {0,1..10} cross | scoreboard `GrapeScoreboard` vs `emulation.advance` bit-exact state | must | pass (bring-up: smoke NPAIRS=2/NSTEPS=2 bit-exact, Verilator + Icarus) |
| F-02 binary64 RNE, HW op order for r^-3/2 (PRD-F2) | `test_bitexact` (`seq_rand_cfg`, ≥100 seeds); unit TBs (done: 4/4 each) | `cg_fp_class`: operand class {norm, subnorm, zero, inf, nan} per unit input, from monitor | scoreboard bit-exact; unit oracles `tb/unit/fp_helpers.ref_op`; HardFloat divSqrt cross-check on sqrt/rcp mismatch triage | must | todo |
| F-03 pair-list order significant (PRD-F3) | `test_bitexact`: ≥100 random pair permutations incl. duplicates (i,j) both orders | `cg_pairs`: i×j cross (i≠j), duplicate-pair bin, same-body-in-2-pairs bin | scoreboard bit-exact vs `emulation.advance` with the same pair order | must | todo |
| F-04 energy fidelity (PRD-F4) | `test_full_benchmark` (benchmark 5-body system, NSTEPS=20000) | `cg_cfg` NSTEPS=20000 bin | two-reference: state bit-exact vs `emulation.advance`; THEN \|ΔE/E\| ≤ 1e-12 vs `nbody_ref` (libm-pow reference — nonzero by design, calibrate.py measured ~1.7e-14) | must | todo |
| F-05 trajectory fidelity (PRD-F5) | `test_full_benchmark` | — (same run) | per-body ‖r_hw−r_ref‖/max(‖r_ref‖,1e-300) ≤ **2e-9 for r and 5e-11 for v** vs `nbody_ref` (calibrate.py measured ~1.06e-10 / ~2.64e-12); exact-0 only vs `emulation` | must | todo |
| F-06 capacity 5 bodies / 10 pairs (PRD-F6) | `test_bitexact` (NPAIRS=10 cases); `test_smoke` | `cg_cfg` NPAIRS=10 bin | scoreboard bit-exact at full occupancy | must | todo |
| F-07 per-invocation programming (PRD-F7) | `seq_rand_cfg` randomises DT/NSTEPS/NPAIRS/masses/positions/velocities/pairs each invocation; b2b invocations in `test_random` | `cg_cfg` cross; `cg_b2b`: {reprogram-all, reprogram-partial(committed reuse)} | scoreboard reprograms golden identically per invocation | must | todo |
| F-08 NSTEPS=0 no-op (PRD-F8) | `test_corner::nsteps0` | `cg_cfg` NSTEPS=0 bin | DONE set, state words unchanged (readback == committed), CYCLES ≤ 4 | must | pass (bring-up: test_corner nsteps0) |
| F-09 config/doorbell write while BUSY ignored + ERR_BUSY (PRD-F9) | `test_errors::busy_writes` (each register class while BUSY) | `cg_err`: {ERR_BUSY×(doorbell, DT, NSTEPS, NPAIRS, PAIR, BODY)} | ERR_BUSY sticky; run result bit-exact to pre-write config (golden unaware of ignored write) | must | todo |
| F-10 state reads while BUSY = last committed (PRD-F10) | `test_errors::busy_reads` (poll state mid-run) | `cg_read_while_busy`: {idle, busy} × {BODY, CYCLES, STEPS_DONE} | BODY window == committed snapshot; CYCLES/STEPS_DONE are live (MAS §4): monotonic non-decreasing while BUSY, STEPS_DONE ≤ NSTEPS | must | todo |
| F-11 ABORT at step boundary ≤ K1+8 (PRD-F11) | `test_abort` (abort at randomised cycle offsets, incl. during final step); `test_corner::abort_idle`; `test_abort::huge_nsteps` (NSTEPS=2³²−1, abort after a few steps — exercises full counter width) | `cg_abort`: write offset within step {0..30,31..122, commit-window}, steps_done {0,1,mid,NSTEPS-1}, DONE-wins bin (abort lands on boundary NSTEPS), NSTEPS=2³²−1 bin | ABORTED **or DONE if the boundary reached is step NSTEPS** (MAS §8 DONE-wins) + IRQ within K1+8=136 cycles of write; STEPS_DONE cross-checked against the cycle-stamped abort time via the schedule model's 123..127 cycles/step window (independent of DUT; exact once F-30 pins the measured value); final state bit-exact after replaying STEPS_DONE steps | must | todo |
| F-12 DONE/ABORTED status + level IRQ, W1C (PRD-F12) | `test_irq` (each sticky bit set → irq within 2 cycles; W1C drops irq; IRQ_EN mask) | `cg_irq`: each STATUS bit × IRQ_EN {0,1}; W1C-while-set | irq == \|(STATUS & IRQ_EN) registered, monitor-checked every cycle; sticky bits survive doorbell | must | todo |
| F-13 IEEE specials propagate, sticky FP_* (PRD-F13) | `test_fp_flags`: coincident bodies (divzero+invalid), huge/tiny mass+DT (overflow/underflow) | `cg_fp_flags`: each of {invalid, divzero, overflow, underflow} set; cross with run-continues | STATUS FP_* == scoreboard sticky mirror (union of per-run `advance` flag sets since last observed W1C/reset — §4); NaN/Inf state bit-exact | must | todo |
| F-14 CYCLES / STEPS_DONE counters (PRD-F14) | `test_smoke`, `test_abort`, `test_full_benchmark` | `cg_counters`: CYCLES read {while busy, after done}; STEPS_DONE {0, mid, NSTEPS} | CYCLES == doorbell-accept..DONE/ABORTED inclusive (monitor cycle-stamps both edges); STEPS_DONE exact | must | todo |
| F-15 mid-run synchronous reset (PRD-F15) | `test_reset` (reset in IDLE / RUN / COMMIT / DONE) | `cg_reset`: FSM state at reset {idle, latch, run, commit, done} | post-reset: all registers at MAS reset values (full readback), re-run from scratch bit-exact | must | todo |
| F-16 AXI4-Lite protocol (PRD-F16) | all tests via `axi_lite_agent` (cocotbext-axi, independent protocol checks); `test_regs` unit suite (done: 11/11) | `cg_axi`: {aligned/unaligned, strobe subsets on CTRL, b2b, doorbell BRESP hold {0..4}} | cocotbext-axi protocol assertions; BRESP hold ≤ 4; wr_err → SLVERR | must | todo |
| F-17 doorbell param validation (PRD-F17) | `test_errors::param_reject` (pair idx ≥ 5, NPAIRS > 10) | `cg_err`: {ERR_PARAM × (pair_idx, npairs)}; reject-then-fix-then-accept | ERR_PARAM only, no BUSY, counters hold; corrected doorbell then runs bit-exact | must | todo |
| F-20 step-FSM transitions (uarch §3.1) | union of `test_smoke`/`test_corner`/`test_abort` | `cg_fsm`: each arc of §3.1 incl. LATCH→DONE_S, COMMIT→ABORT_S, reject arc | FSM monitor: only legal arcs observed | must | todo |
| F-21 MAS §8 write collisions | `test_corner::ctrl_combos` (DOORBELL+ABORT one write, idle and BUSY; ABORT while idle; ABORT same cycle as accept) | `cg_ctrl`: CTRL write value {DB, AB, DB+AB} × {idle, busy} | per MAS §8 row: idle DB+AB → nothing; busy → ABORT acts + ERR_BUSY; abort-at-accept → ABORTED with STEPS_DONE ≤ 1, or DONE when NSTEPS=1 (DONE-wins) — both NSTEPS=1 and NSTEPS>1 driven | must | todo |
| F-22 accumulate RAW chains (uarch §8, R6/S2) | `test_bitexact` duplicate-pair + shared-body patterns (max chain depth) | `cg_chain`: same (body,comp) consecutive-pair distance {1,2,≥3} | bit-exact result (order-sensitive sums differ if a chain breaks); SVA ≤1 accumulate retire/cycle | must | todo |
| F-23 issue-slot collisions (uarch §8) | all tests (SVA armed) | — (assertion, not sampled) | RTL SVAs: fp_*/ac_* issue merge collision → $error | must | todo |
| F-24 FP flags valid-qualified (uarch §9, R11) | `test_fp_flags::quiet_idle` (idle after flag-raising run, W1C, verify no re-set) | `cg_fp_flags` W1C-then-idle bin | FP_* stay 0 while idle N cycles (monitor) | should | todo |
| F-30 K1 measurement (uArch §7 model: 123 nominal / 127 worst) | `test_smoke` (measure), `test_full_benchmark` (20000 steps) | `cg_counters` CYCLES-per-step derived bin {≤128, >128} | CYCLES/NSTEPS ≤ K1=128; report measured value vs model 123 (review carry-forward: mandatory after R6/S2 + scr_fwd restructure) | must | pass (bring-up: measured 126.0 cycles/step ≤ 128; integrate-only 34.7) |
| F-31 all_done accounting (grape_accum `retired == acc_total + 30`) | `test_smoke` with per-step VCD; `test_random` soak | — (checked, not sampled) | no step hangs: RUN→COMMIT within 200 cycles (watchdog per step) | must | todo |
| F-32 NPAIRS ≤ 10 suppression incl. 0 (PRD-F6 range) | `test_bitexact` (each NPAIRS 1..10); `test_corner::npairs0` (NPAIRS=0: integrate-only step) | `cg_cfg` NPAIRS bins 0..10 each | bit-exact per NPAIRS; NPAIRS=0 still integrates positions (golden agrees); suppressed slots leave no state change | must | todo |
| F-33 back-to-back invocations reuse committed state | `test_random`: chain runs where run N+1 reads run N's committed output as input | `cg_b2b` chained bin | golden chained identically; bit-exact after each link | should | todo |

No empty cells; features with no cheap covergroup carry an explicit checker instead (F-23, F-31).

## 3. Env plan (pyuvm)

- **Tests** (`tb/tests/`): `test_smoke`, `test_bitexact`, `test_corner`, `test_abort`,
  `test_errors`, `test_irq`, `test_fp_flags`, `test_reset`, `test_random`,
  `test_full_benchmark` (sign-off only). Each is a `uvm_test` on `GrapeBaseTest`
  (extends `hw/common/tb/base_test.py`).
- **Env** `GrapeEnv(uvm_env)`: one `axi_lite_agent` (`hw/common/tb/axi_lite_agent.py`,
  cocotbext-axi master; **today driver+sequencer only — the passive monitor with TLM analysis
  ports is a `dv_bringup` deliverable**, added to the shared agent so huffman/mtf inherit it) —
  the module is MMIO-only (MAS §5), no stream agent. PRD-F16's "independent protocol agent" =
  cocotbext-axi's own handshake/response checking on the master + the new passive monitor's
  protocol assertions (BRESP hold bound, response codes), independent of the driver path.
  `GrapeStatusMonitor` (passive: irq line, STATUS polling snoop, FSM arc watch via DUT
  hierarchy), `GrapeScoreboard(uvm_scoreboard)` fed by TLM analysis ports from the AXI monitor
  (writes → stimulus mirror, reads → actual values).
- **Sequences** (`tb/sequences/`): `seq_program` (config + state + pairs + doorbell),
  `seq_rand_cfg` (constrained-random config: DT log-uniform ±weird exponents, bodies from
  benchmark ± perturbation, pair permutations), `seq_poll_done` (IRQ or poll), `seq_abort_at(n)`,
  `seq_busy_write`, `seq_w1c`.
- **ConfigDB keys**: `dut`, `clk_period_ns` (20), `golden` (module handle `golden.emulation`).
- **Vectors** (`tb/vectors/`): benchmark initial state dump for `test_full_benchmark`
  (from `golden/nbody_ref.benchmark_system()`).

## 4. Golden-model interface

Scoreboard call, per accepted doorbell (mirrored from the write stream):

```python
flags = golden.emulation.advance(dt, nsteps, bodies, pairs)   # in-place on bodies
```

- Inputs mirrored from the same AXI writes the driver sent (committed-copy semantics: the
  mirror updates only at doorbell accept, PRD-F9/F10).
- Expected: final `bodies` (35 × float64) **bit-exact** (`struct.pack` compare, NaN canonical
  0x7FF8000000000000 per contract), STEPS_DONE == nsteps.
- **Sticky-flag mirror**: FP_* are sticky across doorbells (PRD-F12); the scoreboard keeps a
  mirror = union of every completed run's `advance` flag set, cleared only when it observes a
  matching W1C write or reset on the AXI stream. Check: STATUS FP_* == mirror after every run
  and after every W1C. A W1C landing while BUSY (MAS permits it) makes the mirror a lower bound
  for the rest of that run — the check degrades to STATUS FP_* ⊆ (mirror ∪ current-run flags)
  until the run completes, when exact equality is re-established.
- Abort: golden runs `advance(dt, steps_done_hw, ...)` after the fact — HW reports how far it
  got, golden replays exactly that many steps, then bit-exact compare (valid because steps are
  serial and state changes only at COMMIT).
- Tolerance policy: **two references**. vs `emulation.py` (the HW op-order model): bit-exact,
  everywhere. vs `nbody_ref` (the benchmark's libm-pow `advance`): PRD-F4/F5 tolerances
  (|ΔE/E| ≤ 1e-12, trajectory 2e-9 for r / 5e-11 for v) — nonzero by design because libm pow ≠ the sqrt/mul/rcp
  sequence; `golden/calibrate.py` measured ~1.7e-14 / ~1.06e-10 (r) / ~2.64e-12 (v), i.e. ~50x/~19x margin.
  Reported measured-vs-bound at sign-off.
- Full-benchmark input (sign-off): `benchmark_system()` state, DT=0.01, NSTEPS=20000 — the
  benchmark's own `advance(0.01, 20000)` call.
- Cross-checker for FP-unit mismatch triage only (not a scoreboard): HardFloat `divSqrtRecFN`
  (rcp-agent carry-forward), wired as an offline script over failing vectors.

## 5. Coverage goals

- Verilator `--coverage`: line ≥ 90 %, toggle ≥ 90 % over `rtl/*.sv` excluding
  `grape_regs_tb_top.sv` (TB wrapper, excluded as non-DUT) and generated
  `grape_sched_rom.svh` constants (data, not logic — exclusion justified per line in the
  sign-off report).
- Functional: every `cg_*` bin in §2 hit ≥ 1; crosses listed hit except explicitly waived
  (waivers recorded in `docs/coverage_waivers.md` at sign-off with reasons).
- Expected-hard lines: sqrt/rcp special-path branches (fed by `test_fp_flags` operand classes);
  scr_fwd forward-hit paths (fed by duplicate-pair chains, F-22).

## 6. Formal properties

`formal/` (sby, Yosys smtbmc; optional per FLOW, listed with intent):

| Property | File | Note |
|---|---|---|
| step FSM: only §3.1 arcs reachable; DONE_S/ABORT_S always reach IDLE | `formal/fsm_arcs.sv` | bounded, depth 300 |
| doorbell BRESP hold ≤ 4 cycles | `formal/bresp_hold.sv` | regs block only, unconstrained AXI |
| W1C: STATUS sticky bit falls only on matching W1C write or reset | `formal/w1c.sv` | regs block only |

The datapath (FP64 units, schedule) is out of formal scope: correctness there is bit-exact
simulation vs the executable oracle; state space is far beyond smtbmc depth. If the three
properties above prove too heavy for sby on the flattened regs block, the fallback recorded at
sign-off is "none: covered by test_regs 11/11 + SVA + protocol agent", per FLOW's
"none with reason" allowance.

## 7. Traceability

Every PRD-F row appears as F-01..F-17 in §2; MAS §8 rows map to F-09/F-11/F-12/F-17/F-21;
uArch §3.1 arcs to F-20, §3.3/§8 hazards to F-22/F-23, §7 model to F-30; review carry-forwards
(K1 mandatory measurement, HardFloat cross-check, bring-up-first synthetic step) to F-30, §4,
and `test_smoke` respectively.
