# Hardware-flow lessons

Appended by `hw-advisor` after each gate; one entry per lesson (date, module/stage, friction, fix).

## 2026-08-28 — grape_pipeline/prd

- **Skill invocation bug** — `hw-prd` step 2 says "run the interview with `grill-with-docs`", but
  that skill is `disable-model-invocation: true`; the Skill tool refused it (session 2026-08-28).
  Fix: `hw-prd` (and `hw-mas`/`hw-uarch` if they say the same) should invoke `grilling` +
  `domain-modeling` directly and keep the paper trail itself (`hw/CONTEXT.md`, `hw/docs/adr/`).
- **Golden-model convention discovered late** — `golden/README.md` requires the golden model to
  *wrap* `benchmarks/bm_*` (import + instrument), never re-implement; the first draft of
  `nbody_ref.py` was a copy and had to be rewritten (friction.jsonl 2026-08-28T12:04:00Z). The
  convention lives only in the per-module README. Fix: state it in `hw-prd` (the stage that first
  touches `golden/`) and in FLOW.md "Conventions".
- **Tolerances need a calibration step** — the PRD's fidelity bounds (F4/F5) could not be written
  without first running emulation-vs-golden in Python (`golden/calibrate.py`): the naïve
  "|ΔE/E| ≤ 1e-12 energy conservation" was wrong by 8 orders of magnitude (the integrator itself
  drifts 4e-4). Fix: `hw-prd` gets an explicit "calibrate any numeric tolerance in software before
  writing the number" step; same lesson applies to `huffman_engine` throughput claims.
- **`source hw/env.sh` is cwd-relative** — failed when the shell was inside `hw/<module>/golden`
  (friction 12:04:00Z). Fix: skills say `source "$(git rev-parse --show-toplevel)/hw/env.sh"`.
- **Friction-hook noise** — two "failures" (exit 2) were `ls` of a not-yet-existing directory
  inside read-only inspection commands; not friction. Consider ignoring exit codes from commands
  whose first word is `cat`/`ls`/`grep`/`head` in `friction_hook.py`.

## 2026-08-28 — huffman_engine/prd

- **The benchmark file is a moving target** — `benchmarks/bm_pyflate/run_benchmark.py` is now
  Matan's optimised T3 code (commit da971fc), so "wrap the benchmark" would have wrapped the wrong
  algorithm. The stock algorithm lives in `dev/pyflate/t0_stock.py`. Fix: `hw-prd` step 3 says
  "wrap the *upstream* benchmark code (pin the commit or the `dev/*/t0_stock.py` copy), and
  cross-check the golden against a C library (`bz2`, `zlib`) where one exists".
- **Reference-model bookkeeping can be wrong** — stock pyflate's `tellbits()` drops 16 bits
  (copy-constructor bug `self.count = x.bitfield`); the first golden trace had every bit position
  off by 16 and the emulation model "failed". Fix: golden wrappers count consumed bits themselves
  (patch the read primitive), never trust the reference's own position/size reporting; and the
  first debugging step for a golden-vs-model mismatch is "which side is wrong?" — the user's Q8
  instinct ("maybe the golden model is wrong") was the right one.
- **Software work changes the Amdahl story** — after T3, the Huffman/MTF loop is ~39 % (not
  75 %) and iBWT is co-equal; the PRD now quotes both baselines. Fix: `hw-prd` agenda says "read
  the software teammate's latest findings (`dev/<bench>/FINDINGS.md`) before setting KPIs; quote
  the speed-up against both the stock and the optimised software".
- **`source ./hw/env.sh` from a module directory failed again** (friction 20:03:29Z) even after
  the previous lesson — `env.sh` itself is already cwd-independent; the *path to it* is not, and
  an ad-hoc `cd hw/<module>/golden` earlier in the same shell broke it. Fix: every hw-* skill
  command block starts with `cd "$(git rev-parse --show-toplevel)"` on its own first line (one
  rule, no per-command path arithmetic).

## 2026-08-30 — mtf_cam/prd

- **Index mapping misread** — the first emulation model used rank = symbol − 2 (assuming
  "symbol 2 = rank 0"); pyflate does `favourites[r − 1]`, so rank = symbol − 1 and rank 0 never
  occurs (friction 07:25:33Z). Fix: `hw-prd` step 3 says "quote the reference's index expression
  verbatim in the emulation-model docstring before writing the model".
- **Captured reference values need type normalisation** — pyflate's list holds 1-byte `bytes`
  objects, the model emits ints; the per-symbol comparison failed on type, not value
  (friction 07:25:51Z). Fix: golden wrappers normalise captured values to ints/bytes at capture.
- **Reuse across modules worked** — `mtf_ref.py` imports the huffman golden wrapper instead of
  re-instrumenting pyflate; one instrumentation point per benchmark. Keep: FLOW.md convention
  "one golden wrapper per benchmark, per-module goldens import it".
- No skill-level friction otherwise; the `cd "$(git rev-parse …)"` rule held (0 env.sh failures).
- **Formula cycle models lie** — the first K3 model (`ceil(n/W) − k`) credited overlap the
  hardware cannot have (n is unknown until the run group ends); the reviewer caught it and the
  honest number moved from 1.072 to 1.370 (serialised) / 1.063 (with an 8-item FIFO). Fix:
  `hw-prd` step 3 says "a cycle claim comes from a two-sided *simulation* with named resources
  (queues, ports, widths) and a printed sweep, never from a closed-form estimate".

## 2026-08-30 — grape_pipeline/mas

- **A scaffold cell is not a contract** — the MAS assumed `hw/common/rtl/axi_lite_regs.sv` could
  carry W1C, write-pulse, ignore-while-BUSY and delayed BRESP; the reviewer read the RTL and it
  cannot. Fix: `hw-mas` step 3 says "read the shared RTL cells the spec relies on and write a
  'delta to the shared cell' subsection (or `n/a`) before the register map is final".
- **No headless Chromium here** — `mmdc` cannot launch in this WSL; `tools/hw/blockdiag.py`
  renders `.mmd` + `.svg` from one JSON spec with no dependencies. Keep: all three modules use
  it so the report's diagrams share one style; `mermaid.ink` via curl stays the backup.
- **Shared decisions first, then the module** — Q1–Q2 (bus width, register conventions) became
  ADR-0001 (accepted) and ADR-0005 before any grape-specific offset was written; the next two MAS
  rounds inherit them and should take one round each.

## 2026-08-30 — huffman_engine/mas

- **Doorbell-time vs run-time checks must follow the datapath** — the PRD classed an
  over-subscribed table as a doorbell-time rejection; the reviewer noted the Kraft sum only exists
  after the build's count pass. Fix: `hw-mas` agenda line "for every ERR_* decide *when* the
  hardware can know it (doorbell / build / per symbol) and hold BRESP only for doorbell-time checks";
  record PRD errata in the PRD file rather than silently editing an approved requirement.
- **Stream ports need a DMA life-cycle rule** — after DONE/ERR/ABORT the source/sink channels are
  mid-transfer; without a "stop and flush before every doorbell" rule the multi-block test is
  unspecifiable. Fix: `hw-mas` agenda line for stream modules.
- **A shared driver base needs a shared exit rule** — `wait_done` "until DONE|ABORTED" fails for
  modules whose errors end with BUSY = 0 and DONE = 0; "return when BUSY = 0" is the universal rule
  (hw-integrate lifts it into `AccelDriver`).

## 2026-08-30 — mtf_cam/mas

- **Chained modules need a failure-propagation rule** — with `m_sym → s_sym` wired, an error in
  either module deadlocks the other (one waits for EOB, one for `tready`); the MAS now makes the
  chained driver abort the partner. Fix: `hw-mas` agenda line "for chained modules state what
  happens to the partner on ERR/ABORT/timeout".
- **Third MAS took one round** as predicted: with ADR-0005/0006 and the DMA rule inherited, only
  six module-specific questions remained. Keep the shared-decisions-first order for uArch too.

## 2026-09-04 — grape_pipeline/uarch

- **The mtf_cam lesson generalised and paid off** — the hand-derived §7 latency (124) hid two
  structural impossibilities (145 mul-ops/step through 2 units; an FMA accumulate that silently
  broke bit-exactness). The cycle-accurate 290-op schedule model (`docs/schedule_model.py`) gave
  the real numbers (123/127) and picked the inventory (3 add/3 mul; 2 add/3 mul fails the worst
  corner by exactly 1 cycle). Fix: `hw-uarch` step 4 says "the latency/throughput gate row cites
  a schedule *simulation* over the full op graph, never a stage-sum".
- **Fusion is the default failure mode of FP datapaths** — "use an FMA for a·b+c" is reflexive
  and wrong wherever the reference rounds twice. The op graph in the schedule model doubles as
  the fusion audit: one node per Python rounding.
- **Spike before grilling worked** — the FP64 sourcing agent (CVFPU 1-ulp red flag, yosys-slang
  requirement) turned Q1/Q6 from opinions into decisions with citations.

## 2026-09-05 — grape_pipeline/rtl (stage in progress)

- **`yosys | grep '^ERROR'` is a false green** — Yosys prefixes errors with `file:line:`, so two
  "synth-checked" blocks had never parsed. Fix: grep bare `ERROR`; better, the `make area` target
  is the only synth evidence that counts (it fails loudly).
- **Yosys 0.68 SystemVerilog potholes** (now in the module headers): no struct members on
  unpacked-array elements, no bit-selects on function calls, no unpacked localparam arrays, no
  in-module `import` — write parallel arrays / hoist to locals / case-functions / scoped refs.
- **The reviewer beats lint where it matters** — all five silent-corruption/hang bugs (shadow
  mis-tagging, two missing one-cycle forwards, scoreboard index, uncounted retires) were
  lint-clean. The adversarial trace of issue/retire edge arithmetic is the highest-value review
  instruction; keep it verbatim in future RTL reviews.
- **Contract-first parallel unit builds worked** — three agents built four FP64 units against
  `rtl_contracts.md` + the numpy oracle with zero interface rework at integration; the one
  cross-agent artifact (`fp64_pkg.sv`) landed without collision. Keep: binding contracts + an
  executable oracle before dispatching parallel RTL agents.
- **Rate-limit interruptions are cheap to absorb** — SendMessage resume continued all three
  agents from their transcripts with no lost work.
- **Dynamic engines need their unit TB before review, not after** — `grape_regs` (unit-tested
  first) survived review with 1 bug; `grape_accum`/`grape_force_pipe` (no unit TB, "golden
  comparison at bring-up") collected 9 findings across two passes, and two pass-2 musts (S1/S2)
  were regressions introduced by pass-1 fixes — exactly the class a synthetic-stream unit TB
  (fake op streams, check counters/ordering/all_done) would catch in minutes. The "no cheap
  oracle" exemption is real only for pure FP datapaths; issue/scoreboard/retire logic always has
  a cheap oracle. Evidence: review_rtl.md, git churn grape_accum ×4.

### Addendum (area gate, same stage)

- **Yosys constant case-functions are a trap at scale**: a constant-arg function call is inlined
  as its whole case tree at every call site — 200-entry case × ~30 sites × 200 unrolled
  iterations never terminates. Packed `localparam` vectors read with `[e*W +: W]` fold at
  elaboration. `hw-rtl` ROMs should be packed vectors, case-functions only for handfuls of
  entries.
- **Dynamic array reads through intermediate variables defeat mem2reg**: `arr[v]` where `v` was
  just assigned a constant-foldable expression still becomes a full-depth read mux. Index with
  the foldable expression directly.
- **Keep wide comb views out of big guarded processes**: a 12,800-bit array view built inside a
  200-guard `always_comb` sends every bit through the whole PROC_MUX decision tree (44,706
  items). In its own `always_comb`: 3,216. Split view construction from consumers.
- **Synthesis-runtime is a gate concern, not just synthesizability**: lint-clean + parse-clean
  said nothing about the 4-hour mem2reg blowup. The area gate must actually complete before the
  stage closes (it did, this time, only after three restructurings).

## 2026-09-05 — grape_pipeline/dv_testplan

- No command friction (0 friction.jsonl entries; the stage is document work). Review friction
  pattern worth keeping: **both passes' hard findings were reference-model conflations** — the
  plan said "expect 0" against the wrong golden (emulation vs nbody_ref) and dropped the PRD's
  split r/v tolerance. When a module has two references (op-order emulation + benchmark libm),
  every tolerance line must name which reference it binds to. `hw-dv-testplan` step 5 already
  demands the tolerance policy; the sharpening is "per reference, per quantity" — carried as a
  proposal below rather than applied (one data point).
- Second data point for the "review catches what generation glosses" series: 8 musts across 2
  passes on a 26-row matrix written from the specs it traces to.

## 2026-09-05 — grape_pipeline/dv_bringup

- **The first full-chip sim caught a silently-dropped-op bug in under an hour** that lint, Yosys,
  two RTL review passes and four unit TBs all missed: the schedule ROM's global unit ids (3..5 =
  MUL) were indexed into the 3-lane mul buses as `ev_unit[1:0]` — unit 3 wrote out of bounds
  (op vanished), 4/5 landed on wrong-but-consistent lanes. Symptom chain: divzero flag +
  STEPS_DONE stuck. Vindicates the narrowed hw-rtl rule: an issue engine's unit TB (or the
  module smoke) must run BEFORE review sign-off; a top-level smoke would have caught this at the
  RTL stage.
- The Verkor debug flow (VCD → vcd2csv → reason over the table) found it in three dumps:
  FSM/counters first (localised the hang), then issue/ovalid valids (localised the lane), no
  waveform GUI needed. Worth keeping as the default `hw-dv-bringup` debug loop.
- cocotbext-axi API drift: `write_dword`/`read_dword` return None in the pinned version —
  use `write(addr, bytes)`/`read(addr, n)` whose results carry `.resp`/`.data` (the regs unit TB
  already knew; the shared driver didn't).
- Icarus binds identifiers in declaration order: forward uses that Verilator/Yosys accept are
  elaboration errors (`Unable to bind`). Declare before first use in shared RTL.
- Replay-in-check_phase scoreboarding (single monitor stream, mirror replayed in bus order)
  needed zero concurrency and survived both simulators unchanged.

## 2026-09-06 — grape_pipeline/dv_coverage

- **Two scoreboard-model bugs surfaced only under random stress**, both spec-faithfulness gaps:
  (1) completion detection keyed on sticky DONE — but PRD-F12 lets stale DONE survive a
  doorbell; the live BUSY bit is the only sound completion signal. (2) K1 enforced on random
  pair lists — duplicate pairs build accumulate chains deeper than the static window and
  legitimately exceed 128 cycles/step (worst seen 165); the KPI binds on the benchmark list.
  Both are things a testplan review can't catch — only stimulus can.
- The NaN-canonicalization compare (contract +qNaN vs numpy's sign-carrying NaNs) fired the
  moment the FP test read state back — the testplan §4 canonicalization clause paid off,
  written before any NaN ever crossed the bus.
- Toggle closure was 60% exclusions by volume: constant ROMs, lifetime counters, validated-index
  upper bits, special-path constants. Writing the reason inline at each coverage_off beats a
  central waiver list for reviewability; the two architecturally-unreachable functional bins
  (abort-steps-0, ABORTED-at-final) were testplan definition errors worth recording.

## 2026-09-06 — grape_pipeline/dv_signoff

- **The KPI failed only on the real workload**: K1 measured 162 cycles/step at sign-off after
  every earlier stage was green — smoke (126) used NPAIRS=2 where the static table hides the
  accumulate phase; the model's 123 assumed uArch §3.3's "everything else overlaps", which the
  RTL didn't implement (single-issue accumulate AND single-issue globally-gated integrate).
  Two widenings (3-wide in-order accumulate scan; per-lane multi-issue integrate) landed K1 at
  124 — inside the model's 123..127 window. Lesson for `hw-dv-bringup`: measure the KPI on the
  full-shape workload (all pairs) at bring-up, not only the tiny smoke — the gap was visible a
  stage earlier for anyone who ran 10 pairs.
- **`pgrep -f` self-matching burned four separate process-management rounds**: monitors
  watching for a command string matched each other and their own wrapper shells; kills hit
  wrong pids; two concurrent synths overwrote one log. Rules now: watch a LOG outcome line,
  never a process-name pattern; capture the real worker pid (not the setsid wrapper) if a pid
  is needed; one synth per module directory at a time.
- Review pass-2 on the rewrite found zero functional bugs but produced a proof list
  (slots_used wrap impossible, lane_hold covers issued-this-cycle, busy_bc no holes) that went
  straight into uArch §3.4 — reviews that prove invariants are documentation.
- cocotb poll budgets: a fixed max_polls sized for the expected cycle count expired 1% short
  of the finish line and cost a 5-minute rerun; budget 2x the estimate, poll on BUSY-fall not
  sticky DONE (stale-sticky vacuity, review S1).

## 2026-09-08 — huffman_engine/uarch

- **The reviewer caught an inverted comparator before a single line of RTL existed** (U1: the
  ≥-first_code form decodes every table as length-1; the correct one-sided form is
  <-limit_la with smallest-match-wins, proven with a counterexample and then re-proven in
  pass 2 via the canonical recurrence). Two more passes drove 24 findings to zero — the
  document now carries the invariant proofs the RTL will be reviewed against.
- The C0-visibility question ("which decode-stopping events can the loop know about in its
  own cycle?") reshaped the design twice (per-set EOB latch; DEFLATE demoted to II=2). Asking
  it explicitly at uArch beats discovering it as a hang at bring-up (grape's retired-count
  lesson, applied a stage earlier — the loop tightens).
- A uArch fix reached BACK into the MAS (lengths-window strides amendment) — address-based
  attribution needed a layout the approved MAS didn't have. Post-approval amendments with
  dated bullets worked; the alternative (pending-register attribution) was unfixable.
- Folding derived state into write paths (counts, invalid bins) keeps buying margin: K2 went
  from zero-margin to 1.88x, and the doorbell-time MAXLEN/Kraft checks fell out for free.

## 2026-09-08 — huffman_engine/rtl

- **Contract-first parallel build, second data point**: three agents (regs 13/13, aligner
  12/12, builder+tables 5/5 — the latter two mutation-vacuity-checked) + an own-built serial
  core integrated with ZERO interface rework, and the full-chip smoke passed on the FIRST run
  (grape's first integration sim hung on a lane bug). The differences: binding contracts
  written before any RTL, unit TBs before review, and a top-level smoke at the RTL stage.
- **The review still owned the integration layer**: 3 passes, 19 must-level findings, every
  one in hand-wired top/ctrl/lifecycle code (skid overflow accounting, pulse-vs-level
  handshakes, cross-invocation state, drain/abort dispositions) — none in the TB'd leaves.
  Fixes-of-fixes needed their own verification pass twice (R3's first fix un-stalled exactly
  the wrong cycle; pass 3 found the same hole mid-run). Selector-style engines want a TB case
  per BOUNDARY (entry, 50-boundary, exhaustion), not per feature.
- Reviewer-driven TB additions (boundary_refill_stall) are the regression the next module
  inherits; a reviewer that says "the unit tests can't see this" should trigger a test, not
  just a fix.

## 2026-09-08 — huffman_engine/dv_testplan + grape_pipeline/ppa (partial)

- **The testplan reviewer executed the golden model** and caught an EOB double-count that
  three careful readings missed (`syms` already ends with the EOB; the plan added one more).
  New bar for testplan reviews: every golden-interface claim gets run, not read.
- A must-priority error flag reachable only through a gated should-priority test (ERR_SYMBOL
  behind the DEFLATE gate) is a waiver hiding in a schedule; the fix is to commit the gate's
  resolution as the first bring-up task and lift the test to must.
- PPA trade-off tables are best built from MEASURED points that already exist in git history:
  the K1-fix pair (393k/2.94mm²/K1=162 vs 584k/4.08mm²/K1=124) is a stronger §7 exhibit than
  any synthetic parameter sweep — both points fully verified when they were HEAD.

## 2026-09-08 — grape_pipeline/ppa (OpenLane runs 1–4)

- **A config variable set blind cost a full run**: `SYNTH_NO_FLAT` is OpenLane 1 vocabulary;
  OpenLane 2 warned "deprecated ... see SYNTH_HIERARCHY_MODE" in the log's first three lines,
  ignored it, and flattened anyway — run 4 marched 2.5 h into the identical OOM as runs 2–3.
  The tell was available twice at launch time (the WARNING, and the variable's absence from
  `runs/<tag>/resolved.json`) and nobody looked. New bar for any long background EDA run:
  within a minute of launch, read the log head for config warnings and confirm every variable
  you set appears in the tool's resolved/echoed config. Skill: `hw-ppa` step 4.
- **Flat synthesis of a ≥ 0.5 M-cell design is an OOM, not a slowdown, on a 15 GB host**:
  yosys' techmap of wide-arith cells (`$alu`/`$lcu`) during FLATTEN peaked past 15 GB and the
  kernel killed it silently — the only symptom is a log frozen at the SAME byte count run
  after run (deterministic input ⇒ deterministic death point; 32.67 MB twice, 32.32 MB with a
  changed config). `SYNTH_HIERARCHY_MODE: deferred_flatten` synthesizes per-module (peak
  3.3 GB here) and still hands the physical flow a flat netlist. Set it up front whenever the
  step-2 fast gate reports ≳ 300 k cells. Skill: `hw-ppa` step 4.
- (Runs 1–2 died with session restarts — the setsid-survival and log-watching lessons from
  dv_signoff apply unchanged; no new instruction.)

## 2026-09-08 (late) — grape_pipeline/ppa (run 5 falsifies the run-4 lesson)

- **The deferred_flatten remedy was wrong in mechanism**: run 5 (deferred_flatten, verified in
  resolved.json) died at the SAME point as run 4 — ~18 min in, mid-techmap, logs 486 B apart
  (exactly run 4's deprecation-warning block). One yosys process holds the whole design in
  every SYNTH_HIERARCHY_MODE; the knob moves WHEN flatten runs, not the peak. Per-module
  plain-yosys measurements (3.3 GB) predicted nothing about OpenLane's process. The durable
  rule is a memory BUDGET, not a hierarchy knob: OpenLane's synlig-loaded yosys peaked ~3× plain
  Yosys on the same RTL (7.5 → >20 GB); when 3× the plain-yosys peak approaches host RAM, raise
  the host first (WSL: 50%-of-RAM default; `.wslconfig` memory=/swap= + `wsl --shutdown`).
  Skill: `hw-ppa` step 4 (corrects the entry applied earlier today).
- **Instrument before re-running a suspected OOM**: two runs were spent inferring memory death
  from frozen byte counts; a 5-line RSS sampler alongside the launch turns the next failure
  into a number. When comparing frozen log sizes across runs, subtract the log-head config
  echo first — 486 B of deprecation warning nearly masked that runs 4 and 5 died identically.

## 2026-09-12 — grape_pipeline/ppa (runs 6–7) + scope check

- **Read the assignment before campaigning**: days went into OpenLane signoff before anyone
  re-read `project_instructions.md` §7 — "You are **not expected to synthesize**… discuss the
  **expected** trade-offs." The Yosys numbers + the measured two-point K1 trade-off already
  exceeded the requirement; OpenLane was bonus material all along. New rule: a stage skill's
  first step names the REQUIREMENT SOURCE (course doc §, PRD row) its gate serves; when a
  gate's cost explodes (>2 failed runs, >1 day), re-read that source before the next retry.
  Skill: `hw-ppa` (and the pattern generalizes to every `hw-*` stage).
- **OpenLane runs are resumable mid-flow** — `openlane --run-tag <tag> --from <Step.Id>`
  reuses every completed step's `state_out.json`. Two VM deaths cost ~zero recompute once
  this was used; the days lost earlier to restart-from-scratch were unnecessary. Skill:
  `hw-ppa` step 4.
- **An unachievable clock poisons more than timing**: at 20 ns (WNS −128 ns), repair_timing
  inserted thousands of futile buffers, and the bloated netlist then congested global routing
  into a known OpenROAD crash (GRT-0607, twice — second time after GRT_ADJUSTMENT 0.15 bought
  1.3 h). At 150 ns the same design met timing (+60 ns WS), repair was minutes, and routing
  entered far leaner. Measure first (post-CTS STA gives true Fmax cheaply), then set
  CLOCK_PERIOD ≈ 1.5× the measured worst path for the signoff run. Skill: `hw-ppa` step 4.
- **`pgrep -f` self-match bit AGAIN** (the dv_signoff lesson, re-learned verbatim): a
  post-restart "driver ALIVE" verdict was the checking shell matching itself; the run had
  been dead 4 h. The lessons file documented it; the check was still typed from habit.
  Process-shaped lessons need to live in the COMMANDS a skill prescribes (`ps -eo comm=` by
  name), not only in prose. Skill: `hw-dv-signoff` overlay already has it; `hw-ppa` monitor
  guidance now needs the same concrete command.
- **Laptop sleep freezes the WSL VM**: wall-clock tripled on every long run (12.7 h and 6.8 h
  frozen gaps); "no progress for days" was ~1.5 days of compute. Diagnose with step-log
  mtime gaps + RSS-growth-rate vs wall time before blaming the tool.

## 2026-09-12 — huffman_engine/dv_bringup

- **The measure-KPIs-at-bring-up rule paid for itself in one stage**: the first full-shape
  run showed K1 = 1.5068 vs model 1.0068 — a 1.5× throughput bug (the R1 almost-full gate
  didn't credit the same-cycle pop, stalling every third cycle against a ready sink) that
  every unit TB and the 5-beat smoke were structurally blind to. One-line fix, K1 landed on
  the model EXACTLY. Corollary: almost-full gating without a pop credit is a classic II bug;
  the corner it introduces (credit withdrawn as the sink stalls) needs a top-level
  backpressured test, which unit TBs cannot express.
- **An `ifdef` guard is a claim about the build, and nobody had checked it**: every
  `ifdef SIMULATION` assertion in the repo (huffman's skid guard AND grape's signoff SVAs)
  was dead — no build ever defined SIMULATION. Found only when a reviewer asked "what
  demonstrates the changed invariant?" Fix: `-DSIMULATION` in cocotb_run.py both sims;
  grape re-regressed with SVAs actually armed. Rule: when citing an assertion as evidence,
  grep the build command for the define that compiles it.
- **A dated amendment that doesn't rewrite the sentence it amends leaves two truths**: the
  MAS LEN-window row still said packed-continuous while the 2026-09-08 amendment (and the
  RTL) said 48-word strides; the first TB consumer packed per the stale row and burned a
  debug cycle on a build-time ERR_TABLE. Amendments must edit the original row/sentence and
  keep the dated note as history — one source of truth (writing-for-agents).
- Scoreboard/monitor potholes worth keeping: an AXIS monitor must derive byte lanes from the
  bus width (an 8-bit no-tkeep stream is 1 lane, not 4 — the selector list quadrupled
  silently); committed vectors must be regenerated by their committed generator in the same
  run (bin/json from different runs diverged and the "slack" comment was wrong vs the
  128-bit acceptance window).

## 2026-09-12 — huffman_engine/dv_coverage

- **A gated feature is an unverified feature — un-gating it at coverage found a real RTL bug
  in ONE run.** DEFLATE (F-25) was gated off through RTL and bring-up; the first top-level
  DEFLATE stream exposed `huff_deflate` recomputing the length/distance extra-bit COUNTS
  combinationally in the consume states, where `c1_sym_i` had already advanced past the pair
  — count read 0, extra bits never consumed, distance decode misaligned by the length's extra
  bits. Latching the counts with their symbol (as the bases already were) fixed it. Rule: a
  multi-cycle FSM that reads a pipelined input across several states must LATCH every field it
  needs, not just the obvious ones; and coverage must un-gate every gated feature, never carry
  the gate to signoff.
- **Isolate an II>1 bug by shrinking the extra-bit count, not the stream.** The failing
  benchmark-shaped case had many copies; a single copy with 0 extra bits PASSED, a single copy
  with 1 length-extra bit FAILED — that two-case bisection named the bug (extra-count latching)
  in one iteration. A temporary `ifdef`-guarded consume-trajectory $display, diffed against the
  golden BitReader's bit positions, localized it to the exact cycle.
- **The doorbell-acceptance model belongs in the scoreboard from coverage's first line.** The
  bring-up scoreboard trusted TLAST for invocation segmentation and treated every CTRL write as
  accepted; the moment random/error/abort sequences arrived that desynced. Rebuilding it around
  timestamped invocation windows + a modeled acceptance predicate (BUSY-reject, ABORT priority,
  ERR_PARAM/ERR_TABLE) + a sticky-STATUS mirror let 3 parallel agents write ~700 invocations of
  stimulus with zero scoreboard edits. Predictor stays on golden primitives only.
- Parallel-agent finding harvest (all real, tracked for signoff): huff_regs folds ALL six LEN
  fields into the Kraft bins alphabet-blind (stale stride tails false-fire ERR_TABLE on a
  shrunk alphabet — driver must zero uncovered words, now in pack_lengths); DBG kind-3 index
  range check is `< 288` not `< ALPHABET`; same-cycle selector-error withdrawal drops the
  boundary symbol's beat (legal ADR-0006 withdrawal the predictor doesn't model); cocotbext
  `clear()` doesn't flush an in-flight frame (hard_flush kills+restarts the engine).

## 2026-09-12 — huffman_engine/dv_coverage (toggle closure)

- **Raw toggle coverage has a per-design floor set by signal structure, not stimulus.** A
  comparator-cascade control/storage module floored at ~74 % raw and ~84 % after inline
  waivers on every architecturally-unreachable wide signal; a width sweep (≤16 b 84 %, ≤8 b
  89 %, ≤4 b 90 %, ≤2 b 92 %) showed the remaining unhit bits are minority bits inside
  otherwise-well-toggled moderate-width registers, where a declaration-level `coverage_off` is
  net-neutral (it removes more hit points than missed). grape's FP64 datapath reached 96 %
  naturally because full-range values flip nearly every bit. Lesson: the 90 % toggle target is
  calibrated for datapath modules; for control/storage modules, measure toggle over the
  control subset (`--coverage-max-width`) with the wide datapath waived, and say so — don't
  claim a full-signal 90 %. Two mechanisms, both documented: inline regions for the *named*
  unreachable cases (the "why"), the width cap for the moderate-width residual.
- **Prove the gap is structural before waiving.** Two purpose-built stress tests
  (`deflate_all_codes`, `deep_tree`) that exercised every code and the full length range moved
  raw toggle only 1.3 points — that empirical result is what justifies the waiver, versus
  waiving on assertion. Push stimulus first, then waive what it can't reach.
- **dv_coverage is where gated features get un-gated, and that finds bugs.** Un-gating DEFLATE
  (F-25) at coverage exposed a real extra-bit-count latching bug in one run; the DBG range
  check `< 288` vs `< ALPHABET` fell out of the max-config fill test. A feature carried behind
  a gate to signoff is an unverified feature.

## 2026-09-12 — huffman_engine/dv_signoff

- **A sign-off reviewer's "should" can be a false positive, and the test suite is the arbiter.**
  The review flagged S1 (flush-cycle handshake "race" lets a beat transfer during withdrawal).
  Implementing the fix (mask tvalid/take with !flush) broke errors_runtime: ERR_NOCODE expects
  the N valid symbols before the erroring one to be delivered, and the flush-cycle transfer IS
  that intended delivery — flush withdraws only beats not yet handshaked AFTER this cycle.
  Reverted with an in-code rationale. Lesson: at sign-off, verify a reviewer's proposed fix
  against the regression before trusting it; a green→red on a fix is evidence the original was
  right. Fixing S2-S5 (real: DEFLATE underrun beat suppression, dead code, explicit reset) and
  rejecting S1 is the correct disposition.
- **Un-gated DEFLATE + a full-file sign-off trace is where the robustness-on-malformed-input
  gaps live.** S2 (a TYPE-2 pair beat built from zero-padded extras could leak on truncated
  DEFLATE) was invisible to 17 tests + coverage + formal because every DEFLATE stream fed was
  well-formed (zlib round-trip). Gating the top's pair-push with the aligner's sticky underrun
  closes it. Sign-off review must hand-trace the malformed-input paths that constrained-random
  over VALID inputs never reaches.
- Formal harnesses are cheap insurance at sign-off: ctrl_arcs (FSM termination) + skid (no
  loss/dup, PRD-F6) took ~1 h to write and proved the two properties the testplan listed in
  seconds (BMC+cover). The third (aligner 128-bit cap) took the documented unit-TB fallback —
  fine, but worth attempting the sby first.
