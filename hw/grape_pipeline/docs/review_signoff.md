# grape_pipeline — dv_signoff review

## Pass 1 (2026-09-06, agent)

Scope: scoreboard as evolved for coverage (`tb/env.py`), CR sequences + `GrapeFullBenchTest`,
inline `// verilator coverage_off` regions, `formal/fsm_arcs.sv` + `synth/formal.sby`,
`docs/coverage_waivers.md`. Adversarial focus: false verification claims, vacuous checks,
exclusions hiding live logic, scoreboard paths that mask RTL bugs.

| # | Severity (must/should/nit) | Location | Finding |
|---|---|---|---|
| S1 | must | `tb/sequences/random_err.py:33-67` + `tb/sequences/smoke.py:50-61` (`run_to_done`) + `tb/env.py:172,187,220` | **ErrSeq cases 4-7 are vacuous.** `run_to_done` declares completion on sticky `DONE`, and case 3's run (line 33) is never W1C'd before case 4. So `run_to_done(3)` at line 43 (which also fires a third doorbell) returns on its **first poll** via the stale DONE bit while the 3-step run is still in flight (~120+ cycles vs ~40 elapsed). The line-44 W1C lands while BUSY; cases 5-7 then execute with the scoreboard mirror stuck `busy=True` forever (no later STATUS read ever observes BUSY fall — cases 5-7 contain none). Consequences: (a) the case-7 reads whose comment says "readback proves ignored writes really were ignored" are **skipped** by the scoreboard (`env.py:220` gates cfg-read compares on `not self.busy`); (b) the case-5 "PRD-F7 round-trip at full width" reads of pair words/NPAIRS are skipped the same way; (c) sticky compares (`env.py:187`) never run again, so the DUT's end-of-test `DONE\|ERR_BUSY` vs the mirror is never compared; (d) any RTL bug in this window (write-while-busy corrupting latched config, broken restore writes) is masked. The test passes while checking nothing after line 43. Fix: W1C `ST_DONE` between cases 3 and 4 (or make `run_to_done` poll on BUSY falling, not sticky DONE), **and** add an end-of-test guard in `GrapeScoreboard.check_phase`: `assert not self.busy and not self.aborted_wait_steps, "mirror desynced / deferred replay never resolved"` so any future silent desync fails loudly. |
| S2 | must | `tb/sequences/random_err.py:47-58` + `tb/env.py:194-197` | **IRQ_EN round-trip claim is vacuous even with S1 fixed.** ErrSeq case 5 writes `IRQ_EN = 0x1FFFE` and reads it back as part of the stated "PRD-F7 round-trip at full width" check, but `IRQ_EN` (0x010) is not in the scoreboard's `cfg_set` (`env.py:194-197` lists only DT/NSTEPS/BODY/PAIR words), so the read at line 54 is compared by nobody — a full-width IRQ_EN storage bug (stuck bit, wrong reset, bit-16 alias) would pass. The irq-pin test only exercises bit 1 (DONE). Fix: add `IRQ_EN` to `cfg_set` (it is idle-writable config; the ERR_BUSY-on-write-while-busy arm may need an exemption to match RTL — verify grape_regs treats IRQ_EN writes while busy as accepted, and mirror accordingly) or compare the readback in the sequence itself. |
| S3 | should | `tb/env.py:172-186` | **Completion disposition trusts possibly-stale ABORTED.** `_on_status_read` classifies the run as aborted via `self.abort_sent and (data & ST_ABORTED)`, but the same function's own comment concedes sticky bits "can be stale from an un-W1C'd earlier run". With a stale ABORTED (earlier aborted run not W1C'd) and an abort sent near the final boundary, a DUT bug that ends the run asserting **neither** DONE nor ABORTED is fully masked: the DONE check is skipped (aborted branch), the sticky compare matches the stale ABORTED, and `STEPS_DONE <= nsteps` passes. Not reachable with today's sequences (AbortSeq's `finish_abort` W1Cs each trial) — latent, so should not must. Fix: classify aborted on a *fresh* edge — e.g. `self.abort_sent and (data & ST_ABORTED) and not (self.sticky & ST_ABORTED)`, and in the done branch additionally check `not (data & ~self.sticky & ST_ABORTED)` (no unexplained fresh ABORTED). |
| S4 | should | `tb/env.py:177,187-190,213-215,220,226-233` | **`aborted_wait_steps` window is an unguarded blind spot.** Between abort completion and the STEPS_DONE read: (a) all sticky and cfg-readback compares are gated off; (b) a W1C in the window corrupts the deferred replay (DUT's FP flags were raised during the run and cleared by the W1C, but the mirror only ORs them in at the later `_advance_golden` — false mismatch), and a cfg/BODY write in the window is clobbered when the deferred `_advance_golden` overwrites all BODY mirror words; (c) if a sequence never reads STEPS_DONE after an abort, `aborted_wait_steps` sticks for the rest of the test and every subsequent sticky/readback check is silently vacuous. Today's AbortSeq always reads STEPS_DONE immediately, so this is latent. Fix: the S1 end-of-test assert closes (c); for (a)/(b) either document the window as a TB stimulus contract ("no W1C/cfg writes between ABORTED and STEPS_DONE read") in env.py, or replay the deferred advance before applying W1C/cfg-write items. |
| S5 | should | `tb/test_grape_pipeline.py:190-226` (`GrapeFullBenchTest`) | **Sign-off equivalence chain is sound but unguarded.** The PRD-F4/F5 asserts run against a separately recomputed `emulation.advance` state; the DUT enters the claim only through the scoreboard's bit-exact compare of the 70 BODY readback words in `FullBenchSeq`. Verified: the readback loop is currently complete, the reference path is equivalent to `bench_nbody()` (`offset_momentum(SYSTEM[0])` on the same module objects + the generated bit-exact `advance(0.01, 20000)` + `report_energy()` defaults; `report_energy` is pure so the extra pre-call in `bench_nbody` is irrelevant), and scoreboard inputs (mirror words, pair order) bit-match the test's `em` inputs. But nothing asserts the 70 compares happened: a truncated readback loop or a future scoreboard gating regression would leave the sign-off test passing on software-only data (the global `compared > 0` doesn't cover it). Fix: after the sequence, `assert self.env.scoreboard.compared >= 70` (snapshot count before/after) so PRD-F4/F5 provably rests on DUT data. |
| S6 | should | `rtl/grape_step_fsm.sv:18-22,41-47`, `rtl/grape_pipeline.sv:76-80`, `rtl/grape_regs.sv:34-38` + `tb/env.py:237-248` | **CYCLES is simultaneously toggle-waived and functionally unbounded below.** The coverage_off reason says "upper bits need 2^10..2^63-cycle runs", but the exclusion covers **all 64/32 bits** of `cycles`/`steps` — including low bits that toggle every cycle — and the scoreboard's only CYCLES checks are upper bounds (`per_step <= K1`, `<= 4` for NSTEPS=0). A CYCLES counter stuck at zero (or counting every 2nd cycle) passes every check with its toggle coverage waived: PRD-F14 would sign off on a dead counter. STEPS_DONE is exactly compared, so the gap is CYCLES-specific. Fix: add a lower bound in the k1 arm (e.g. `per_step >= 1`, ideally `>= <pipeline latency floor>`), and/or narrow the exclusion to the upper bits. |
| S7 | should | `synth/formal.sby` vs `docs/testplan.md` §6, `formal/fsm_arcs.sv:4-8` | **Formal delivery vs testplan table.** (a) Testplan §6 records fsm_arcs as "bounded, depth 300"; the actual run is depth 40 (bmc+cover, both PASS, 5/5 covers, src copies verified identical to current `rtl/`+`formal/` sources). (b) `bresp_hold.sv` and `w1c.sv` are listed in the §6 table but do not exist; the testplan's own fallback ("none: covered by test_regs 11/11 + SVA + protocol agent") must be *recorded at sign-off* — as it stands the table reads as delivered. (c) The harness header says "only the uArch §3.1 arcs are reachable" — an unbounded claim on bounded evidence; a `prove` (k-induction) task is nearly free for this 6-state FSM. Harness logic itself verified sound: the output decode is unique per real state, and the feared "busy-but-nothing-asserted bug state" *does* decode as LATCH — but the LATCH arc assert (must reach RUN/DONE_S next cycle) then fails on any hang or illegal-state detour, so the harness proves what it claims within the bound. Fix: align depth (raise to 300 or amend testplan), add a `prove` task, and pre-draft the §6 fallback line for the sign-off record. |
| S8 | nit | `rtl/grape_regs.sv:196-207` | Unbalanced coverage markers: `coverage_off` (196) ... `coverage_off` (199) ... `coverage_on` (202) — the `npairs_tmp` region is missing its `coverage_on`. Currently harmless (only the two intended declarations sit inside; `w1c_tmp` at 203 stays covered), but a declaration inserted at 198-199 would be excluded silently. Balance the pairs. |
| S9 | nit | `rtl/grape_accum.sv:22-25`, `rtl/grape_force_pipe.sv:23-26`, `rtl/grape_regs.sv` pairs decls | Over-broad whole-signal toggle exclusions: the pair-list exclusions justify waiving index bits [7:3] (doorbell-validated < N_BODIES) but also waive bits [2:0], which are live and toggling. Functional compares cover behavior, so nit — but the waiver reason doesn't match the waiver extent. |
| S10 | nit | `synth/formal/` | Stale sby run dir from the older single-task `config.sby`; its `src/fsm_arcs.sv` predates the current harness (missing the `unused_w` sink). `formal_bmc`/`formal_cover` are the live runs. Delete or regenerate to avoid a reviewer trusting the stale PASS. |
| S11 | nit | `rtl/grape_regs.sv:364-375,427` + `tb/env.py:220` | Reads-while-BUSY return the *latched/committed* copies (dt_l, npairs_l, committed body bank) but the scoreboard skips all cfg/BODY read checks while busy, so committed-copy read semantics are never checked by any test. Low risk (idle readback covers storage); note for a future window check. |

### Verified-clean (claims checked, no finding)

- **coverage_waivers.md "architecturally unreachable" claims: both TRUE** per `rtl/grape_step_fsm.sv`.
  `cg_abort.steps.0`: S_ABORT is entered only from S_COMMIT, which unconditionally increments
  `steps` first, so ABORTED ⇒ STEPS_DONE ≥ 1. ABORTED-with-steps==NSTEPS: the S_COMMIT arc takes
  S_DONE whenever `steps+1 == nsteps_i` regardless of `abort_pend` (line 88-91), and nsteps is
  latched, so ABORTED ⇒ STEPS_DONE ∈ [1, NSTEPS-1]. `nsteps.20000` deferral matches the
  Verilator-only `full_benchmark` test.
- **Inline coverage_off regions swallow no live logic.** Every region was inspected: all contain
  only signal/port declarations (toggle exclusions) or the pure-data `seed_rom` initial block in
  `fp64_rcp_nr.sv:87-1116` (verified: nothing but `seed_rom[i] = ...` assignments inside). No
  executable statement is excluded from line coverage.
- **GrapeFullBenchTest reference path ≡ `bench_nbody()`** (see S5 for the one guard gap): same
  module-level SYSTEM objects, same offset_momentum reference (sun == SYSTEM[0]), same generated
  `_BIT_EXACT` advance, same `report_energy` defaults/pair order; tolerances match PRD-F4/F5
  (1e-12 / 2e-9 / 5e-11).
- **NaN canonicalization** (`f2w`): canonicalizes only the *expected* value to the contract +qNaN;
  a DUT emitting sNaN/wrong-sign/payload NaN, or a number where golden NaNs, still mismatches.
- **k1_enforce gating**: K1 is enforced in smoke/corner/full_bench (all read CYCLES_LO with
  `steps_final` set), recorded-only in random tests as documented; no check became vacuous by the
  gating itself (but see S6 for the missing lower bound).
- **Formal freshness**: `formal_bmc`/`formal_cover` src copies are byte-identical to
  `rtl/grape_step_fsm.sv` and `formal/fsm_arcs.sv`; both PASS, all 5 reachability covers hit.

### Summary: 2 must / 5 should / 4 nit

## Resolutions (author, same day)

- **S1 (must, fixed)**: `run_to_done`/`poll_end` now require BUSY low together with the
  completion bit (stale sticky DONE no longer satisfies the poll), and the scoreboard's
  check_phase asserts the mirror ends idle (`busy`/`aborted_wait_steps` false) — a future
  desync fails loudly instead of skipping checks. Evidence: errors test went from 4 compared
  items / 1 run (vacuous) to 23 / 2 with the fix; 8/8 suite green.
- **S2 (must, fixed)**: IRQ_EN has its own mirror (bits 16:1, writable while BUSY per MAS §4)
  and every IRQ_EN read is compared. The full-mask round-trip in ErrSeq is now checked.
- **S4 (should, hardened)**: covered by the S1 end-of-test assert (an unread STEPS_DONE after
  abort now fails the test).
- **S5 (should, fixed)**: scoreboard counts BODY-window compares; GrapeFullBenchTest sets
  `min_body_compares=70` — the F-04/F-05 chain's premise is asserted, not assumed.
- **S6 (should, fixed)**: CYCLES now has lower bounds (>= steps completed; NSTEPS=0 in 1..4) —
  a dead counter fails.
- **S3 (should, accepted)**: latent only while sequences always W1C between aborts (they do);
  noted for dv-coverage of the next module.
- **S7 (should, resolved by documentation)**: testplan §6 amended — fsm_arcs delivered at BMC
  depth 40 + cover (FSM diameter << 40; every state reached in <= 6 steps), `bresp_hold`/`w1c`
  take the §6 fallback ("covered by test_regs 11/11 + SVA + protocol agent": the regs block's
  3x2240-bit body copies are beyond smtbmc reach).

### Summary after resolutions: 0 must open

## Pass 2 (2026-09-06, agent — 3-wide accumulate rewrite)

Scope: uncommitted diff vs HEAD in `rtl/` — `grape_accum.sv` (bitmap issue core, up to 3
accumulate ADDs/cycle), `grape_body_rf.sv` (3 write ports), `grape_pipeline.sv` (wiring),
`grape_regs_tb_top.sv` (port-0 zero-extension). Adversarial focus: same-(body,comp) order
hazards, slot-counter arithmetic, retire/write-back distinctness, bypass operand selection,
width arithmetic, Yosys 0.68 constructs, TB wrapper semantics. Trigger: K1 = 162 > KPI 128 at
sign-off; schedule model predicts 123/127.

| # | Severity (must/should/nit) | Location | Finding |
|---|---|---|---|
| A1 | must | `synth/yosys.log`, `synth/yosys_area.gen.ys`; `rtl/grape_accum.sv:186-221` | **Sign-off evidence incomplete: the only synth run on the new code is truncated, and the rewrite plausibly moves the critical path.** `yosys.log` does elaborate the new code (references `grape_accum.sv:359` muxes, reaches `opt_clean` on `grape_pipeline`) but the log ends mid-line with no final stats/check section — it cannot be cited as synthesizability/area evidence. The new issue core is a 60-iteration strictly serial comb cone (per-op: pairs-word mux, lane decode, `lane_hold`/`slots_used` carried iteration-to-iteration, 64-bit operand steering through variable-index `slot_q[slots_used]`, bypass compare against 3 retiring units), fed by `bc_clr` (shadow regs + `add_ovalid_i`) and fanning into the FP-ADD operand buses — a new longest-path candidate vs the old single-op decode. Plus the 35×64-bit working bank now has a 3-deep write mux per word. Close-out requires: (a) rerun `yosys_area.gen.ys` to completion and record area/timing delta; (b) the 20,000-step benchmark K1 (rerunning at review time) recorded against KPI ≤ 128. Neither is a code bug; both block the sign-off record. |
| A2 | should | `rtl/grape_accum.sv:243-258` (mul picker), `:279-289` + `:222-234` (single `integ_add_go`) vs `docs/uarch.md` §7 (123/127 model) | **Integrate phase is still single-issue — residual KPI risk if the 20k rerun misses 128.** The rewrite widened accumulate ADD issue to 3/cycle, but the integrate sequencer still issues at most one dt·v MUL per cycle (single `mul_slot`, one `integ_idx` walker) and at most one r+dtv ADD per cycle (one `integ_add_go` grant). The §7 schedule model that justifies 123/127 list-schedules the integrate ops greedily onto all 3 MUL/ADD units; at 1/cycle the 15-mul + 15-add tail costs roughly 10 extra cycles over the model. Measured abort case is exactly 128 (zero margin). If the pending 20k-step KPI run lands > 128, this is the identified bottleneck: widen the integrate mul walker (up to 3 free MUL slots/cycle, independent lanes) and let up to `nslots - slots_used` integrate adds issue. If the rerun lands ≤ 128, record this as the accepted design point. |
| A3 | should | `docs/uarch.md:16` (§1 block table), §3.3, §5 | **uArch↔RTL drift on the body RF and issue width.** The §1 block table still says body RF "2 read ports (pair i, j), 1 write port"; the RTL now has 3 write ports (one per ADD unit) with a distinct-target contract enforced by SVA. §3.3's "everything else overlaps" is consistent with 3-wide issue but never states the width, the bitmap/in-order-scan mechanism, or the one-op-per-lane-in-flight invariant the write-port distinctness proof rests on. Update §1/§3.3/§5 before the gate (uArch is the RTL's contract document) and record measured vs predicted cycles in §7. |
| A4 | nit | `rtl/grape_accum.sv:12`, `rtl/grape_body_rf.sv:9` | Edit artifacts in the module headers: line 12 of grape_accum splices two sentences onto one over-long line ("…162 cycles/step at sign-off. After the last pair, integrates…"), and grape_body_rf line 9 similarly runs "…guards distinctness); commit copies working -> committed in one cycle; load copies the" past the wrap column. Cosmetic; rewrap. |
| A5 | nit | `rtl/grape_regs_tb_top.sv:159-162`, `tb` regs suite | The regs unit TB drives RF write port 0 only (ports 1-2 tied to zero), so the widened 3-port `working_next` mux (`grape_body_rf.sv:60-64`) has unit-level coverage only on port 0; ports 1/2 are exercised solely by pipeline-level tests (which do use all three). Fine functionally — note it in the coverage record so the port-0-only wrapper isn't mistaken for full RF write coverage. |
| A6 | nit | `rtl/grape_accum.sv:366-380` | The distinct-target SVA is an immediate assert inside `always_comb`; in event-driven simulators (Icarus) it can fire on transient intermediate values mid-delta before `wr_*` settle. Verilator (the sign-off simulator) evaluates settled values, so no false fires today; `assert final` (deferred) would be the robust form. Pre-existing pattern (the old ≤1-retire assert had the same shape). |

### Verified-clean (hunted, no finding)

- **`slots_used` wrap (the feared over-issue): does not occur.** Both counters are 2-bit;
  `nslots` ≤ 3 (at most 3 `add_free_i` bits, `slot_q` written at indices 0..2 only). The
  increment at `grape_accum.sv:217` executes only under `slots_used < nslots` (:197), so the
  largest value ever written is `2'd2 + 1 = 2'd3` — no wrap to 0; at `slots_used == 3` the
  guard is false for every later op and for `integ_add_go`. The 3'd3→0 wrap requires an
  increment at 3, which the guard makes unreachable.
- **`lane_hold` covers issued-this-cycle ops.** Line 219 sets `lane_hold[e_lane]` for *every*
  valid unissued op — including one that just issued in the same iteration — so at most one op
  per (body,comp) lane issues per cycle, and any later same-lane op is blocked behind an
  unissued earlier one (stalled on force_ready, busy, or slots). The scan restarts at e=0 each
  cycle over the persistent `acc_issued` bitmap, so per-lane program order is re-derived from
  scratch every cycle; no overtake path exists.
- **`busy_bc` has no holes.** `busy_bc <= (busy_bc & ~bc_clr) | bc_set` (:316): a lane retiring
  and re-issuing via the bypass in the same cycle stays busy (bc_set wins — S2 re-occupancy
  preserved); a lane retiring without re-issue clears; distinct lanes are independent bits.
  Combined with lane_hold this gives the invariant *at most one op per lane in flight*, which
  makes the bypass unit selection (:200-206) unique — two units can never retire the same lane
  in one cycle (they would have had to issue on the same lane in the same cycle, which
  lane_hold forbids, or while busy, which busy_bc forbids).
- **Bypass cannot skip an op or feed the wrong value.** The bypass is taken only when
  `busy_bc[e_lane] && bc_clr[e_lane]`, and the op taking it is the earliest unissued op on the
  lane (scan order) — by the one-in-flight invariant, exactly the chain successor of the
  retiring op. When the bypass-eligible op loses the slot race, the lane clears and the next
  cycle's issue reads the working RF, which the retiring unit's write port updated in the same
  cycle the retire happened (`add_r_i[u]` == the written data, `grape_body_rf` flops at that
  posedge). `busy_bc==0 && bc_clr==1` (bypass mux skipped while a retire writes the RF) is
  unreachable: a retire implies the op issued, which implies busy was set.
- **Write-back distinctness holds by construction.** Accumulate retires target fields 3..5
  (`iss_fld = comp+3` at issue, passed through `add_sh_f`); integrate adds target fields 0..2
  (`{1'b0, f[1:0]}` at write-back, and `iss_fld = integ_add_comp` ∈ 0..2 at issue). So
  accumulate-vs-integrate can never collide even on the same body. Two accumulate retires are
  distinct lanes (one-in-flight invariant) ⇒ distinct (body, comp+3). Two integrate adds
  cannot retire together: `integ_add_go` grants one per cycle and the ADD pipe is fixed
  3-cycle, so distinct issue cycles ⇒ distinct retire cycles. The body-RF last-port-wins
  collision behavior is therefore unreachable; the SVA guards the invariant in sim.
- **Force operand indexing is bit-identical to the old engine.** `force_flat_i[e*64 +: 64]`
  with e = pair·6+op ≡ old `(pair*6+op)*64 +:64`; sub select `(e%6)<=2` ≡ `acc_op<=2`; i/j
  body decode (`pair*16` vs `pair*16+8`) and comp decode (`(e%6)%3` ≡ old op[1:0] / op−3)
  all match. Chains touch only their own lane's v (no cross-lane reads), and force terms are
  fixed registered values, so cross-lane reordering cannot change any per-location FP op
  sequence — bit-exactness reduces to per-lane order, which is preserved (matches 8/8
  bit-exact + duplicate-chain random evidence).
- **`acc_valid_mask` arithmetic sound.** `32'(e/6) < {24'd0, npairs_i}`: e is a nonnegative
  unrolled constant, and a signed-vs-unsigned compare is performed unsigned — correct for all
  e, npairs. `acc_done` (combinational over registered `acc_issued`) has the same timing as
  the old registered flag (true the cycle after the last issue) and is only sampled at posedge
  in `always_ff` — comb glitches are irrelevant to NBA sampling. Stale `acc_done`/`all_done_o`
  between steps is never observed: the step FSM pulses `step_start_o` from S_LATCH/S_COMMIT
  (run_o low), and by the first S_RUN cycle the bitmap is cleared; `all_done_i` is sampled in
  S_RUN only.
- **`retired` cannot overshoot the equality.** Each op retires exactly once (shadow-qualified),
  the counter accumulates once per cycle (S1 form kept), total = 6·NPAIRS+30 exactly; 8-bit vs
  max 90. `retire_cnt` 3-bit vs real max 4 (3 ADD + 1 MUL — mul issue is 1/cycle so mul
  retires are 1/cycle).
- **TB zero-extension is faithful.** `grape_regs_tb_top` port 0 = the old single port
  (`bwr_*` 1-to-1), ports 1/2 tied inactive — test_regs drives exactly what it drove before;
  regs suite 11/11 unaffected.
- **Yosys 0.68 constructs OK.** No block-local declarations, no struct arrays; the
  variable-index unpacked-array writes (`slot_q[nslots]`, `iss_a[slot_q[slots_used]]`) and
  the parallel-array shadows elaborate (log reaches opt_clean past accum) — only run
  completion is missing (A1). `e_lane` 4-bit truncation for body ≥ 6 is unreachable
  (doorbell-validated < N_BODIES) — same pre-existing pattern as the old `bc_idx`.
  `busy_bc[integ_idx[3:0]]` at integ_idx=15 is gated off by `integ_mul_done` (pre-existing).
- **Pipeline merge still safe.** Accum drives only `add_free_i` slots via `slot_q`; the
  `(fp_add_valid & ac_add_valid) == 0` SVA (`grape_pipeline.sv:181`) still guards the OR
  merge with multi-issue; sub/operand defaults are zero on non-issuing units.

### Summary: 1 must open

A1 (evidence: complete Yosys rerun + 20k-step K1 record) blocks sign-off; A2/A3 should land
with it (A2 becomes the action item if the K1 rerun exceeds 128). No functional bug found in
the ordering/slot/retire core: the specific traps hunted (slots_used wrap at 3, lane_hold
missing issued ops, busy_bc set/clear collision, double-retire on one lane, bypass skipping
the chain head, force-index change, mask width, TB extension) are all clean.

## Resolutions after pass 2 (author)

- **A2 (should, fixed)**: integrate widened to per-lane readiness (uArch §3.1) with multi-issue
  on all free MUL/ADD slots — landed minutes after the review snapshot. 8-test suite: smoke K1
  126 -> 111, abort worst 128 -> 117, corner integrate-only 34.7 -> 27.7, all bit-exact.
- **A3 (should, fixed)**: uArch §1 write-port count corrected; new §3.4 records the 3-wide
  scan, the one-op-per-lane invariant (the write-port distinctness proof), and per-lane
  integrate.
- **A1 (must)**: closed by the final `make area` rerun and the 20,000-step K1 result recorded
  in the gate table below/STATUS.

- **A1 (must, closed)**: final `make area` completed on the sign-off RTL — 584,454 sky130
  cells / 4.075 mm^2, 0 errors (pre-fix: 393,367 / 2.938 mm^2; the +39% area buys K1 162->124).
  Full 20,000-step K1 = 124.0 <= 128 recorded in the gate table.

### Final: 0 must open (both passes)
