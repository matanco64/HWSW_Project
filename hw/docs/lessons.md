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
