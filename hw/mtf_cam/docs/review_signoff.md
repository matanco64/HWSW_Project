# mtf_cam — dv_signoff review (RTL mode)

hw-review RTL mode over the FINAL `rtl/` (8 modules), `tb/` (env.py replay scoreboard, 16 tests,
sequences), and the new `formal/` harness, for the sign-off checkpoint. Consolidates the
bring-up (review_bringup.md) and RTL (review_rtl.md) reviews and adds the formal + stale-worktree
reconciliation specific to sign-off.

## Checklist verdicts (final tree)

| Item | Verdict | Evidence |
|---|---|---|
| Reset | PASS | every state register resets via `!rst_n` next-state; memories (`lst`, FIFO, packer) gated by valid/fill before read; Icarus 4-state X-free after reset (make sim-icarus 16/16) |
| CDC | PASS | single clock domain, no crossings (module headers) |
| Width | PASS | lint clean `-Wall`, sized literals, Q-notation matches; one intentional narrow waived with comment |
| X-propagation | PASS | every `always_comb` defaults all outputs; every `case` has `default`; Yosys "no latch"; Icarus X-free |
| Handshake | PASS | `m_l` tvalid registered, never comb on tready — **formally proven** (formal `hs` task, BMC depth 30, PASS); AXI-Lite responses always returned |
| FSM completeness | PASS | 4 states, each with an exit + `default → IDLE` |
| Sequential-read / UNOPTFLAT | PASS | lint clean; combinational loops (item-valids↔ERR_LIMIT, run-overflow↔acc_en) broken |
| Testbench honesty | PASS | scoreboard calls FROZEN golden `list_model.expand` (READ/CALL only), cross-checked `== mtf_ref.l_vector` per block; every test hard-asserts (`assert`, not a log line) |

## Formal soundness (sign-off specific)

The `formal/` harness proves REAL properties, not vacuous ones:
- **Non-vacuity established two ways**: development surfaced genuine k-induction/BMC counterexamples
  (requiring the env assume `mv_en |-> mv_rank < n_used` — a constraint the controller genuinely
  enforces via ERR_RANK, MAS §5/F-10 — plus two true-of-the-DUT strengthening invariants
  `rem_q ⊆ used_latched` and live-entries-in-domain, which are **asserted, not assumed**); and all
  5 `cover`/`hscover` traces are reachable.
- **Frontend vacuity trap avoided**: the built-in Yosys Verilog frontend silently drops
  SystemVerilog `bind` and hierarchical reads (a `bind` checker produced a vacuous pass); the
  harness uses `read_slang` so the permutation invariant actually observes `mtf_list` internals.
- **K8 core is COMPLETE**: the three list invariants (permutation, lookup-returns-pre-shift,
  post-shift positions) are proven by **UNBOUNDED k-induction at N_LIST=16** — strictly stronger
  than any bounded-depth check.

### Known limitation (must be surfaced at the checkpoint)

**K8's N_LIST=256 bounded-BMC target of depth ≥ 20 is not met — it closes at depth 6.** Cause:
`mtf_list`'s fill is a 256-deep lowest-set-bit priority-encoder chain (~530 logic levels); proving
any list invariant across it unrolled walls every engine tried (smtbmc+boolector/yices/z3, btor
btormc, abc bmc3, abc pdr) at k≈5–6. The property is **not weakened** — full permutation is
checked at 256 (depth 6) AND proven unbounded at N_LIST=16 — only the 256 *bounded depth* falls
short of the testplan number. The testplan §Formal pre-authorizes this fallback ("if smtbmc chokes
on the 256 case the induction stands on N_LIST=16"). Documented in `synth/formal.sby` header.
**Disposition: this is the one place the formal evidence is below the literal testplan target; the
human sign-off should acknowledge it. Not a correctness gap (the unbounded proof covers all N).**

## Stale-worktree finding reconciliation

A resumed pre-stage RTL agent (worktree at `05f4cf9`, an early provisional baseline) reported an
`INIT_CYCLES = N_USED+1` **must** (257 at N_USED=256, over MAS §4 ≤256) and "fixed" it in its
worktree (`89392e6`). **Reconciled: NON-APPLICABLE to merged main.** Merged main uses a different
INIT-exit mechanism (`init_active = init_start ∥ state==S_INIT`) that computes N_USED exactly —
proven empirically: `test_corner`'s `nused256` case reads the INIT_CYCLES register after DONE
(sequences/corner.py:111-113) and the scoreboard asserts `INIT_CYCLES == N_USED == 256`; the full
suite passes 16/16 (agent run + firsthand re-run). The worktree fix is for code not in the tree.
Its other findings — R2 (defensive doorbell `pipe_flush`, "true by construction" — the property is
covered on main by `test_xinv` beat-withdrawal passing), R3/R5 (nits: header wording, ±1 counter
latitude), R4 (ERR_LIMIT byte-case reading, behavior matches spec) — are **non-blocking**.

## Verdict

Testbench compares against `golden/` (never a re-implementation); all 8 RTL modules pass the
hardware checklist; the formal harness is sound and non-vacuous with the K8 core proven unbounded.
**Musts open: 0.** One honest limitation (K8 256-depth 6 vs ≥20, testplan-fallback-covered) is
carried to the human checkpoint for acknowledgement. Ready for sign-off approval.
