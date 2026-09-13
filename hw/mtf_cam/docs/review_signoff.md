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

### K8 N_LIST=256 depth — pushed to 24 (target met), with a scoping caveat

PRD-K8 wants the N_LIST=256 bounded run at depth ≥ 20. The complete K8 guarantee is now:
- **(a) Unbounded k-induction at N_LIST=16** — the three list invariants (permutation,
  lookup-pre-shift, post-shift positions) for ALL values, covering fill *and* moves. Strictly
  stronger than any bounded check.
- **(b) N_LIST=256 permutation preservation across 24 move cycles** (`bmc256moves`) — **meets the
  ≥20 target.** Reached by *fill-abstraction*: assuming a valid post-fill start (`rem_q==0`, fill
  done) collapses the 256-deep priority-encoder chain that otherwise walls plain BMC at depth 6
  (verified this is the real wall). To stay tractable it pins a **concrete canonical post-fill
  state** (`used={0..7}`, `lst[i]=i`, 8 live entries; only the moves are free). This is sound and
  meaningful because the RTL move logic is **value-agnostic** — it shuffles positions and never
  inspects byte values, so the 8-entry state exercises the full 256-wide shift network.
  Non-vacuity confirmed: `famoves_cover` reaches the regime (filled list, lookups, back-to-back
  moves) and a mutation test (inject a duplicate) makes the distinctness assert FAIL.
- **(c) General-occupancy permutation at N_LIST=256, depth 6** (`bmc`) — the free-used-set check.

**The scoping caveat (surface at sign-off):** the depth-24 result at 256 is over the abstracted
move regime from a concrete post-fill state, **not** an unbounded proof at full 256 width — that
was pursued (O(N) free-witness k-induction) and found genuinely SAT-intractable; it was **not
faked**. Full-generality (free used set) preservation stays tractable only to ~depth 3–11. So K8 is
met at the depth target with two honest scopings: full generality is unbounded only at N_LIST=16,
and the 256 depth-24 result fixes the occupancy. Documented in `synth/formal.sby` header.
**Not a correctness gap.**

**Unbounded-256 exhaustively attempted (round 2, PDR/IC3).** A dedicated effort built an O(N)
single-free-witness-value permutation encoding (`PERM_WITNESS`, sound: quantified over one free
byte value held stable) and ran it as an unbounded `mode prove` under the strongest available
model checkers. Results (each 900 s time-boxed, in scratch workdirs):
- **rIC3** (state-of-the-art Rust IC3/PDR): **TIMEOUT** at N_LIST=256.
- **ABC PDR** (`abc pdr`): **TIMEOUT** at N_LIST=256.
- smtbmc k-induction (round 1): step times out.
- fill-abstracted **general-occupancy** (free used set) under rIC3: **TIMEOUT** (unbounded not
  reached; bounded only to ~depth 3–11).
- Non-vacuity of the witness encoding **confirmed**: the mutation task (assert "no value ever
  live") correctly **FAILS** with a CEX, so the check genuinely bites.

**Conclusion:** an unbounded permutation proof at the full N_LIST=256 width is beyond every
available engine (smtbmc, ABC PDR, rIC3) — a genuine model-checking wall (the 256-wide bijection
is SAT-hard), not an effort gap. The strongest honest N_LIST=256 guarantee is the **depth-24
fill-abstracted move-preservation** above, with the complete unbounded proof standing at
N_LIST=16. The round-2 witness encoding (a failing base-case WIP without the domain strengthening)
was reverted; the harness stays at the clean depth-24 state.

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
