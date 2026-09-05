# grape_pipeline — bring-up review

## Pass 1 (2026-09-05, agent)

Scope: `hw/common/tb/axi_lite_agent.py` (new AxiLiteMonitor + driver API change),
`hw/grape_pipeline/tb/env.py` (GrapeScoreboard replay), `tb/sequences/smoke.py` +
`tb/test_grape_pipeline.py` vs testplan rows F-01/F-08/F-30, and the stage RTL diff
(`grape_force_pipe.sv` MUL lane-mapping fix, `grape_accum.sv` declaration hoist).
Reviewed against `docs/testplan.md`, `docs/mas.md` §4/§8, `golden/emulation.py`.

| # | Severity (must/should/nit) | Location | Finding |
|---|---|---|---|
| 1 | must | `hw/common/tb/axi_lite_agent.py:7,76-79` | X-check coverage does not match the stated contract. The docstring claims the monitor "asserts that DUT-driven signals are X-free after reset", but `_hs()` returns False on an unresolvable valid/ready — an X on `awready`/`wready`/`bvalid`/`arready`/`rvalid` silently reads as "no handshake" (no assert, no log); only BRESP/RDATA/RRESP are asserted, and only when the enclosing handshake resolved. On the primary Verilator (2-state) sim every X-assert is vacuous by construction. In Icarus a dropped handshake surfaces only indirectly (orphan-B/AR assert cycles later, or a driver hang). Fix: assert `is_resolvable` on all five valid/ready pairs (and `rst_n`) once out of reset, or narrow the docstring to the resp/data channels actually checked. |
| 2 | must | `hw/grape_pipeline/tb/env.py:115-116,81` | Sticky FP-flag mirror is never cleared. The STATUS-write branch is `pass` with the comment "W1C: sticky mirror cleared only for FP bits" — but no code clears `expected_flags` on an FP-bit W1C, contradicting the comment and testplan §4 ("cleared only when it observes a matching W1C write or reset"). Masking case: RTL whose FP-bit W1C is broken (bits never clear) still passes — after a W1C and a later run's DONE, RTL shows the stale flags and the mirror still expects the uncleared union, so `got == expected` holds. Dormant today (`expected_flags` is empty in bring-up runs) but it defeats F-13/F-24 the moment `test_fp_flags` exists. Fix: on a STATUS write, clear from `expected_flags` the FP names whose W1C bits are set (honouring `it.strb` byte 1). |
| 3 | should | `env.py:117-124`, `smoke.py:77-78` | W1C efficacy is unverified. The post-W1C `rd(STATUS)` in SmokeSeq is compared against nothing: with DONE cleared, the read falls through every scoreboard branch. A stuck-at-DONE W1C bug passes smoke outright (in CornerSeq it is caught only indirectly, via the stale DONE truncating run 2's poll and the subsequent STEPS_DONE/body mismatches). The bring-up "pass" rows (F-01/F-08/F-30) do not claim W1C, so no claim lies — but the sequence performs the W1C+read as if checked. Add a mirror of the DONE/ABORTED sticky bits (cleared on W1C replay) and compare every idle STATUS read, or at minimum assert DONE==0 on the post-W1C read. |
| 4 | should | `env.py:111-121` | Mirror BUSY window is skewed at the tail. Mirror `busy` clears on the STATUS **read** that shows DONE/ABORTED; RTL BUSY cleared at the actual DONE, possibly many cycles earlier. A config write landing between real-DONE and observed-DONE is accepted by RTL but dropped by the mirror (line 113 gates on mirror busy) → stale mirror → false mismatch. Head of window is aligned (monitor emits the CTRL write at B-completion, and BRESP is held until BUSY is visible per MAS §5 — good), only the tail diverges. Dormant with the current blocking poll sequences; a trap for `test_errors`/`test_random`. Document the invariant or clear mirror busy heuristically on the first config write after a run's golden has been executed. |
| 5 | should | `env.py:113-114` vs `grape_regs.sv` `apply_strb` | Write modeling diverges from MAS §4 register semantics on strobes and reserved bits: (a) the mirror drops any config write with `strb != 0xF` entirely, while RTL applies byte strobes (`apply_strb`); (b) the mirror stores the full 32-bit written value for NPAIRS (bits 7:0 in RTL) and PAIR[k] (bits 15:0), whose reserved upper bits read 0 in RTL — so read-back of e.g. NPAIRS=0x100 would false-mismatch. Both dormant (driver always writes full 4-byte strobes, tests write small values); both bite when F-16 strobe-subset tests arrive. Model byte strobes and per-register write masks in the mirror. |
| 6 | should | `env.py:110-124` | Replay has no abort model and an undocumented W1C invariant. (a) CTRL bit 1 only blocks doorbell-accept; an abort while busy leaves mirror busy until an ABORTED-showing read, then compares full-NSTEPS golden state against the aborted RTL → guaranteed false mismatch (testplan §4 requires replaying `steps_done_hw` steps) — needed before `test_abort`. (b) DONE is sticky: a sequence that doorbells again without W1C leaves stale DONE visible, and the mirror clears `busy` on the next run's first poll → readback compared while RTL still runs → false mismatch. Every sequence must W1C before the next doorbell; state that in the scoreboard docstring or mirror the sticky bits (finding 3 fixes this too). |
| 7 | should | `axi_lite_agent.py:93-117` | `ap` "bus order" is write-before-read within a cycle by construction (the B pop is evaluated before the R pop in the same ReadOnly pass); true ordering between the independent AXI channels completing in the same cycle is arbitrary. Sound while the driver is blocking single-outstanding (it is, today); once `test_random` pipelines reads against writes the replay order becomes a coin flip on same-cycle completions. Note the constraint next to the monitor, or timestamp items. |
| 8 | nit | `axi_lite_agent.py:94,96,114` | In Icarus, an X in `awaddr`/`wdata`/`wstrb`/`araddr` during a resolvable handshake raises `ValueError` from `int()` — loud, but an unlabeled traceback rather than a monitor assert with a signal name. |
| 9 | nit | `env.py` (whole `_replay`) | `item.resp` is never checked by the scoreboard (monitor captures BRESP/RRESP; driver captures them too). A decode bug returning SLVERR on a mapped register is caught only indirectly through data mismatches. Cheap add: assert OKAY for every address the mirror recognizes. |
| 10 | nit | `env.py:111` vs `grape_regs.sv:286` | Mirror doorbell-accept ignores `wstrb`; RTL requires byte-0 strobed on CTRL (review R7). A strobeless CTRL write would diverge (mirror runs golden, RTL ignores) — loud (timeout), and unreachable with the current driver, but the gate is one `it.strb & 1` away. |
| 11 | nit | `env.py:135-141` | K1 check has no lower-bound sanity: a CYCLES register stuck at 0 passes `per_step <= 128` (the exact-CYCLES checker is F-14, todo). A `per_step >= 1` (or `>= 30` integrate-only floor) guard would make the F-30 "measured" figure self-validating. |

### Verified clean (checklist verdicts)

- **MUL lane-mapping fix consistent everywhere.** The stage diff fixes all six sites in
  `grape_force_pipe.sv` (five issue-site indices at lines 252-256 and the free-mask at 274) to
  `2'(ev_unit - 3'd3)`. All consumers of the lane index operate purely on 0..2:
  `mul_iss_p/t` are written per-lane and read per-lane by the shadow pipes; `mul_free_o` →
  `grape_accum.mul_free_i` (lane-indexed slot picker); `grape_pipeline.sv`'s issue merge,
  collision SVAs and generate-loop instantiation are all lane-indexed. `grape_force_pipe.sv:201`
  is the **only** consumer of `SCHED_UNIT_V` in the tree; the decode chain `<=2 / <=5 / ==6 /
  else` fully covers the 3-bit id with sqrt=6 exact-matched and rcp=7 as the residual — no other
  place can truncate a 3..7 global id. ADD's `ev_unit[1:0]` is identity for 0..2 — correct.
- **`grape_accum.sv` diff is order-only**: seven declarations (`integ_body/comp`,
  `integ_add_pick_v/lane/body/comp`) hoisted above first use; comments only, zero logic change.
- **No `.strb` AttributeError path**: `it.strb` is read only inside the `it.kind == "write"`
  branch (`env.py:113`), and the monitor sets `.strb` on every write item; read items never
  reach it.
- **Scoreboard compares are live, not dead guards**: the FP-flags compare fires on the very
  STATUS read that shows DONE (busy is cleared first, then the `not self.busy` guard passes);
  the config-read compare is the actual bit-exact check — 70 body words per readback against
  the golden-advanced mirror. `check_phase` honesty asserts (`runs > 0`, `compared > 0`)
  prevent a silently idle scoreboard.
- **Monitor sampling is sound**: RisingEdge + ReadOnly samples the settled cycle-N state
  uniformly on all five channels — one item per handshake-cycle, no double count on
  back-to-back transfers. AW/W/B FIFO pairing is correct for AXI-Lite's in-order semantics,
  including AW/W skew, multiple outstanding, and same-cycle AW+W+B (appends evaluated before
  the B pop); protocol-illegal B-before-AW/W trips the orphan assert. End-of-test item loss is
  precluded by BaseTest's 5-cycle drain before `drop_objection`.
- **F-01/F-08/F-30 "pass (bring-up)" rows are honestly driven**: SmokeSeq programs
  NPAIRS=2/NSTEPS=2 on `benchmark_system()` bodies and the full 70-word readback is
  scoreboard-compared bit-exact vs `emulation.advance` (F-01). CornerSeq's NSTEPS=0 leg reaches
  DONE within 10 polls, compares the unchanged readback, and the CYCLES≤4 branch is reachable
  and fires on the post-DONE CYCLES_LO read (F-08). The K1 check fires on the post-DONE
  CYCLES_LO read in both smoke (÷2) and corner run 2 (÷3, NPAIRS=0 integrate-only) — the
  126.0 / 34.7 figures come from a live bound check plus its logger line (F-30).
- **Golden usage per testplan §4**: the mirror calls `emulation.advance` in place (never a
  re-implementation), pair tuples share the body list objects so chained mutation matches the
  model, i/j byte order matches MAS PAIR[k] encoding, and committed-reuse across back-to-back
  runs (CornerSeq) is modeled by the doorbell-time copy-back. BODY-read-while-BUSY is safely
  ungated (skipped, F-10 todo) rather than mis-compared.

### Summary: 2 must / 5 should / 4 nit

## Resolutions (author, same day)

- Must-1: `_hs()` now asserts `is_resolvable` on every valid/ready it samples (post-reset only);
  the X-free claim is real in Icarus and honestly vacuous-by-construction in Verilator.
- Must-2: STATUS W1C writes now clear the matching FP bits from the scoreboard's sticky mirror.
- Shoulds (W1C efficacy test, busy-tail skew, apply_strb modeling, abort replay, ap ordering
  under a non-blocking driver) are accepted as dv_coverage/sign-off work; noted in testplan
  rows F-12/F-11 territory.

### Summary: 0 must open
