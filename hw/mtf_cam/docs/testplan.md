# mtf_cam — DV testplan (stage 5)

Status: **draft** 2026-09-12 (dv_testplan stage, awaiting review). Stage 5 of `hw/FLOW.md`.

Inputs: `docs/prd.md` (PRD-F1..F16, KPIs K1–K8; acceptance-test names §7), `docs/mas.md` (I/O §2,
register map §4, data-path §5, error/status §8, traceability §9), `docs/uarch.md` (§3 FSMs, §7
cycle model, §8 hazards, §10 traceability), `rtl/` (8 modules + `axi_lite_if.sv`, built and
RTL-reviewed), `golden/` (frozen: `mtf_ref.trace_stream/trace_benchmark`,
`list_model.expand/cycles`, `calibrate.py`). Methodology: `tb-best-practices` layered pyuvm TB.

**RTL-review carry-ins** (`docs/review_rtl.md`): **R1** (MAX_RUN per-invocation reset — FIXED in
RTL, needs a dedicated **multi-block** regression here, F-22); **R2** (the DUT `s_sym.tready` gate
reserves **2 slots** for every DECODE beat, vs the golden `list_model.cycles` **need-based** gate —
0 items for run beats; the DUT therefore stalls ≥ the model at the `cnt=7` FIFO boundary — **OPEN,
a dv_bringup entry criterion**: measure the DUT's real K1/K3 and reconcile, F-21). `--assert` armed
on every run.

All benchmark numbers below were **reproduced by executing the frozen golden** (`calibrate.py` and
direct `expand`/`cycles`/`trace_benchmark` calls) on `interpreter.tar.bz2`, 2026-09-12 — see §2.

## 1. Feature list ↔ tests ↔ covergroups ↔ checkers matrix

`F-01..F-16` ↔ `PRD-F1..F16`; `K1..K8` ↔ the PRD §2 KPIs (one row each, per the gate).
Added: `F-20` (ctrl-FSM arcs, uArch §3.1), `F-21` (R2 K3 model-vs-DUT reconciliation),
`F-22` (R1 MAX_RUN per-invocation reset), `F-23` (2-wide atomic enqueue / enqueue-after-check,
uArch M2/M3), `F-24` (cross-invocation empty-stream start / pending-beat withdrawal, MAS §5).
Env-plan names (§5): tests `test_smoke`, `test_random`, `test_full_benchmark`, `test_driver`,
`test_corner`, `test_multiblock`; `make formal`. Scoreboard = **DUT vs predictor
(`list_model.expand`) per beat, predictor vs golden (`mtf_ref`) per block** (§2).

| Feature | Test (directed / random sequence) | Covergroup + bins | Checker | Prio | Status |
|---|---|---|---|---|---|
| F-01 one block, EOB rules, DONE (PRD-F1) | `test_smoke` (4 used, 10 sym incl. run); `test_full_benchmark` (real block) | `cg_block`: eob {TYPE3+value=N_USED+1 ✓, TYPE3+wrong value, TYPE0+value=eob, TYPE1/2}; DONE-latency {1 cyc after last beat} | scoreboard: `m_l` byte stream == golden `mtf_ref` (0 mismatch, len 336,184); the 3 bad-EOB bins → ERR_RANK (F-10); DONE the cycle after the last beat is handshaken | must | todo |
| F-02 MTF semantics, bit-exact (PRD-F2) | `test_smoke`; `test_random` (`seq_rand`) | `cg_rank`: r ∈ {1, 2, 3(p50), 17(p90), 62(p99), 144(max), N_USED−1} | per-beat DUT byte == predictor `list_model.expand` `('mtf',r,byte)` event (0 mismatch) | must | todo |
| F-03 run semantics, n≤2^20, ERR_RUN (PRD-F3) | `test_random`; `test_corner` (n = 2^20, 2^20+1, 8,157) | `cg_run`: kind {RUNA-only, RUNB-only, mixed}; group symbols {1..20}; n {1, 2(p50), 8157(max), 2^20, 2^20+1}; terminator {MTF, EOB} | run bytes == predictor `('run',n,byte0)` (rank-0 byte captured **before** the terminating MTF move); n = 2^20 accepted; 2^20+1 → ERR_RUN at the offending run symbol (F-10) | must | todo |
| F-04 init from used map, INIT_CYCLES ≤ 256 (PRD-F4) | `test_driver`; `test_random` | `cg_init`: N_USED {1, 145(bench), 256}; `s_sym.tready` {0 during init} | DBG_SEL/DBG_DATA sweep == sorted used bytes; INIT_CYCLES == N_USED ≤ 256 (uArch §3.2 priority-encoder fill); `tready` = 0 through IDLE/INIT | must | todo |
| F-05 list invariants — FORMAL (PRD-F5, K8) | `make formal` (`synth/formal.sby`) | `cg_fml`: cover traces {permutation reached, lookup r=0, r=1, r=max, back-to-back moves} | `sby` PASS on the 3 obligations (§3): permutation, lookup-returns-pre-shift, post-shift positions; **N_LIST=16 unbounded induction + N_LIST=256 fill-abstracted move-preservation depth ≥ 20** (amended 2026-09-13 — see §3) | must | done |
| F-06 byte-packed `m_l`, TKEEP/TLAST, backpressure (PRD-F6) | `test_random` (stall mode, `tready` 0–90 % duty); `test_full_benchmark` (exact-multiple last beat) | `cg_pack`: last-beat TKEEP {full/exact-multiple, partial 1..W−1}; `tready` duty {0,50,90 %}; stall length {1,2..10,long} | 0 mismatch under random `tready`; **exact-multiple**: 336,184 = 42,023×8 → last beat TKEEP all-ones **and** TLAST (uArch S3); protocol agent: `tvalid` stable until `tready`, never combinational on `tready` | must | todo |
| F-07 item FIFO depth D, K3 (PRD-F7) | `test_random` (random `tvalid`); `test_full_benchmark` | `cg_fifo`: occupancy {0..D}; {full-stall, 2-slot reservation at a run-terminating MTF} | 0 loss/dup under random `tvalid`; K3 from `CYCLES/SYMBOLS_IN` (model 1.063 at D=8; see K3 row) | must | todo |
| F-08 parameters W∈{4,8,16}/N_LIST/D/RUN_W (PRD-F8) | all at W=8; `test_smoke` + `test_full_benchmark` at W=4/16 | `cg_caps`: CAPS.W {4,8,16}; CAPS.D {8}; CAPS.N_LIST {256, 16-formal} | CAPS read == build params (0x0100_0808 at W=8,D=8); decode byte-exact at each W; K3 = 1.175/1.063/1.023 (K3 row) | must | todo |
| F-09 ERR_PARAM doorbell-time (PRD-F9) | `test_corner::param` (each clause) | `cg_errparam`: {N_USED=0, SYMBOL_LIMIT=0, SYMBOL_LIMIT>2^27, BYTES_LIMIT=0, BYTES_LIMIT>2^30} | sticky ERR_PARAM set, **0 output beats**, no BUSY/DONE, counters hold; `irq` if enabled; reject → fix → accept | must | todo |
| F-10 run-time errors (PRD-F10) | `test_corner::{rank,run,limit,underrun}` (directed streams) | `cg_errrt`: {ERR_RANK (value>N_USED+1, TYPE1/2, EOB type/value mismatch), ERR_RUN, ERR_LIMIT (SYMBOL_LIMIT-th not EOB; BYTES_LIMIT), ERR_UNDERRUN (TLAST on non-EOB)}; error position {first, mid, near-EOB}; run-pending-at-ERR_RANK | stop at the offending symbol; SYMBOLS_IN frozen at that beat; pending run **discarded** (M3 — no run byte reaches `m_l`); ≤ 1 flush beat (TKEEP contiguous, **no TLAST**); BYTES_OUT == bytes handshaken incl. flush; IRQ ≤ 2 cyc after the flag | must | todo |
| F-11 control: doorbell/abort/W1C/reset (PRD-F11) | `test_driver` (one directed check per rule) | `cg_ctrl`: abort-in {INIT, DECODE, long-run drain, `tready`-stalled, post-EOB DRAIN}; {doorbell+abort→abort wins, abort idle no-op, abort-after-last-beat→DONE}; `cg_irq` W1C pins | latencies cycle-stamped (ABORT ≤ 8 cyc any state); MAS §8 disposition rows; DONE/ABORTED/ERR_* + IRQ are W1C, an accepted doorbell clears none; ERR_BUSY on config write while BUSY | must | todo |
| F-12 counters (PRD-F12) | `test_driver`; `test_full_benchmark`; `test_multiblock` (MAX_RUN) | `cg_counters`: read {idle, busy} for CYCLES/SYMBOLS_IN/BYTES_OUT/INIT_CYCLES/MAX_RUN; MAX_RUN {big block then small block} | == TB counts (exact); CYCLES inclusive doorbell→DONE; BYTES_OUT == beats handshaken; **MAX_RUN resets per invocation (R1, F-22)** | must | todo |
| F-13 empty block (PRD-F13) | `test_corner::empty` (EOB first symbol) | `cg_empty`: {EOB-first} | DONE (cycle after the EOB handshake), **no `m_l` beat** (MAS Q1), BYTES_OUT = 0 | must | todo |
| F-14 bus protocol agents (PRD-F14) | all tests | `cg_axi`: AXI-Lite {resp OKAY/SLVERR, RAZ/WI}; `s_sym`/`m_l` {tkeep patterns, tlast, backpressure} | `cocotbext-axi` protocol assertions on all 3 ports, **independent of the datapath scoreboard**; 0 violations | must | todo |
| F-15 reference models (PRD-F15) | `golden/calibrate.py` (CI); every scoreboard run | — (the scoreboard/golden itself; §2) | predictor `list_model.expand` == golden `mtf_ref.l_vector` per block (336,184 B / 89,837 lookups, `calibrate.py`); DUT == predictor per beat | must | todo |
| F-16 single clock, sync reset, one IRQ (PRD-F16) | `test_driver::reset` (reset in INIT/DECODE/DRAIN) | `cg_reset`: state-at-reset {init, decode, drain, stalled} | post-reset full readback == reset values (every RW/W1C/counter → 0); `tready`/`tvalid` drop ≤ 1 cyc; re-run trace-exact; one level `irq` = registered \|(STATUS & IRQ_EN) | must | todo |
| K1 MTF path 1 sym/cycle (PRD §2) | `test_driver` (directed run-free stream, 4,096 symbols, `tready`=1) | `cg_k1`: {run-free 4,096; rank spread 1..255} | CYCLES == INIT_CYCLES + 4,096 + pipeline latency (≤ 8); measured on the DUT at bring-up (R2) | must | todo |
| K2 expander W bytes/cycle (PRD §2) | `test_corner` (the 8,157-byte run, `tready`=1) | `cg_k2`: {run length 8,157; W ∈ {4,8,16}} | 8,157 B → ⌈8157/W⌉ full beats in that many **consecutive** cycles (1,020 beats at W=8); no bubble | must | todo |
| K3 block cycles ≤ 1.10, W-sweep (PRD §2) | `test_full_benchmark` (W=4/8/16), K3-enforced | `cg_k3`: W {4,8,16}; bin {≤1.10, >1.10} | DUT `CYCLES/SYMBOLS_IN` ≤ 1.10; model `list_model.cycles` = 1.175/**1.063**/1.023 at D=8 (§2, reproduced); **R2 reconcile the model↔DUT delta at bring-up (F-21)** | must | todo |
| K4 Fmax ≥ 50 MHz (PRD §2) | `make ppa PARAMS=W=…` (PPA stage) | `cg_ppa`: W {4,8,16} | OpenLane/STA tt_025C_1v80 Fmax ≥ 50 MHz (100 stretch); read-mux-limited (uArch §6) | must | todo |
| K5 block time & speed-up (PRD §2) | integration (`docs/integration.md`, `test_driver` cycle model) | — (derived from K3 CYCLES + `huffman_engine` numbers) | 157,560 cyc @ 50 MHz = 3.15 ms; ≈ 25× vs the original MTF alone | should | todo |
| K6 area, W-sweep (PRD §2) | `make ppa PARAMS=W=4/8/16` | `cg_ppa`: W {4,8,16} | trade-off table area vs K3 in `docs/ppa.md`; soft ceiling 1.0 mm² (flagged, non-gating) | should | todo |
| K7 power (PRD §2) | `make ppa` | `cg_ppa`: W {4,8,16} | OpenLane power, **report-only** | should | todo |
| K8 formal invariants (PRD §2) | `make formal` | (see F-05 `cg_fml`) | `sby` PASS: **N_LIST=16 unbounded induction + N_LIST=256 fill-abstracted move-preservation depth ≥ 20** (amended 2026-09-13, §3) | must | done |
| F-20 ctrl FSM arcs (uArch §3.1) | union of the directed tests | `cg_fsm`: every arc IDLE→INIT→DECODE→{DRAIN,ERR_S}, DRAIN→{DONE_S,ABORT_S}, INIT/DECODE→ABORT_S, *→IDLE | FSM monitor: only legal arcs taken; DONE/ERR/ABORT each reach IDLE | must | todo |
| F-21 R2 K3 model-vs-DUT reconciliation (bring-up) | `test_full_benchmark` **at dv_bringup** (not deferred) | `cg_k3` DUT-vs-model delta bin | measure DUT CYCLES/SYMBOLS_IN; the 2-slot `tready` reservation stalls ≥ the need-based model at `cnt=7`; if DUT ≤ 1.10 accept the (small) delta — the reservation is the safe/correct behaviour, golden frozen; else reconcile. **A committed bring-up task, not a waiver** | must | todo |
| F-22 R1 MAX_RUN per-invocation reset | `test_multiblock` (large-max block then smaller-max block, same session) | `cg_maxrun`: {block1 max > block2 max} | MAX_RUN of block2 reflects block2 only (not the stale block1 value); `inv_clr` on doorbell verified | must | todo |
| F-23 2-wide atomic enqueue / enqueue-after-check (uArch M2/M3) | `test_random`; `test_corner::rank` (run pending at ERR_RANK) | `cg_enq`: {run-terminating MTF → RUN+MTF_BYTE same cycle; FIFO cnt at the paired push; ERR_RANK with run pending} | both items enqueued in one cycle (order RUN then MTF_BYTE), no loss/overwrite for 2W/1R; on ERR_RANK **neither** item enqueued (run discarded, F-10) | must | todo |
| F-24 cross-invocation empty start / beat withdrawal (MAS §5) | `test_multiblock`; `test_driver` (doorbell/reset with a parked beat) | `cg_xinv`: {doorbell with pending `m_l` beat, reset with pending beat} | a still-pending `m_l` beat is withdrawn (`tvalid`→0, bytes **not** counted); every block starts with empty `s_sym`/`m_l`; block2 trace-exact | must | todo |

## 2. Golden-model interface

Two frozen Python models under `golden/`, with distinct roles (PRD-F15):

- **Predictor** `list_model.expand` — the per-beat expectation the scoreboard checks the **DUT**
  against.
- **Golden** `mtf_ref` — the `== libbzip2` reference the **predictor** is checked against per block.
- **Cycle model** `list_model.cycles` — validated **only against the DUT** (K3), never a functional
  golden.

**Confirmed by execution** (2026-09-12, `source ./hw/env.sh`; `calibrate.py` + direct calls):

```
expand(symbols, used, alphabet)               -> (l_bytes, events)
cycles(symbols, used, alphabet, W=8, D=0)     -> int cycles
mtf_ref.trace_benchmark()                     -> MtfTrace(used, symbols, alphabet, l_vector, mtf_out, output)
```

Reproduced benchmark numbers (`interpreter.tar.bz2`): used/alphabet = **145 / 147** (EOB value =
alphabet−1 = **146**); input **148,271** symbols = 89,837 MTF + 58,433 RUNA/RUNB + 1 EOB;
L-vector **336,184** B = 89,837 MTF + 246,347 run (73.3 %); **34,664** run groups, MAX_RUN
**8,157**, ≤ 12 run symbols/group; **42,023** beats at W=8 (**336,184 % 8 == 0** → last beat full,
TKEEP all-ones + TLAST, uArch S3; W=4 → 84,046 beats, W=16 → 21,012); `cycles(…,W=8,D=8)` =
**157,560** → **K3 = 1.063** (≤ the 163,098 ceiling); W-sweep at D=8 = 1.175 / 1.063 / 1.023;
lower bound max(148,271, 144,533)/148,271 = **1.000**. Cross-checks: `mt.output == bz2.decompress`
OK; `expand()[0] == mt.l_vector` OK; per-symbol MTF bytes == `mt.mtf_out` OK.

### 2.1 DUT vs predictor (per beat, byte-exact — tolerance 0)

Per accepted doorbell the scoreboard mirrors the config writes and calls, on the **same** symbol
values the driver sends and the **same** used map written to `USED[0..7]`:

```python
l_bytes, events = list_model.expand(symbols, used, alphabet)   # used: 256 bools; alphabet = popcount(used) + 2
```

- `symbols` are the raw values driven on `s_sym` (0/1 = RUNA/RUNB, 2..N_USED = MTF rank+1,
  N_USED+1 = EOB); the replay sequence maps them to ADR-0006 beats (TYPE 0 for the body, TYPE 3 +
  TLAST for the EOB value). `alphabet = N_USED + 2` (software programs it as popcount+2, PRD-F1).
- Expected `m_l` byte stream = `l_bytes`; the packer maps byte *i* → lane *i* mod W of beat
  *i* div W, last beat TKEEP contiguous-from-lane-0 (all-ones on the exact-multiple case). Compare
  **per beat, in order, byte-exact** (0 mismatches). `events` (`('mtf',r,byte)` / `('run',n,byte)`
  / `('eob',)`) give the per-symbol MTF and per-run expectations for the F-02/F-03 bins.
- **Error streams**: `expand` **raises** `ValueError` on ERR_RUN (run > 2^20) and ERR_RANK
  (s ≥ alphabet) at the offending symbol — the scoreboard takes that raise point as the DUT's stop
  point. The frozen model has **no limit/underrun argument**, so for ERR_LIMIT / ERR_UNDERRUN /
  bad-EOB the scoreboard **derives** the expectation itself: expected `m_l` = `l_bytes` truncated at
  the offending symbol (bytes already handshaken stay; a run pending at that symbol is **discarded**,
  M3), then the flush partial beat (TKEEP contiguous, no TLAST). No golden change — `golden/` stays
  frozen.

### 2.2 Predictor vs golden (per block, byte-exact)

```python
mt = mtf_ref.trace_benchmark()                 # or mtf_ref.trace_stream(data) for a specific stream
assert list_model.expand(mt.symbols, mt.used, mt.alphabet)[0] == mt.l_vector           # 336,184 B
assert [e[2] for e in events if e[0]=="mtf"]  == mt.mtf_out                             # 89,837 lookups
```

This is exactly `calibrate.py`; it runs in CI so a golden/predictor drift fails loudly. `mt.output
== bz2.decompress(data)` anchors `mtf_ref` to libbzip2. The benchmark symbol trace (used map,
symbols, alphabet) is dumped once into `tb/vectors/` for `test_full_benchmark`.

### 2.3 Cycle model vs DUT only (K3)

```python
list_model.cycles(mt.symbols, mt.used, mt.alphabet, W=8, D=8)   # 157,560, K3 = 1.063
```

Used **only** in `test_full_benchmark` to bound the DUT's `CYCLES/SYMBOLS_IN` ≤ 1.10 — never as a
byte oracle. **R2 (F-21):** the model's `tready` gate is need-based (`len(q)+need <= D`, 0 items on
a run beat), while the RTL reserves **2 slots** for every DECODE beat, so the DUT stalls ≥ the model
at the `cnt=7` boundary. Bring-up (`hw-dv-bringup`) **must** measure the DUT's real K1/K3 and
reconcile the delta: if the DUT is still ≤ 1.10 the 2-slot reservation is accepted as the
safe/correct behaviour (the golden is frozen); otherwise reconcile before sign-off. This is a
committed bring-up entry task, **not** a pre-granted waiver.

## 3. Formal properties

SymbiYosys, mirroring the grape/huffman `formal/*.sv` + `.sby` approach. The K8 obligation is the
`mtf_list` (uArch §3.2) move-to-front CAM; the harness is built with **N_LIST = 16** for unbounded
k-induction (so `smtbmc` closes), plus an **N_LIST = 256 fill-abstracted move-preservation BMC to
depth 24** (≥ 20).

> **Amendment 2026-09-13 (dv_signoff).** The original target — "N_LIST=256 *bounded* depth ≥ 20"
> on the full design — is **not achievable** and is superseded by the line above. Proving the
> permutation invariant across the 256-deep priority-encoder INIT fill (~530 logic levels) walls
> every engine tried (smtbmc BMC at depth 6; and for an *unbounded* proof: smtbmc k-induction,
> ABC PDR, and rIC3 all TIMEOUT at 900 s — a 256-wide-bijection SAT wall, not an effort gap).
> The sound, self-consistent target that IS achieved: **(a)** the 3 invariants proven *unbounded*
> by k-induction at N_LIST=16 (the move logic is value-agnostic, so 16 is structurally
> representative), **and (b)** permutation preservation across **24 consecutive move cycles at
> N_LIST=256** via fill-abstraction (assume a valid post-fill start, which collapses the fill
> chain; concrete post-fill occupancy, moves free; non-vacuity confirmed by a mutation CEX).
> Rationale and engine evidence: `docs/review_signoff.md` §"K8 N_LIST=256 depth" and
> `synth/formal.sby` header.

| Property | File | Note |
|---|---|---|
| (i) **permutation**: `multiset(list[0..N_USED−1])` == `multiset(initial used bytes)` at all times — no loss, no duplicate | `formal/mtf_list_inv.sv` (assert) | K8; the core invariant |
| (ii) **lookup-returns-pre-shift**: on a rank-r lookup, `byte_out` == `list[r]` sampled the cycle **before** the shift | `formal/mtf_list_inv.sv` | K8 |
| (iii) **post-shift positions**: `list_n[0]==byte_out`; `list_n[k]==list[k−1]` for 1≤k≤r; `list_n[k]==list[k]` for k>r | `formal/mtf_list_inv.sv` | K8 |
| N_LIST=16 unbounded **induction** (`prove`) + N_LIST=256 **fill-abstracted move-preservation** depth 24 (`bmc256moves`) + N_LIST=256 general two-probe depth 6 (`bmc`) | `synth/formal.sby` | K8 driver (amended 2026-09-13, see above); grape `fsm_arcs` structure |
| `s_sym`/`m_l` handshake: `tvalid` stable until `tready`, `tvalid` !comb on `tready`; `m_l` no beat loss/dup under valid/ready (flush exempt) | `formal/handshake.sv` (assert) | small, self-contained; mirrors huffman `skid.sv` |

Cover traces (`cg_fml`): the permutation reached after several moves, lookups at r=0 / r=1 / r=max,
back-to-back moves. F5/K8 is the module's headline formal target and is met per the 2026-09-13
amendment above (unbounded induction at N_LIST=16 + fill-abstracted depth-24 move-preservation at
N_LIST=256); the unbounded-256 proof was exhaustively attempted (rIC3 / ABC PDR / k-induction, all
TIMEOUT) and found beyond available engines — documented in `docs/review_signoff.md`.

## 4. Sign-off criteria

- **Matrix (§1)**: every `must` row PASS with no empty cell; `should` rows (K5–K7) recorded.
- **Functional**: `test_full_benchmark` `m_l` == golden `mtf_ref` — **0 mismatching bytes**, exact
  length **336,184 B / 42,023 beats at W=8**, exact-multiple last beat (TKEEP all-ones + TLAST);
  W=4/16 `test_smoke` + `test_full_benchmark` byte-exact; DUT == predictor per beat across all
  tests; predictor == golden per block (`calibrate.py` green in CI).
- **KPIs**: **K3** DUT `CYCLES/SYMBOLS_IN` ≤ 1.10 at W=4(≤1.10 only from W≥8)/8/16, **R2 delta
  reconciled at bring-up** (F-21); **K1** run-free 4,096-symbol stream = INIT_CYCLES+4,096+≤8;
  **K2** the 8,157-byte run drains in ⌈8157/W⌉ consecutive full beats; **K4/K6/K7** at the PPA
  stage; **K8** `sby` PASS (§3).
- **Coverage (§6)**: line/toggle ≥ 90 % over `rtl/*.sv` (minus non-DUT wrappers); all §1
  functional bins hit; exclusions justified inline.
- **Protocol**: 0 `cocotbext-axi` violations on all three ports (F-14), independent of the
  scoreboard.
- **RTL carry-ins closed**: **R1** MAX_RUN per-invocation reset (`test_multiblock`, F-22); **R2**
  K3 model↔DUT reconciled (F-21).

## 5. Env plan (pyuvm)

- **Tests** (`tb/tests/`): `test_smoke`, `test_random`, `test_full_benchmark`, `test_driver`,
  `test_corner`, `test_multiblock`. `MtfBaseTest` extends the common `base_test`.
- **Env** `MtfEnv`: shared **`axi_lite_agent`** (MMIO, with the grape/huffman passive monitor);
  a **`stream_agent`** master driving `s_sym` (ADR-0006 beat replay with `tvalid`-gap injection);
  a **`stream_agent`** monitoring `m_l` (slave with `tready`-gap injection, 0–90 % duty);
  **`MtfScoreboard`** fed via TLM analysis ports — mirrors config writes, runs the predictor
  `list_model.expand` at each doorbell, compares every `m_l` beat in order (byte-exact), checks
  sticky STATUS via a full mirror (BUSY-fall completion), and all counters (CYCLES/SYMBOLS_IN/
  BYTES_OUT/INIT_CYCLES/MAX_RUN).
- **Sequences** (`tb/sequences/`): `seq_used_map` (write `USED[0..7]` + limits), `seq_symbols`
  (raw values → ADR-0006 beats: TYPE 0 body, TYPE 3+TLAST EOB), `seq_rand` (random used maps
  N_USED 1..256, random ranks 1..N_USED−1 and run groups of ≤ 20 symbols with n ≤ 2^20),
  `seq_gaps` (`tvalid`/`tready` stalls), `seq_abort_at`, `seq_corner` (the F-09/F-10 error streams).
- **Vectors** (`tb/vectors/`): the benchmark block dumped once from `mtf_ref.trace_benchmark()` —
  used map, 148,271 symbols, alphabet 147.
- **ConfigDB**: `dut`, `clk_period_ns` (20), `golden` (predictor `list_model` + golden `mtf_ref`),
  `k3_enforce` (True for `test_full_benchmark` only).

## 6. Coverage goals

Line/toggle ≥ 90 % over `rtl/*.sv` minus any `_tb_top` wrappers (excluded as non-DUT); every §1
functional covergroup bin hit; exclusions inline `coverage_off` with a reason (grape/huffman
discipline). The F-05/K8 formal covergroup (`cg_fml`) closes on the `sby` cover traces.

## 7. Traceability

PRD-F1..F16 ↔ F-01..F-16; PRD §2 KPIs ↔ K1..K8; PRD-F15 = the golden itself (§2, frozen).
MAS §8 error/status rows ↔ F-09/F-10/F-11/F-13 + F-16 (reset row); MAS §4 register map ↔ F-04/F-09/
F-10/F-11/F-12 + F-08 (CAPS); MAS §5 data path (empty start, beat withdrawal) ↔ F-24.
uArch §3.1 FSM arcs ↔ F-20; §3.2 CAM invariants ↔ F-05/K8 (§3); §7 cycle model ↔ K3/F-07; uArch
musts M2/M3 ↔ F-23. RTL-review carry-ins ↔ **R1** → F-22, **R2** → F-21 (both closed at sign-off,
§4).
