# grape_pipeline — coverage waivers (dv_coverage, 2026-09-06)

- `cg_abort.steps.0`: unreachable by design — ABORT is sampled only at a step boundary
  (uArch §3.1), and reaching a boundary completes a step, so STEPS_DONE ≥ 1 after any ABORTED.
  Testplan bin was defined before this implication was spelled out.
- `cg_abort` ABORTED-with-steps==NSTEPS: unreachable — DONE wins on the final boundary
  (MAS §8); the case is covered by the `done_wins` bin instead.
- `cg_cfg.nsteps.20000`: deferred to `test_full_benchmark` at dv_signoff (testplan §4 names it
  the sign-off input; a 20,000-step run is the sign-off equivalence test, not a coverage test).
- Line/toggle exclusions are inline `// verilator coverage_off` regions, each carrying its
  reason (constant seed ROM, invocation-lifetime counter upper bits, special-path constant
  patterns, doorbell-validated pair-index upper bits, reserved staged-write bits, documented
  always-0 leftover). grape_regs_tb_top.sv is a TB wrapper (testplan §5 exclusion).
