# huffman_engine — dv_bringup review (RTL mode)

Adversarial agent review of `git diff fc47cb2..HEAD -- hw/huffman_engine/{rtl,tb}` (the R23
aligner fix, the R1 stall-credit fix + declaration hoists, and the new pyuvm bench). The agent
traced every checklist item through source, ran the arithmetic on the bench vector, and
executed the R23 tkeep computation. 13 findings.

## Findings and dispositions

| id | sev | location | problem | disposition |
|---|---|---|---|---|
| B1 | must | huff_out.sv:75 + cocotb_run.py | the push-while-full assertion (and grape's SVAs in grape_accum/grape_pipeline) sit behind `ifdef SIMULATION`, which **no build defined** — the guard for the changed invariant never compiled | **FIXED**: `-DSIMULATION` added to cocotb_run.py build args for Verilator and Icarus; clean-dir rebuild + full rerun green (armed) |
| B2 | must | tb: no top-level test drops m_sym tready | the stall-credit withdrawal corner (tready falls exactly as C1 pushes → occ hits 2) had zero dynamic coverage | **FIXED**: `smoke_backpressure` test added — deterministic alternating pause on `sym_sink` guarantees the corner; trace-exact scoreboard + the now-armed B1 assertion are the checkers |
| B3 | should | tb/vectors/dump_bench.py | committed bin/json from different generator runs; a regenerated tail (144 b) would exceed the 128-bit acceptance window and silently lose the TLAST regime | **FIXED**: keep = end_byte + 10 with `tail ≤ 128 bit` assert; bin+json regenerated in one run (both 67,562 B) |
| B4 | should | tb/env.py `_frame_bytes` | invocation segmentation assumes every TLAST is accepted; leftovers desync a following doorbell; queued source beats can bleed across invocations | open — **dv_coverage entry criterion** (multi-block F-13 requires it): tag beats by doorbell epoch or drain sources between invocations |
| B5 | should | tb/env.py doorbell handling | scoreboard treats every CTRL bit0 write as accepted: no BUSY-reject, no ABORT priority, no ERR_PARAM/ERR_TABLE rejection, mirror records BUSY-discarded writes | open — **dv_coverage entry criterion** (F-09/F-11 tests will desync without it) |
| B6 | should | tb/env.py + smoke.py run_to_done | completion = first `!BUSY && DONE` read without requiring an observed BUSY=1 — stale sticky DONE can complete a not-yet-run invocation (grape S1 applied halfway) | open — **dv_coverage entry criterion**: require seen-BUSY between doorbell and completion in both places |
| B7 | should | tb/env.py AxisMonitor | tdata/tkeep/tlast read without is_resolvable checks on accepted beats (vacuous on 2-state Verilator) | open — dv_coverage: add resolvable asserts; 4-state leg exists (`sim-icarus` runs the full suite) |
| B8 | should | huff_deflate.sv D_DIST (pre-existing, F-25-gated) | `limit_stop` rising between length and distance issues livelocks D_DWAIT (no beat, no limit_hit) | open — must close before un-gating F-25 (test_deflate) |
| B9 | nit | tb/env.py | unused `k1_enforce`/`STICKY_MASK` imply a scoreboard K1 check that doesn't exist | open — wire or delete at dv_coverage |
| B10 | nit | tb/sequences/smoke.py pack_lengths | `alphabet` unused; untouched stride words not zeroed → cross-program ERR_TABLE risk on reuse | open — dv_coverage (multi-program sequences) |
| B11 | nit | tb/unit/test_aligner.py | deflate keep choices miss 0x1/0x7; module docstring stale (says unconditionally MSB-first) | open |
| B12 | nit | tb/unit/test_aligner.py R23 test | uses private `rd._bit`; comment assumes 7-byte fragment | open |
| B13 | nit | tb/env.py counters | SYMBOLS/BITS compared only if read (both tests do read them); OVERFETCH logged, not checked | open — OVERFETCH expectation at dv_coverage |

## Verdict (agent's conclusion)

The RTL changes survive the attack: the aligner reverse composes with tkeep for all tail
cases and mode is latched idle-only; the stall credit cannot underflow, the skid-occupancy
induction closes (occ ≤ 2 always, including tready dropping as C1 pushes), tvalid stays two
flops from tready (PRD-F6), and the hoists are mechanical. What the green run hid was
demonstration, not correctness: B1's assertion never compiled, B2's corner was never
stimulated. Both are fixed and re-run; B3–B6 are recorded as dv_coverage entry criteria.

Musts open: **0** (B1, B2 fixed with the edits named above; evidence: clean-dir
`make sim SIM_BUILD=sim_build_b1` 3/3 PASS with `-DSIMULATION` armed, `sim-icarus` 3/3).
