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

2. **mtf W=16 throughput-gain rounding.** `report_pyflate.typ:367` says "about **3.9 %**"; the
   PPA doc says **3.8 %** and the exact figure is (1.063−1.023)/1.063 = **3.76 %**
   (`hw/mtf_cam/docs/ppa.md:84`). Suggest changing 3.9 % → 3.8 % to match the doc.

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
   `hw/huffman_engine/docs/ppa.md §3` (now rewritten), `STATUS.json` huffman `ppa.fmax_mhz` = 25.1.

   Recommended `report_pyflate.typ` edits (your call — HW docs already carry all of this):
   | line | currently | change to |
   |---|---|---|
   | `:303` | huffman "Timing-derived frequency ≈ 8.9 MHz" | **≈ 25.1 MHz** |
   | `:304` | huffman "Power estimate — not reported" | **≈ 283 mW** (post-CTS, default activity, 40 ns — indicative) |
   | `:310-311` | "Huffman's 8.9 MHz comes from pre-placement static timing; MTF's 37.6 MHz comes from post-CTS timing … different stages … not directly comparable" | **all three are now post-CTS STA** — grape 19.46 / huffman 25.1 / mtf 37.6 MHz. You can drop the "different stages / not directly comparable" caveat (keep "none completed 50 MHz sign-off / no GDS"). |
   | `:312` | "Neither completed 50 MHz sign-off" | still true — keep |

   - **Speedup unchanged.** huffman is clock-insensitive (Amdahl-fraction-bound): at 25.1 MHz
     S ≈ **1.96×** vs 1.93× at 8.9 MHz — the ~1.97× headline (`:323-325`) is unaffected. No
     change needed to the speedup prose.
   - **Power comparison caveat:** if you add huffman's 283 mW, note it is at a **different
     clock** (40 ns) than mtf's 13.7 mW (20 ns) and uses default activity — not comparable
     to each other, not workload power. `hw/docs/hardware_report.md §4` states this.
   - **Method note (defense):** measuring at 40 ns (near-critical, +0.156 ns reg→reg slack) is
     *stronger* than a loose measurement — the tool actually optimized the critical path. The
     critical path is now `huff_regs → AXI readback`, not the decode cascade.

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

## E. README.md hardware table — already updated by me (FYI, not a request)

Your `43a2bc3` refresh of `README.md` added a hardware table (README:31-42) written before the
huffman post-CTS run, so it had stale huffman timing. Because it is factual `hw/` data (not
`report/*.typ`), I updated it directly — flagging here so you know what changed and why:

| README line | was | now |
|---|---|---|
| `:34` (table) | huffman Fmax "~8.9 MHz" | **25.1 MHz** |
| `:37-42` (prose) | "`mtf_cam` and `grape_pipeline` reached post-CTS … `huffman_engine` has a pre-placement estimate and its placement did not converge" | "**All three now report post-CTS** static timing … huffman's ~8.9 MHz pre-placement was a high-fanout-net wireload artifact; relaxing the clock let placement converge through post-CTS (25.1 MHz, *faster*)" |

Unchanged and still correct: grape 19.5 MHz, mtf 37.6 MHz (README:33,35); "preliminary timing
estimates, not measured silicon" and "stopped before routed sign-off" (README:27-28); the grape
three-wide-area / prefix-netlist note (README:39-41). Same substance as report item **C4** above
— if you apply C4 to `report_pyflate.typ §5`, the README and the report will match.

## Note on the last sync (commits `4abb512`, `c2adbda`, `43a2bc3`)

Those three commits (MDP-benchmark removal, nbody stock-oracle rename, README/CHECKPOINT/promts)
**do not touch `report_*.typ`** and require **no change to the HW report content** — no HW doc
references MDP or the renamed `dev/nbody` files (verified). The only downstream effect was the
stale README table above.
