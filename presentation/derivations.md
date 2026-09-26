# Derivations behind the projection slide (S12) and the process counts (S24, B10)

Every line here is arithmetic on numbers that live in a shipped file; the inputs are cited
`file:line`, the results are what the slides quote. Nothing below is a measurement. Recompute
with the one-liners shown; the schedule-model blocks are the verbatim output of the scripts
named, run on 2026-09-26.

Shared inputs:

- grape cycles per invocation: 2,480,000 (124 cycles/step × 20,000 steps) — `hw/docs/hardware_report.md:168`
- achievable clock: 19.46 MHz (post-CTS STA, extrapolated from a 150 ns run) — `hw/docs/hardware_report.md:122-124`
- target clock: 50 MHz — `hw/docs/hardware_report.md:121`
- original Python: 231.20 ms; optimized Python: 143.13 ms; native Rust: 9.53 ms (9.530 ± 0.050 ms) — `hw/docs/hardware_report.md:180-182`, `report_nbody.txt:189`
- accelerated fraction f = 0.95, residual (1 − f)·T = 11.56 ms — `hw/docs/hardware_report.md:167`, `hw/grape_pipeline/docs/integration.md:84-85`

## 1. Clock at which grape compute alone matches Rust

Formula: f_match = cycles / T_rust = 2,480,000 / 9.530 ms.

- Result: 260.2 MHz, i.e. about 260 MHz (compute only, no residual, no interface time).
- The report states the same figure: "matching Rust needs ≈ 260 MHz" — `hw/docs/hardware_report.md:188`.
- With the 11.56 ms Python residual added there is no clock at which the Python-hosted system matches Rust, because 11.56 ms > 9.53 ms — `hw/docs/hardware_report.md:188`.
- That is 13.4× the 19.46 MHz post-CTS clock (260.2 / 19.46 = 13.37).

## 2. grape at the 50 MHz design target

Formula: t_hw = 2,480,000 / 50 MHz; T_new = 0.05 × 231.20 + t_hw; S = 231.20 / T_new.

- t_hw = 49.6 ms compute — `hw/grape_pipeline/docs/integration.md:84`.
- T_new = 11.56 + 49.6 = 61.16 ms → S = 3.78× vs the original — `hw/grape_pipeline/docs/integration.md:84`.
- vs Rust: 61.16 / 9.530 = 6.42× slower (compute only: 49.6 / 9.530 = 5.20× slower). The report rounds this to "≈ 6× at target" — `hw/docs/hardware_report.md:187`.
- vs optimized Python: 143.13 / 61.16 = 2.34× faster.

## 3. A wider unit mix at N = 5, from the schedule model

`python3 hw/grape_pipeline/docs/schedule_model.py` prints (verbatim):

```
nominal: add 3, mul 3, sqrt 30 (II=2), rcp 22 (II=2); commit+fsm 6
  2 add, 2 mul: 133 cycles/step  (fail)  benchmark 2.66 M cycles
  2 add, 3 mul: 125 cycles/step  (PASS)  benchmark 2.50 M cycles
  2 add, 4 mul: 122 cycles/step  (PASS)  benchmark 2.44 M cycles
  3 add, 2 mul: 133 cycles/step  (fail)  benchmark 2.66 M cycles
  3 add, 3 mul: 123 cycles/step  (PASS)  benchmark 2.46 M cycles
  3 add, 4 mul: 117 cycles/step  (PASS)  benchmark 2.34 M cycles
worst corner: add 3, mul 3, sqrt 32 (II=2), rcp 24 (II=2); commit+fsm 6
  2 add, 2 mul: 137 cycles/step  (fail)  benchmark 2.74 M cycles
  2 add, 3 mul: 129 cycles/step  (fail)  benchmark 2.58 M cycles
  2 add, 4 mul: 126 cycles/step  (PASS)  benchmark 2.52 M cycles
  3 add, 2 mul: 137 cycles/step  (fail)  benchmark 2.74 M cycles
  3 add, 3 mul: 127 cycles/step  (PASS)  benchmark 2.54 M cycles
  3 add, 4 mul: 121 cycles/step  (PASS)  benchmark 2.42 M cycles
```

Formula for the 3 add + 4 mul point: cycles = 117 × 20,000 = 2,340,000.

- At 19.46 MHz: 2,340,000 / 19.46 MHz = 120.2 ms compute (vs 127.4 ms as built): a 5.6 % gain.
- At 50 MHz: 46.8 ms compute.
- Clock at which 3 + 4 compute matches Rust: 2,340,000 / 9.530 ms = 245.5 MHz, about 245 MHz; at 19.46 MHz it is 120.2 / 9.530 = 12.6× slower than Rust.
- Conclusion: at N = 5 the step is latency-bound (one pair's chain is about 80 cycles, `hw/docs/hardware_report.md:193`), so a fourth multiplier buys 6 cycles/step and does not change the verdict; the 1-wide → 3-wide data (`hw/docs/hardware_report.md:216-217`) says wider issue costs area and clock.

## 4. Rust host + hardware versus Python host + hardware

Assumption (ours, not the report's): the non-accelerated 5 % share is host work (pyperf harness, two `report_energy` calls), so a Rust host would keep the same 5 % share of its own 9.530 ms run, i.e. 0.05 × 9.530 = 0.48 ms, instead of the Python host's 0.05 × 231.20 = 11.56 ms. The report's own sensitivity for the Python host is 1–5 % of the original, 2.3–11.56 ms, giving 1.66–1.78× at 19.46 MHz — `hw/grape_pipeline/docs/integration.md:92-94`.

Formula: T_new = residual + t_hw.

- Python host + grape @ 19.46 MHz: 11.56 + 127.4 = 139.0 ms; 14.6× slower than Rust (139.0 / 9.530); the report rounds to "≈ 15×" — `hw/docs/hardware_report.md:186`.
- Rust host + grape @ 19.46 MHz: 0.48 + 127.4 = 127.9 ms; 13.4× slower than Rust (127.9 / 9.530).
- Rust host + grape @ 50 MHz: 0.48 + 49.6 = 50.1 ms; 5.25× slower than Rust.
- Rust host + grape @ 260 MHz: 0.48 + 9.53 = 10.0 ms; 1.05× slower than Rust, i.e. parity only once the clock reaches the item-1 figure.
- Conclusion: changing the host from Python to Rust removes 11.1 ms (11.56 − 0.48), an 8 % change at 19.46 MHz; the compute term dominates until the clock is above roughly 200 MHz. The host language is not what loses to Rust; the clock is.

## 5. Larger N, from the N-parameterised schedule model

`python3 hw/grape_pipeline/docs/schedule_model_n.py` prints (verbatim):

```
check N=5 (3 add,3 mul): (123, 290)
    N   pairs      ops  cyc/step cyc/pair us/pair@19.46 vs Rust 0.045us
    5      10      290       123    12.30         0.632           14.0x
   10      45     1230       272     6.04         0.311            6.9x
   20     190     5060       902     4.75         0.244            5.4x
   50    1225    32150      5393     4.40         0.226            5.0x
  100    4950   129300     21584     4.36         0.224            5.0x
wider inventories at N=100 (add,mul,sqrt,rcp, II=1 for sqrt/rcp):
    6 add  6 mul 1 sqrt 1 rcp:   10810 cyc/step   2.18 cyc/pair   0.112 us/pair @19.46   0.044 @50
   12 add 12 mul 1 sqrt 1 rcp:    5426 cyc/step   1.10 cyc/pair   0.056 us/pair @19.46   0.022 @50
   12 add 12 mul 2 sqrt 2 rcp:    5445 cyc/step   1.10 cyc/pair   0.057 us/pair @19.46   0.022 @50
   24 add 24 mul 2 sqrt 2 rcp:    2754 cyc/step   0.56 cyc/pair   0.029 us/pair @19.46   0.011 @50
```

Formula: µs/pair = cycles/pair ÷ f_clk; ratio vs native = µs/pair ÷ 0.045 µs/pair (`results/bigN_sweep.txt` via `hw/docs/hardware_report.md:195`).

- As built (3 add + 3 mul) at N = 100: 4.36 cycles/pair = 0.224 µs/pair at 19.46 MHz, 5.0× slower than native — `hw/docs/hardware_report.md:194-195`.
- 12 add + 12 mul at N = 100: 1.10 cycles/pair, 1.25× slower than native at 19.46 MHz — `hw/docs/hardware_report.md:196`.
- 24 add + 24 mul + 2 sqrt + 2 rcp at N = 100: 0.56 cycles/pair = 0.029 µs/pair, 1.6× faster than native at 19.46 MHz — `hw/docs/hardware_report.md:197`; the crossover point.
- Caveats carried from the report: assumes the clock survives 8× wider issue selection (the 1-wide → 3-wide data says it degrades), SRAM body state, and that direct summation stays the software competitor (Barnes-Hut wins above N ≈ 300) — `hw/docs/hardware_report.md:197-199`.

## 6. Process counts quoted on S24 and B10

- Gate criteria: `python3 -c "import json; d=json.load(open('hw/STATUS.json')); print(sum(len(s.get('gate',{})) for m in d['modules'].values() for s in m['stages'].values()))"` → 136 gate criteria (3 modules × 10 stages, 30 gates).
- Human checkpoints: PRD, MAS, uArch, DV sign-off — 4 human checkpoints per module, `hw/FLOW.md:23`.
- Review findings: `cat hw/*/docs/review_*.md | grep -c '^|.*| *\(must\|should\|nit\) *|'` → 354 table rows, of which `grep -c '^|.*| *must *|'` → 126 must. Quoted as "about 350 review findings, 126 must". The 15 gate-evidence strings in `hw/STATUS.json` that record a count sum to 277 (they omit the RTL reviews of huffman/mtf and the sign-off reviews); `presentation/STRATEGY.md:47` says "~390", which neither count reproduces — the table-row count is the one used on the slides.
- Prompt log entries: `grep -c '^20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]' prompt.txt` → 220 dated entries (14 hand-written headings, 205 auto-logged session stamps, 1 other), `grep -c '^Prompt:' prompt.txt` → 241 prompt lines; `wc -l prompt.txt` → 1,598 lines.
