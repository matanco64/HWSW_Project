# Report deltas — hardware sections (for Matan)

Handoff from the hardware side (Yuval). This lists every place the report `.typ` sources
(`report/report_nbody.typ` §5, `report/report_pyflate.typ` §5) diverge from the reconciled
`hw/` docs, with **exact line numbers** and the correct value + source. I did **not** edit
your `.typ` files (SW/report ownership is yours); apply these at your discretion.

**Context you'll want first:** a three-way audit (reports ↔ `hw/` docs ↔ `STATUS.json`) found
your §5 prose is **accurate and honestly staged** — in particular the evidence-stage labeling
(huffman pre-placement 8.9 MHz vs grape/mtf post-CTS) is correct, which is the main thing a
grader will probe. Most of the contradictions were **doc-side and I have already fixed them**
(grape `integration.md`/`ppa.md` still said 11.15 MHz; a stray pyflate baseline said 1.13 s).
So your report mostly already agrees with the now-corrected docs. The items below are the
residue.

> **CORRECTION 2026-09-19 (Yuval/HW side) — if you read an earlier copy of this file:** huffman's
> post-CTS frequency is **39.9 MHz, not 25.1 MHz.** The 25.1 figure came from misreading the worst
> *hold* slack (+0.156 ns) as the worst *setup* slack (+14.941 ns); it was caught while copying
> the timing evidence into tracked folders. Knock-on: the chain's shared clock is now
> **mtf-limited at 37.6 MHz**, so the chain stage time is ≈ 4.2 ms (not 6.35), ≈ 1.3× slower than
> the Rust kernel (not 1.9×), ≈ 28× over the Python loop (not 19×), end to end ≈ 171 ms.
> Every item below already carries the corrected numbers. README.md is corrected too.

## Triage — 24 h to submission (read this first)

| Priority | Items | Why |
|---|---|---|
| **MUST** — wrong, or required by the brief | **C4** (+**R14**) huffman 8.9 → 39.9 MHz post-CTS · **R5** nbody power row is wrong · **R8** nbody bottom line · **R11** pyflate bottom line, compared against the wrong baseline · **R15** chain clocking + "simulated together" (the report's own caveat is now satisfied) · **R18** Conclusions must state the hardware impact (brief: "summarize the impact of… hardware acceleration") · **R1**, **R9** module names never explained · **R12** hardware workflow never explained | factual errors, open caveats now closed, or content the brief asks for |
| **SHOULD** — clarity / space | **R22** toolchain table → appendix A8 · **R10** why two modules · **R13** nbody cost table · **R16** define the formula + three deletion candidates · **R4** drop run tag/date · **R7** history vs final design · **R21** hardware evidence → own appendix section | makes §5 readable and frees page space |
| **NICE** — typography / polish | **R2** figure spacing (one line in `style.typ`) · **R3** colons on run-in labels · **R20** spell out "VM" · B1 grape cell count · B3 mtf formal wording | cheap, global, low risk |
| **No action** | A (already consistent) · D (keep caveats) · E (README done by Yuval) · **R17** math audit — all correct · **R19** appendix status · ~~B2~~ retracted · R6 → folded into R12 | information only |

Still to come from the HW side: final-netlist grape **area / cell count** (re-run in progress) —
it only changes two numbers in R13 and lets one hedge sentence in R7 be deleted.

---

## A. Nothing broken — already consistent (no action)

- **grape Fmax 19.46 MHz** (`report_nbody.typ:251, 259, 272, 277`): **correct.** Your report
  was *ahead* of grape's own `integration.md`, which I've now updated to match you (19.46 MHz
  post-CTS, `grape_prefix2`). No change needed.
- **pyflate stock baseline 1,123.49 ms** (`report_pyflate.typ:32, 325`): **correct** (pyperf
  mean). I aligned the huffman doc to it (it had wrongly used 1.13 s / the max line). No change.
- **nbody stock baseline 231.20 ms** (`report_nbody.typ:24, 277`): **correct** (mean). Docs now
  use the mean canonically; median is 229 ms (`baseline_nbody_stats.txt:17`). No change.

## B. Optional polish (low priority, your call)

1. **grape cell count omitted.** `report_nbody.typ` §5 gives grape's **area** (4.075 mm²,
   `:265`) but not its **cell count**, while `report_pyflate.typ` gives cells for both pyflate
   modules (`:302`). For symmetry you may add **584,454 cells** (source `hw/grape_pipeline/docs/ppa.md`;
   `STATUS.json` grape `ppa.cells`). Purely cosmetic consistency.

2. ~~mtf W=16 throughput-gain rounding~~ — **RETRACTED (my error).** `report_pyflate.typ:367`
   "about 3.9 %" is **correct**: throughput gain = 1.063 / 1.023 − 1 = **3.91 %**. The "3.8 %" in
   `hw/mtf_cam/docs/ppa.md` was the *cycle reduction* ((1.063 − 1.023) / 1.063 = 3.76 %)
   mislabeled as a throughput gain — fixed on the HW side. No report change.

3. **mtf formal understated (conservative).** `report_pyflate.typ:316-317` says the MTF
   invariant proofs are "bounded to depth 24 rather than exhaustive." True but incomplete: **3
   list invariants are proven *unbounded* by k-induction @ N_LIST=16** (strictly stronger), and
   the depth-24 bound is specifically the permutation proof @ N_LIST=256 (`STATUS.json` mtf
   `dv.formal`; `hw/mtf_cam/docs/review_signoff.md`). If you want to claim more, you can — the
   current wording only undersells.

## C. huffman Fmax / power — RESOLVED, report update recommended

4. **huffman is now post-CTS, not pre-placement — the report currently *understates* it.**
   The relaxed-clock re-run succeeded: a 40 ns OpenLane run (`signoff_confirm`) converged
   through CTS to **post-CTS STA** with **0 setup violations**, giving huffman a real post-CTS
   Fmax. The pre-placement 8.9 MHz turned out to be a **high-fanout-net wireload artifact**
   (one register Q fanning out to thousands of pins, unbuffered pre-CTS — the same class as
   grape's pre-PnR fanout net); once CTS buffers it, the real timing is **faster**. Source:
   `hw/huffman_engine/docs/ppa.md §3` (now rewritten), `STATUS.json` huffman `ppa.fmax_mhz` = 39.9.

   Recommended `report_pyflate.typ` edits (your call — HW docs already carry all of this):
   | line | currently | change to |
   |---|---|---|
   | `:303` | huffman "Timing-derived frequency ≈ 8.9 MHz" | **≈ 39.9 MHz** |
   | `:304` | huffman "Power estimate — not reported" | **≈ 283 mW** (post-CTS, default activity, 40 ns — indicative) |
   | `:310-311` | "Huffman's 8.9 MHz comes from pre-placement static timing; MTF's 37.6 MHz comes from post-CTS timing … different stages … not directly comparable" | **all three are now post-CTS STA** — grape 19.46 / huffman 39.9 / mtf 37.6 MHz. You can drop the "different stages / not directly comparable" caveat (keep "none completed 50 MHz sign-off / no GDS"). |
   | `:312` | "Neither completed 50 MHz sign-off" | still true — keep |

   - **Speedup unchanged.** huffman is clock-insensitive (Amdahl-fraction-bound): at 39.9 MHz
     S ≈ **1.97×** vs 1.93× at 8.9 MHz — the ~1.97× headline (`:323-325`) is unaffected. No
     change needed to the speedup prose.
   - **Power comparison caveat:** if you add huffman's 283 mW, note it is at a **different
     clock** (40 ns) than mtf's 13.7 mW (20 ns) and uses default activity — not comparable
     to each other, not workload power. `hw/docs/hardware_report.md §4` states this.
   - **Method note (defense):** post-CTS STA at a 40 ns constraint: worst **setup** slack
     +14.941 ns → 25.06 ns → 39.9 MHz; hold met (+0.156 ns). A looser 120 ns run gives 31.7 MHz,
     so the estimate is bracketed 31.7–39.9 MHz and rises as the constraint tightens (the
     timing-driven resizer works harder); a 27 ns confirmation run is in progress. Critical path:
     `huff_regs → huff_aligner` control path, not the decode cascade. Evidence files are now
     tracked: `hw/huffman_engine/synth/evidence/`.

## D. Evidence-stage caveats — keep them

Do **not** remove the honest hedges; they are what makes §5 defensible:
- "not demonstrated silicon operating frequencies" / "neither completed 50 MHz sign-off"
  (`report_pyflate.typ:311-313`) — keep.
- grape "preliminary timing estimate rather than measured silicon" (`report_nbody.typ:256-260`)
  — keep.
- mtf power "tool estimate using default switching activity … not measured workload power"
  (`report_pyflate.typ:314-315`) — keep.
- "conditional projections … not measurements of the implemented hardware attached to Python"
  (`report_pyflate.typ:323-327`) — keep.

These match the `hw/` docs exactly and are the correct posture: no module reached GDS.

## R. Reading-pass findings (Phase B, joint read of the built PDFs)

Items found while reading the reports as a grader. Numbered R1, R2, … as they come up.

R1. **`grape_pipeline` is never introduced** (`report_nbody.typ:208`). §5 opens with
    "`grape_pipeline` retains state on the device…" — a reader has no idea what the name means
    or why the design looks the way it does. Suggested replacement for that first sentence:

    > `grape_pipeline` is our accelerator for the `advance()` kernel. The name follows *GRAPE*
    > ("GRAvity PipE"), the University of Tokyo family of special-purpose N-body machines
    > (1990–2003), which hard-wire the pairwise-force formula as a pipeline and leave the rest to
    > a host. Ours differs in two ways that the benchmark forces: it computes in full IEEE-754
    > FP64 in the benchmark's own operation order (GRAPE's reduced-precision pairs diverge from
    > the Python energy trace), and it retains state on the device and executes a complete
    > `advance(dt, n)` request rather than returning forces to a host integrator.

    Sources: `research/hw-algorithms-nbody.md §1` (GRAPE lineage table),
    `hw/docs/adr/0002-grape-fp64-datapath-and-tolerance-oracle.md` (why FP64).
    The same applies lightly to `report_pyflate.typ` §5: `huffman_engine` / `mtf_cam` are
    self-describing names, so no change needed there.

R2. **Figure captions sit too close to the following paragraph** (first seen at nbody Fig. 4 →
    "Datapath", `report_nbody.typ:212-216`, but it is global). Cause: `style.typ:24` sets
    `par(spacing: 0.65em)` and `style.typ:33` sets only `figure(gap: 6pt)` (image↔caption), so a
    figure block gets paragraph spacing and its 9.5 pt caption reads as part of the next
    paragraph. One-line global fix, directly under `style.typ:33`:

    ```typst
    show figure: set block(above: 1.1em, below: 1.4em)
    ```

    Prototyped on a scratch copy: nbody stays **6 pages**, and the caption/paragraph gap is
    clearly separated. Fixes every figure in all three documents; no per-figure `#v()` needed.

R3. **Bold run-in labels should end with ":" not "."** A label names what follows, so a colon
    (or dash) is the right mark; a period makes it read as a stray one-word sentence.
    Change **labels only** — bold *full sentences* keep their period.

    | change `.` → `:` (labels) | keep `.` (full sentences) |
    |---|---|
    | nbody `:216` Datapath · `:221` Interface · `:276` End-to-end estimate | nbody `:120` "Correctness constrains the arithmetic." · `:174` "Native needs 26.7× fewer…" |
    | pyflate `:110` Ablation scope · `:310` Evidence levels | pyflate `:191` "RLE4 remains a separate final stage." · `:218` "The submitted Rust source was rebuilt on the VM." |
    | pyflate worked-example titles `:167` "A four-entry lookup, step by step" · `:177` "Counting-sort BWT construction" · `:184` "Reversed move-to-front" (and `:133` already contains a colon — drop its trailing period) | |
    | appendix `:74` Counter scope · `:102`,`:240` Interpretation · `:149` PMU configuration · `:189` Shape · `:208` Grouping | |

    Optional hardening so the style lives in one place: add to `style.typ`
    `#let runin(t) = [*#t:* ]` and write `#runin[Datapath] Three FP64 …`.

R4. **Internal run tag and date in the evidence table** (`report_nbody.typ:251`). The cell reads
    "≈ 19.46 MHz, typical corner, `grape_prefix2` (2026-09-14)". `grape_prefix2` is our OpenLane
    run tag — never explained, meaningless to a reader — and the date adds nothing. Suggested:

    > `[Post-CTS static timing], [≈ 19.46 MHz (typical corner); ≈ 127.4 ms computed execution time],`

    The run tag belongs only in the evidence footer / appendix A7. Same cleanup at `:270`
    ("new area measurement for `grape_prefix2`") — see R7.
    *Number re-verified from the raw report:* `ws.max.rpt` slack 98.6212 ns @ 150 ns →
    51.38 ns → **19.46 MHz** ✔.

R5. **"Physical completion / power" row is half wrong** (`report_nbody.typ:253`): "No completed
    routed sign-off or GDS" ✔ (verified — no run produced a `final/` or `.gds`), but "no workload
    power result" hides that a tool estimate **does** exist: post-CTS `report_power` =
    **≈ 19.2 mW** (default switching activity, at the 150 ns run constraint). Our own `ppa.md`
    wrongly said "not obtained" — **fixed on the HW side** (ppa.md, hardware_report.md,
    STATUS.json). For parity with how pyflate reports mtf's 13.7 mW, suggested cell:

    > `[Physical completion / power], [No routed sign-off or GDS. Tool power estimate ≈ 19 mW at the 150 ns run constraint with default switching activity — not workload power],`

R6. **"sky130" is name-dropping unless glossed** (`report_nbody.typ:269`; `report_pyflate.typ:300`
    table header "sky130, Yosys + OpenLane"). Gloss once at first use in each report, e.g.:

    > "…mapped to *sky130*, the open-source SkyWater 130 nm process whose standard-cell library
    > the open tools (Yosys for synthesis, OpenLane/OpenROAD for place-and-route) target."

    That single clause also explains Yosys and OpenLane, which are equally unexplained.

R7. **Report the final design, not its history — and these are the first cut candidates if
    page real-estate is short.** Policy agreed on the HW side: the report states what the design
    *is*; the path that got there lives in `hw/*/docs/ppa.md`.

    | cut / rewrite (`report_nbody.typ`) | why |
    |---|---|
    | `:270-272` "The subsequent prefix rewrite replaces a roughly 60-deep issue-selection scan… improving the post-CTS frequency estimate from 11.15 to 19.46 MHz." | pure history; final answer is 19.46 MHz |
    | `:272-273` "The critical path moved from the accumulate-adder selection to the integrate-multiplier operand path." | history; keep only "the critical path is the integrate-multiplier operand path" |
    | `:248` "after the prefix rewrite" | history qualifier on the 9/9 regression |
    | `:268-270` "These sky130 synthesis areas describe the recorded pre-prefix design points; they are not a new area measurement for `grape_prefix2`." | **a caveat, not history — it goes away only when the area is re-measured on the final netlist.** HW side is re-running `make area` on the current RTL now; I will send the final cell/area numbers so this sentence can simply be deleted and the table show the final design |

    Keep (this is design content, not history): the 1-wide vs 3-wide trade-off table — it is the
    §7 "performance/area trade-off" evidence — and the sentence "More parallelism can reduce
    cycles while adding selection, forwarding and wiring cost that limits the clock."

R8. **§5 has no bottom line — the reader cannot tell whether the hardware won.** The numbers are
    scattered through the hedged "End-to-end estimate" paragraph (`report_nbody.typ:276-284`) and
    never set beside the software tiers. Suggested: replace that paragraph's opening with one
    comparison table + a two-sentence verdict (this also lets several hedging sentences go):

    | Tier | Time / run | vs stock | Evidence |
    |---|---:|---:|---|
    | Stock Python | 231.20 ms | 1.00× | measured |
    | Optimized Python | 143.13 ms | 1.62× | measured |
    | Native Rust | 9.53 ms | 24.3× | measured |
    | Hardware @ 19.46 MHz (achievable) | ≈ 139 ms | ≈ 1.66× | projected: 2,480,000 RTL cycles ÷ post-CTS clock + 5 % Python residual |
    | Hardware @ 50 MHz (design target) | ≈ 61 ms | ≈ 3.8× | projected |

    > *Verdict.* At the achievable clock the accelerator is a projected ≈ 1.66× over stock — level
    > with the optimized Python tier (1.03×) and ≈ 15× slower than the native Rust tier (still ≈ 6×
    > slower at the 50 MHz target). One step costs 124 cycles = 6.4 µs at 19.46 MHz against
    > 0.48 µs natively: the benchmark's cost was interpreter overhead, so removing the interpreter
    > captures almost all of the gain, and at N = 5 with ordered pair dependencies there is little
    > parallelism for custom FP64 hardware to exploit. Matching Rust would need ≈ 260 MHz.

    Every figure is already in the report or `hw/grape_pipeline/docs/integration.md §3`; only the
    side-by-side presentation and the explicit verdict are new. Keep the word "projected" — no
    Python-attached hardware run exists.

R9. **`huffman_engine` and `mtf_cam` are never explained** (`report_pyflate.typ:270`). §5 opens
    with "`huffman_engine` followed by `mtf_cam` produces the same L-vector…". (I first judged the
    names self-describing; a first-time reader disagrees — and "CAM" is actively misleading, see
    note.) Suggested opening:

    > bzip2's symbol stage is two different jobs back to back. *Huffman decoding*: the compressed
    > input is a stream of variable-length codes, each matched against the block's code tables to
    > recover a symbol — `huffman_engine` does this, comparing the next bits against every code
    > length in parallel, one symbol per cycle. *Move-to-front and run expansion*: each symbol is
    > either a rank into a list of recently used bytes (output that byte, move it to the front) or
    > part of a run count to expand — `mtf_cam` does this with a 256-entry byte list held in a
    > parallel shift register, read by rank and re-ordered in one cycle. Chained on chip they
    > produce the same L-vector as the Rust kernel, over the same boundary.

    **Naming note (defense risk):** "CAM" = content-addressable memory, but the *decode* path reads
    the list **by rank** (`byte_out = list[r]`, `hw/mtf_cam/docs/uarch.md §3.2`) — there is no
    content search. The name follows the MTF list structure (the encoder direction searches by
    content). Describe it as above; don't lean on "CAM" in the prose (`report_pyflate.typ:295,369`
    "the CAM is 68% of its area" → "the move-to-front list is 68% of its area").

R10. **No motivation for having two modules** — add after the opening (sources ADR-0003, ADR-0004):

    > *Why two modules:* the two jobs want different hardware. Huffman decoding is table-driven and
    > its cost is storage (95 % of `huffman_engine` is code tables); move-to-front is a wide list
    > update whose risk is the output rate (73 % of the output bytes come from runs). Separate
    > modules are verified against separate golden models and sized by separate trade-offs (table
    > storage vs output width), and the Huffman block stays reusable (it also implements DEFLATE).
    > They are chained on chip so the 148 k intermediate symbols never cross to software; leaving
    > move-to-front in software would have kept about 11 % of stock runtime on the CPU.

R11. **No bottom line, and the comparison is made against the wrong baseline.** "Conditional
    benefit and integration cost" (`report_pyflate.typ:321-349`) projects 1.97× / 1.15× / ~2.7×
    against *stock* Python and then says such a projection "cannot demonstrate an improvement
    over that stronger baseline" and that the replaced region should be timed. **It already is:**
    Appendix A3 (`report_appendix.typ:132`) has the native decode phase = **3.304 ms**, the exact
    boundary the two modules replace. Suggested replacement core — two small tables + verdict:

    *The replaced stage only (148,271 symbols → 336,184 bytes):*
    | Implementation | Time | Evidence |
    |---|---:|---|
    | Optimized Python loop | ≈ 117 ms | derived: 283.88 − 170.01 + 3.30 (approximate — separate experiments) |
    | Rust kernel | 3.30 ms | measured, Appendix A3 |
    | Hardware chain @ 37.6 MHz (achievable, shared clock — mtf-limited) | ≈ 4.24 ms | **159,303 cycles measured in chain RTL simulation** ÷ post-CTS clock, before DMA |
    | Hardware chain @ 50 MHz (design target) | ≈ 3.2 ms | same measured cycles ÷ target clock |

    *End to end:*
    | Configuration | Time | vs stock |
    |---|---:|---:|
    | Stock Python | 1,123.49 ms | 1.00× |
    | Optimized Python | 281.16 ms | 4.00× |
    | Python + Rust kernel | 170.01 ms | 6.61× |
    | Python + hardware chain @ 37.6 MHz | ≈ 171 ms | ≈ 6.6× (projected, before DMA) |
    | Python + hardware chain @ 50 MHz | ≈ 170 ms | ≈ 6.6× (projected) |

    > *Verdict.* For the stage it replaces, the hardware chain is ≈ 28× faster than the optimized
    > Python loop and ≈ 1.3× slower than the Rust kernel at the achievable clock (parity at the
    > 50 MHz target). End to end it ties the delivered 170 ms path, because once this stage is off
    > the interpreter it is ≈ 2 % of what remains; inverse BWT (137.7 ms, ≈ 80 %) sets the floor for
    > both the native and the hardware route.

    Chain timing uses one shared clock (the slower module's 37.6 MHz — `mtf_cam`) and the **measured** chain
    cycle count (159,303, R15). The report's caveat "use a combined backpressure simulation rather
    than adding standalone cycles/symbol" (`:343-345`) is now satisfied and can be replaced by the
    R15 paragraph. What is still a projection is the *clock* (static timing, not silicon) and the
    DMA/interface time. Also add the **two-module comparison row set** to the cost table
    (`:299-308`): area 1.634 vs 0.187 mm² (8.7×), area driver (code tables 95 % vs list 68 %),
    chain limiter (huffman: clock; mtf: cycles/symbol). This supersedes the stock-based 1.97× /
    1.15× / 2.7× paragraphs (`:323-341`), which are then cut candidates under R7's policy.

R12. **The hardware workflow is never explained — "sky130, Yosys + OpenLane" reads as buzzwords**
    (`report_pyflate.typ:300` table header; `report_nbody.typ:256-258` explains only CTS; the
    appendix has nothing). The reader is never told how the cost-table numbers were produced or
    why to trust them. **Put it in the main reports, not the appendix**: `report_appendix` is an
    optional extra (the brief requires only `report_<benchmark>.txt`), so a grader may never open
    it and nothing needed to understand §5 may live only there. ~5 lines before the first
    hardware number in each report's §5 (the appendix "Hardware evidence map" can keep the longer
    file-by-file detail):

    > *How these numbers were produced.* Each accelerator is written in SystemVerilog and
    > simulated cycle by cycle (Verilator, cross-checked with Icarus) inside a Python testbench
    > that feeds it the real benchmark input and compares every output against a *golden model* —
    > a Python reference of the same stage; cycle counts, test results and coverage come from these
    > runs. The design is then *synthesized*: Yosys translates it into a netlist of standard logic
    > cells from *sky130*, the open-source SkyWater 130 nm process, which gives cell count and
    > area. Finally OpenLane *places* the cells, builds the clock tree and runs *static timing
    > analysis* — it sums gate and wire delays along every register-to-register path, and the
    > slowest path sets the maximum clock. We stop after clock-tree synthesis ("post-CTS"): cells
    > and the clock network are placed but signal wires are not routed, so the frequency is an
    > estimate, not silicon. The toolchain is entirely open-source, so every number can be
    > regenerated from the repository.

    Plus a three-row key tying each cost-table row to its stage:

    | Rows | Produced by |
    |---|---|
    | Cycles per symbol/step, tests, coverage | RTL simulation against the golden model |
    | Cells, area | Yosys synthesis onto sky130 cells |
    | Frequency, power estimate | OpenLane place + clock tree + static timing |

    This subsumes R6 (sky130 gloss). Optional: a one-row flow figure
    (RTL → simulate vs golden → synthesize → place + CTS → timing) via `make_figures.py`.

R13. **nbody lacks the "Measured cost" table that works so well in pyflate**
    (`report_pyflate.typ:299-308` vs nbody's prose-heavy "Evidence | Result and scope" table at
    `report_nbody.typ:244-254`). Suggest the same shape for nbody, one column:

    | sky130, Yosys + OpenLane | `grape_pipeline` |
    |---|---:|
    | Cells | 584,454 *(final-netlist re-measure in progress — will confirm)* |
    | Area | 4.075 mm² *(same)* |
    | Timing-derived frequency | ≈ 19.46 MHz (post-CTS) |
    | Power estimate | ≈ 19 mW (default activity, 150 ns run clock — indicative) |
    | Cycles per step | 124 |
    | Directed + random tests | 9 / 9 |
    | Line / toggle coverage | 91.7 % / 96.0 % |

    Sources: `hw/grape_pipeline/docs/ppa.md`, `hw/STATUS.json` (grape `dv_signoff` coverage row).
    The scope sentences now in that table's right-hand column move to the "Evidence levels"
    paragraph, as pyflate does.

R14. **Stale appendix sentence** (`report_appendix.typ:~303`): "`hw/huffman_engine/docs/ppa.md`
    records pre-placement timing" — no longer true; it now records **post-CTS** timing (39.9 MHz)
    and a default-activity power estimate, like mtf. Update with C4.

R15. **Clocking of the chain is left undecided in the report, but it is decided in the design**
    (`report_pyflate.typ:343-345`: "A shared clock would be constrained by both modules; separate
    clocks would require an explicit clock-domain crossing. In either case…"). The report must
    answer: same clock or CDC? how was the clock chosen? how was the link tested? how is the rate
    difference handled? Facts (sources: `hw/huffman_engine/docs/mas.md §3` "One clock domain… no
    CDC"; `hw/mtf_cam/docs/mas.md §2` "single clock"; ADR-0004; ADR-0006 beat format). Suggested
    replacement:

    > *Clocking and the link between the modules.* Both modules are single-clock synchronous
    > designs and the chain uses **one shared clock — there is no clock-domain crossing**. The
    > link is an AXI4-Stream valid/ready handshake carrying one symbol per beat. A shared clock
    > runs at the slower module's frequency: 37.6 MHz, set by `mtf_cam`; `huffman_engine`'s
    > 39.9 MHz estimate leaves it a little headroom. We preferred this to two clocks joined by an
    > asynchronous FIFO because the two rates are nearly equal (6 % apart) and the chain is not clock-limited end to end,
    > so a crossing would add area, latency and verification burden for no benefit. The modules
    > differ in *cycles per symbol*, not in clock: `mtf_cam` needs 1.0686 cycles per symbol
    > against the decoder's 1.0068, so it back-pressures the decoder through `tready` and the
    > chain advances at `mtf_cam`'s rate (≈ 158 k cycles per block).
    >
    > *How it was tested.* Each side of the link is verified against the same beat-format
    > contract and the same golden symbol stream: `huffman_engine`'s output is trace-exact over
    > all 148,271 beats; `mtf_cam` consumes that golden stream and its output is byte-exact over
    > 336,184 bytes; both testbenches inject back-pressure, and both handshakes are also checked
    > formally. The two modules were then **simulated together** under one top-level
    > (`pyflate_accel`, one shared clock, direct stream link) on the real benchmark block: the
    > output is byte-exact over all 336,184 bytes, with and without random back-pressure on the
    > output, in **159,303 cycles** — 0.5 % above the standalone projection, the difference being
    > the decoder's table-build start-up.

    **Gap CLOSED 2026-09-19 (HW side):** `hw/pyflate_accel/` now holds the wrapper + chain test
    (`make -C hw/pyflate_accel sim` → 2/2 PASS, 30 s). Measured: 159,303 cycles always-ready,
    189,448 with 50 % output back-pressure; 148,271 link beats, 0 malformed; in the chain the
    decoder is stalled by `mtf_cam` on 10,013 cycles and `mtf_cam` starves on only 873 — i.e. the
    chain runs at `mtf_cam`'s rate, as projected. In the paragraph above change "≈ 158 k cycles
    per block" to "159,303 cycles per block (measured)".

R16. **The estimate formula opens a paragraph as an imperative and its terms are never defined**
    (`report_pyflate.typ:323` "Use `Tnew = (1 - f)*Tstock + Thardware + Tinterface`."; same at
    `report_nbody.typ:276` "Use `Tnew = Tremaining + cycles / frequency + Tinterface`."). The two
    reports also use `f` for different things (fraction vs frequency). Suggested, one convention
    for both (`f` = fraction, `f_clk` = clock):

    > *How the end-to-end time is estimated:* offloading a stage removes its share of the software
    > time and adds the hardware's time plus the cost of moving data,
    > `T_new = (1 − f)·T_sw + T_hw + T_if`, where `T_sw` is the measured software run time, `f` the
    > fraction of it spent in the replaced stage, `T_hw` = RTL cycles ÷ `f_clk` (clock frequency),
    > and `T_if` the driver, DMA-setup and copy time, which is not measured here.

    nbody: same sentence; there `(1 − f)·T_sw` is the Python work that stays in software (energy
    evaluation, harness ≈ 5 %) and `T_if` is ≈ 150 AXI-Lite register transactions per run.

    **Deletion candidates in the same subsection** (all superseded by R11's matched comparison,
    and all "history" under R7's policy — the words "older"/"old" are the tell):
    | `report_pyflate.typ` | text | why it can go |
    |---|---|---|
    | `:324-327` | "The older integration model assumes f = 0.496… 1.97× at 50 MHz… 1.93× at 8.9 MHz…" | stock-based projection; 8.9 MHz is obsolete; R11 replaces it |
    | `:329-333` | MTF standalone ≈ 1.15×; "older isolated 80.4 ms microbenchmark… 19.1× / 25.4×" | two different experiments the text itself warns not to mix |
    | `:335-341` | "Adding the old Huffman assumption (49.6 %) to the newer MTF profile share… ≈ 2.7×… sensitivity example" | the paragraph argues against its own number |

    If R11 goes in and these three go out, the subsection gets shorter *and* gains a bottom line.

R17. **Math audit of "Conditional benefit and integration cost" and "Area and throughput
    trade-offs" — all 16 computed figures re-derived by script, all correct**
    (`report_pyflate.typ:321-370`): 2.99 / 16.77 ms, 566 ms residual, 1.97× / 1.93×, 1.0686 and
    1.0068 cycles/symbol, 4.21 ms, 1.15×, 19.1× / 25.4×, f ≈ 0.63 → 2.7×, +10.9 % area, 3.9 %
    throughput, 68 % list share. No arithmetic change needed. (If C4 is applied, the 8.9 MHz pair
    "16.77 ms → 1.93×" becomes "3.74 ms → 1.97×" at 39.9 MHz — though under R16 that whole
    sentence is a deletion candidate.)

R18. **The Conclusion says nothing concrete about the hardware** (`report_pyflate.typ:378-380`:
    "Both accelerators have RTL verification and synthesis evidence. Their end-to-end benefit
    remains conditional…" — no number, no verdict; nbody `:295-297` is equally vague). The brief
    asks the Conclusion to "summarize the impact of the optimizations **and hardware
    acceleration**". Suggested hardware paragraphs:

    *pyflate:*
    > In hardware, `huffman_engine` and `mtf_cam` implement the same symbol-decode boundary as the
    > Rust kernel. Simulated together on the real benchmark block they are byte-exact over all
    > 336,184 output bytes and need 159,303 clock cycles — ≈ 4.2 ms at the 37.6 MHz clock that
    > static timing supports: about 28× faster than the optimized Python loop and about 1.3× slower
    > than the Rust kernel (parity at the 50 MHz design target), for 1.8 mm² of 130 nm standard
    > cells. End to end this ties the delivered 170 ms path, because once the symbol stage leaves
    > the interpreter it is about 2 % of what remains; inverse BWT, still in software, sets the
    > floor for both routes. These are projections from RTL simulation and static timing, not a
    > run of Python attached to hardware.

    *nbody:*
    > In hardware, `grape_pipeline` executes the whole `advance()` kernel bit-exactly against its
    > arithmetic model in 124 cycles per step. At the 19.46 MHz clock that static timing supports
    > this projects to ≈ 139 ms per run: 1.66× over stock, level with the optimized Python, and
    > about 15× slower than the native Rust tier (≈ 6× at the 50 MHz target), for 4.1 mm². The
    > benchmark's cost was interpreter overhead rather than arithmetic, so removing the
    > interpreter captures nearly all of the gain; at five bodies with ordered pair dependencies
    > there is too little parallelism for custom FP64 hardware to repay its area.

R19. **Status of `report_appendix` (checked, no change required).** It is *not* a required
    deliverable — the brief asks for `report_<benchmark>.txt` per benchmark; the appendix falls
    under "additional files (optional but encouraged)". The main reports use it correctly: 12
    references, all provenance/method pointers (A2, A3, A5, A7) with the number itself stated in
    the main text; all six required sections live in the main reports; README:187 explains what
    it is. Rule going forward: **anything a grader needs in order to follow or believe a claim goes
    in the main report; the appendix only backs it up.** Hardware-relevant content in the
    appendix is just "Hardware evidence map" (`report_appendix.typ:299-308`), which needs R14
    (stale huffman sentence) and, once the grape area is re-measured, loses its "older
    synthesis-area table describes the earlier architecture" sentence too.

R20. **"VM" is never spelled out** — 20 bare uses across the three documents, 0 × "virtual
    machine" (first uses: `report_nbody.typ:34`, `report_pyflate.typ:42`, `report_appendix.typ:7`,
    all "Course QEMU/KVM VM"). Low severity (the staff supplied the VM), three-word fix at each
    first use: "the course's QEMU/KVM **virtual machine (VM)**". Same pass: the A7 title
    "VM verification of the delivered route" (`report_appendix.typ:270`) uses "delivered route",
    a phrase found nowhere else — suggest "A7. Verification of the final code path on the course VM".

R21. **"Hardware evidence map" is filed under the wrong heading** (`report_appendix.typ:299`, a
    sub-section of "A7. VM verification…"). Nothing in it relates to the VM: the hardware numbers
    come from RTL simulation and the synthesis/timing tools on the development host, never from
    the VM. Filed there, a reader looking for hardware evidence won't find it, and a reader of the
    VM section may infer the hardware was exercised on the VM. Suggest promoting it to its own
    section **"A8. Hardware evidence"** and opening it with one sentence that states the split:

    > Software times in this report are measured on the course VM (A7). Hardware figures are not:
    > cycle counts come from RTL simulation against golden models, area from synthesis, and clock
    > and power estimates from place-and-route static timing, all on the development host. The
    > hardware speedups divide the first kind of number by the second.

    That sentence is also the honest one-line answer to "what exactly did you measure?". The
    A7 table is the denominator of every hardware comparison (231.20 / 143.13 / 9.53 ms nbody;
    1,123.49 / 283.88 / 170.01 ms pyflate) together with A3's 3.30 ms native decode phase.
    A8 should also absorb R14 (huffman is now post-CTS) and mention the chain co-simulation
    (R15: byte-exact, 159,303 cycles, `make -C hw/pyflate_accel sim`).

R22. **No place states the hardware toolchain (what / for which step / why).** R12's paragraph
    names the tools in prose; the full table — tool, version, step, reason — is now
    `hw/docs/hardware_report.md §0.1` (14 rows: SystemVerilog, Verilator lint+sim, Icarus 4-state
    cross-check, cocotb/pyuvm/cocotbext-axi, pytest, SymbiYosys, Yosys + sky130 Liberty, the sky130
    PDK choice, OpenLane 2.3.10, the pinned OSS CAD Suite bundle, waveform tools, our own
    flow/diagram scripts, AI assistance). Suggest: copy it into the appendix's new "A8. Hardware
    evidence" (R21) — an appendix is the right home for a table like this — and keep only R12's
    paragraph in the main reports. Priority: SHOULD.

    *FYI — block diagrams regenerated (HW side, no report action):* the three
    `hw/*/docs/block_diagram.svg` had a generator bug (every edge label drawn twice, labels on top
    of block titles) and stale content (grape showed "6 FMA" — the design has **no FMA**, which
    your Fig. 4 already states correctly; huffman showed a "Symbol table RAM" — it is flops).
    Fixed in `tools/hw/blockdiag.py` and the JSON specs; your report figures
    (`grape_report.svg`, `decode_report.svg`) were already correct and are untouched.

## E. README.md hardware table — already updated by me (FYI, not a request)

Your `43a2bc3` refresh of `README.md` added a hardware table (README:31-42) written before the
huffman post-CTS run, so it had stale huffman timing. Because it is factual `hw/` data (not
`report/*.typ`), I updated it directly — flagging here so you know what changed and why:

| README line | was | now |
|---|---|---|
| `:34` (table) | huffman Fmax "~8.9 MHz" | **39.9 MHz** |
| `:37-42` (prose) | "`mtf_cam` and `grape_pipeline` reached post-CTS … `huffman_engine` has a pre-placement estimate and its placement did not converge" | "**All three now report post-CTS** static timing … huffman's ~8.9 MHz pre-placement was a high-fanout-net wireload artifact; relaxing the clock let placement converge through post-CTS (39.9 MHz, *faster*)" |

Unchanged and still correct: grape 19.5 MHz, mtf 37.6 MHz (README:33,35); "preliminary timing
estimates, not measured silicon" and "stopped before routed sign-off" (README:27-28); the grape
three-wide-area / prefix-netlist note (README:39-41). Same substance as report item **C4** above
— if you apply C4 to `report_pyflate.typ §5`, the README and the report will match.

## Note on the last sync (commits `4abb512`, `c2adbda`, `43a2bc3`)

Those three commits (MDP-benchmark removal, nbody stock-oracle rename, README/CHECKPOINT/promts)
**do not touch `report_*.typ`** and require **no change to the HW report content** — no HW doc
references MDP or the renamed `dev/nbody` files (verified). The only downstream effect was the
stale README table above.
