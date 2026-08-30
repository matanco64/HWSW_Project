# grape_pipeline — MAS (Architecture Spec)

Status: **approved** 2026-08-30 (MAS checkpoint). Stage 2 of `hw/FLOW.md`.
Inputs: `docs/prd.md` (approved 2026-08-28), ADR-0001 (AXI-Lite 32-bit, accepted), ADR-0002 (FP64
datapath), ADR-0005 (register-map conventions). Block diagram: `docs/block_diagram.{json,mmd,svg}`
(`tools/hw/blockdiag.py`). Interview record: `prompt.txt` 2026-08-30 (Q1–Q8).

## 1. Context

`grape_pipeline` is a memory-mapped peripheral on the CPU's SoC bus (PRD §5, Q7): one AXI4-Lite
slave window of 4 KB, one level interrupt, one clock. No DMA and no streaming ports: the whole
body state (280 B) and pair list (40 B) are written and read through the window. Software
(`GrapeDriver.advance(dt, n, bodies, pairs)`) loads state, configures DT/NSTEPS/NPAIRS, rings the
doorbell, waits for DONE, and reads the committed state back.

## 2. I/O table

| Signal | Dir | Width | Clock | Reset value | Description |
|---|---|---|---|---|---|
| `clk` | in | 1 | — | — | single system clock, K2 ≥ 50 MHz |
| `rst_n` | in | 1 | `clk` | — | synchronous, active-low; every register → 0 (PRD-F15) |
| `s_axi_awaddr` | in | 12 | `clk` | — | AXI-Lite write address (byte, 4 KB window) |
| `s_axi_awprot` | in | 3 | `clk` | — | ignored |
| `s_axi_awvalid` / `s_axi_awready` | in / out | 1 / 1 | `clk` | — / 0 | write address handshake |
| `s_axi_wdata` | in | 32 | `clk` | — | write data, little-endian word |
| `s_axi_wstrb` | in | 4 | `clk` | — | byte strobes (honoured) |
| `s_axi_wvalid` / `s_axi_wready` | in / out | 1 / 1 | `clk` | — / 0 | write data handshake |
| `s_axi_bresp` | out | 2 | `clk` | 0 | OKAY / SLVERR (out-of-window) |
| `s_axi_bvalid` / `s_axi_bready` | out / in | 1 / 1 | `clk` | 0 / — | write response handshake |
| `s_axi_araddr` | in | 12 | `clk` | — | read address |
| `s_axi_arprot` | in | 3 | `clk` | — | ignored |
| `s_axi_arvalid` / `s_axi_arready` | in / out | 1 / 1 | `clk` | — / 0 | read address handshake |
| `s_axi_rdata` | out | 32 | `clk` | 0 | read data |
| `s_axi_rresp` | out | 2 | `clk` | 0 | OKAY / SLVERR |
| `s_axi_rvalid` / `s_axi_rready` | out / in | 1 / 1 | `clk` | 0 / — | read data handshake |
| `irq` | out | 1 | `clk` | 0 | level, = \|(STATUS & IRQ_EN) (PRD-F12) |

Parameters: `N_BODIES = 5`, `N_PAIRS_MAX = 10` (PRD-F6; only defaults verified).

## 3. Clock and reset

One clock domain (`clk`); `rst_n` synchronous, asserted for ≥ 1 cycle; no CDC. After reset
release the module is idle within 1 cycle; every RW/W1C register and counter reads 0 (PRD-F15;
ID and VERSION are constants), `irq` = 0. Reset drops any in-flight AXI transaction (the
handshake cell deasserts `bvalid`/`rvalid`); the bus master is reset together with the module.

## 4. Register map (ADR-0005 header + module registers)

Byte offsets in the 4 KB window. Access: RO, RW, W1C (write 1 to clear), WP (write-1 pulse, reads 0).
Reserved bits and listed reserved words: write ignored, read 0, response OKAY. Offsets not listed
→ SLVERR (read data 0). Writes to RO registers: ignored, OKAY. **Writable while BUSY: only STATUS
(W1C), IRQ_EN and CTRL**; a write to any *listed* RW configuration register (DT, NSTEPS, NPAIRS, BODY[i] fields,
PAIR[k]) or a DOORBELL while BUSY is ignored with ERR_BUSY (response OKAY); reserved and unmapped
words keep their table behaviour regardless of BUSY. Configuration registers hold *pending* values:
while idle a read returns what software last wrote (PRD-F7 round-trip); at the accepted doorbell
the pending values are latched into the working copy; while BUSY reads return the latched values
and BODY reads return the **committed** snapshot (state at the doorbell, PRD-F10); at
DONE/ABORTED the committed state is copied into the BODY pending registers, so the read-back in
§5 step 3 reads the result. STATUS and the counters are live.

| Offset | Name | Bits | Access | Reset | Description |
|---|---|---|---|---|---|
| 0x000 | ID | 31:0 | RO | 0x47525031 | ASCII `GRP1` |
| 0x004 | VERSION | 31:0 | RO | 0 | git short SHA (synthesis parameter) |
| 0x008 | CTRL | 0 | WP | 0 | DOORBELL: start an invocation (PRD-F1); ignored + ERR_BUSY while BUSY (F9); rejected with ERR_PARAM (F17) |
| | | 1 | WP | 0 | ABORT: stop at the next step boundary (F11); no-op when idle; wins over bit 0 in the same write |
| 0x00C | STATUS | 0 | RO | 0 | BUSY |
| | | 1 | W1C | 0 | DONE |
| | | 2 | W1C | 0 | ABORTED |
| | | 8 | W1C | 0 | ERR_BUSY (F9) |
| | | 9 | W1C | 0 | ERR_PARAM (F17: pair index ≥ N_BODIES or NPAIRS > N_PAIRS_MAX) |
| | | 12 | W1C | 0 | FP_INVALID (F13) |
| | | 13 | W1C | 0 | FP_DIVZERO |
| | | 14 | W1C | 0 | FP_OVERFLOW |
| | | 15 | W1C | 0 | FP_UNDERFLOW |
| | | 16 | W1C | 0 | FP_DENORMAL — reserved for the uArch subnormal decision (PRD §8 Q1); reads 0 until then |
| 0x010 | IRQ_EN | 16:1 | RW | 0 | mask over STATUS sticky bits (same bit positions); may be written while BUSY |
| 0x014 | IRQ_STATUS | 16:1 | RO | 0 | STATUS & IRQ_EN |
| 0x018–0x03C | — | — | reserved | 0 | RAZ/WI, OKAY (ADR-0005 header gap) |
| 0x040 | CYCLES_LO | 31:0 | RO | 0 | busy cycles of the last invocation, low word (F14) |
| 0x044 | CYCLES_HI | 31:0 | RO | 0 | high word |
| 0x048 | STEPS_DONE | 31:0 | RO | 0 | steps committed in the last/current invocation (live) |
| 0x04C–0x0FC | — | — | reserved | 0 | RAZ/WI, OKAY |
| 0x100 | DT_LO | 31:0 | RW | 0 | dt, IEEE binary64 low word (F7) |
| 0x104 | DT_HI | 31:0 | RW | 0 | dt high word |
| 0x108 | NSTEPS | 31:0 | RW | 0 | steps per invocation; 0 → immediate DONE (F8) |
| 0x10C | NPAIRS | 7:0 | RW | 0 | pairs walked per step, 0..N_PAIRS_MAX (ERR_PARAM above) |
| 0x110–0x1FC | — | — | reserved | 0 | RAZ/WI, OKAY |
| 0x200 + 64·i | BODY[i].X_LO/HI … | 31:0 × 14 | RW | 0 | body i (0..4): x, y, z, vx, vy, vz, m as FP64 pairs at +0x00, +0x08, +0x10, +0x18, +0x20, +0x28, +0x30; +0x38 reserved. Same window is the read-back window: reads return the **committed** state (F10) |
| 0x340–0x3FC | — | — | reserved | 0 | RAZ/WI, OKAY |
| 0x400 + 4·k | PAIR[k] | 15:8 j, 7:0 i | RW | 0 | pair k (0..9): i = first body (b1, mass m1 in PRD-F2), j = second (b2); any field ≥ N_BODIES → ERR_PARAM at the doorbell (F17); order is semantic (F3) |
| 0x428–0xFFC | — | — | — | — | not mapped → SLVERR |

64-bit values: low word at the lower offset; software writes LO then HI (any order is accepted;
the pair is latched at the doorbell). CYCLES: while not BUSY the two words are stable and read LO
then HI; while BUSY they are live with **no atomicity guarantee** (software re-reads or waits).

### 4.1 Delta to the shared AXI-Lite cell (`hw/common/rtl/axi_lite_regs.sv`)

The shared cell stores a flat contiguous register array with a hardware-override port; it cannot
express W1C, write-1-pulse, "ignored while BUSY", sparse decode with SLVERR, or a delayed write
response. `hw-rtl` therefore splits it: **`axi_lite_if.sv`** keeps only the AXI4-Lite handshake
and exposes a simple register bus — `req_wr` (addr[11:2], wdata, wstrb), `req_rd` (addr[11:2]),
`rd_data`, `rd_err`, `wr_err`, and **`wr_resp_hold`** (the module holds BRESP until the doorbell's
acceptance/rejection is visible in STATUS, ADR-0005) — and every module implements its own decoder
with the access types above. `axi_lite_regs.sv` stays as the smoke-test cell. The register bus is
the seam the testbench's register agent drives in unit tests.

## 5. Data path protocol

MMIO only (ADR-0001): no DMA, no streams. Per invocation: 70 words of body state + 10 pair words
+ 4 configuration words in; 1 doorbell; 60 words of state + 3 counter words out ≈ 150 AXI-Lite
transactions ≈ 600 bus cycles (estimate: 4 cycles per transaction from the handshake cell's
AW/W capture + B response; `test_driver` measures the real figure with `cocotbext-axi`). The
per-invocation model of PRD K1 is unchanged by this register map (PRD §8 Q4 closed): the
accelerator time is CYCLES, the bus time is < 0.03 % of it.
Doorbell write response (BRESP) is returned only after the module has latched the configuration
and STATUS shows BUSY or ERR_PARAM (ADR-0005), so `start()` → `status()` is never stale.

Invocation sequence (software view):
1. write BODY window (70 words), PAIR window (NPAIRS words), DT, NSTEPS, NPAIRS;
2. write CTRL.DOORBELL; read STATUS: BUSY = 1 (accepted) or ERR_PARAM = 1 (rejected);
3. poll STATUS.DONE or wait for `irq` (IRQ_EN.DONE = 1); on DONE: read CYCLES, STEPS_DONE, BODY window;
4. write STATUS = DONE (W1C) to clear.

## 6. Driver API (Python, `hw/grape_pipeline/driver/`, reused by `hw-integrate`)

```python
class AccelDriver:                       # shared base (ADR-0005), hw/common/driver/accel.py
    def __init__(self, bus, base): ...    # bus: read32(addr)/write32(addr, v)
    def status(self) -> int
    def start(self) -> bool               # doorbell; False if ERR_PARAM
    def abort(self) -> None
    def wait_done(self, max_polls: int) -> int        # polls STATUS until DONE|ABORTED; raises only on
                                                      # timeout or ERR_PARAM/ERR_BUSY raised since start();
                                                      # FP_* flags are returned, never raised
    def clear(self, bits: int = 0x1FFFE) -> None      # W1C, all sticky bits 16:1
    def counters(self) -> dict            # {"cycles": int, ...}

class GrapeDriver(AccelDriver):
    N_BODIES, N_PAIRS_MAX = 5, 10
    def load_bodies(self, bodies) -> None            # bodies: [[r[3], v[3], m], ...] (benchmark layout)
    def load_pairs(self, index_pairs: list[tuple[int, int]]) -> None   # validated < N_BODIES before writing
    def configure(self, dt: float, nsteps: int) -> None
    def read_bodies(self, bodies) -> None            # writes r and v back into the same lists; mass untouched
    def advance(self, dt, n, bodies, pairs) -> None  # benchmark signature: pairs are (body, body) tuples of
                                                     # the same list objects -> indices by identity (i = first,
                                                     # j = second); load, start, wait_done, read_bodies
```

`hw/common/driver/accel.py` and `hw/grape_pipeline/driver/` are created by `hw-integrate`; the
signatures above are the contract.

## 7. Block diagram

`docs/block_diagram.svg` (from `block_diagram.json`; Mermaid source `block_diagram.mmd`):
Host/bus (CPU + driver ⇄ AXI4-Lite handshake cell; STATUS/`irq` back to the CPU) → Control
(register file with pending/latched copies, step FSM with doorbell and abort, counters) → State
(double-buffered body register file: working + committed snapshot; pair list) → Datapath (pair
pipeline, ordered velocity accumulate, position integrator) → commit into the body register file
at each step boundary. Internal widths and stage counts are uArch decisions; the MAS fixes only
the external interface and the block boundaries.

## 8. Error and status behaviour

| Event | STATUS bits | BUSY | irq (if enabled) | Counters |
|---|---|---|---|---|
| doorbell accepted | BUSY = 1 | 1 | — | CYCLES restarts, STEPS_DONE = 0 |
| DONE | DONE | 0 | DONE | CYCLES stops (inclusive), STEPS_DONE = NSTEPS |
| ABORT (while BUSY) | ABORTED within K1 + 8 cycles of the write (F11); DONE instead if the boundary reached is step NSTEPS | 0 | ABORTED | CYCLES stops, STEPS_DONE = completed steps |
| ABORT while idle | none | 0 | — | unchanged |
| DOORBELL + ABORT in one write | idle: nothing starts, no flags; BUSY: ABORT acts **and** ERR_BUSY (the doorbell was ignored) | — | — | — |
| ABORT in the same cycle the doorbell is accepted | the invocation starts and is aborted at its first step boundary (ABORTED) | — | ABORTED | STEPS_DONE ≤ 1 |
| doorbell/config write while BUSY | ERR_BUSY | unchanged | ERR_BUSY | unchanged |
| doorbell rejected (F17) | ERR_PARAM | 0 | ERR_PARAM | hold |
| IEEE exception in the datapath | FP_* sticky | continues | FP_* | continues |
| reset | all 0 | 0 | 0 | 0 |

Sticky bits are cleared only by W1C or reset; an accepted doorbell does not clear them (F12).
`irq` is a registered copy of \|(STATUS & IRQ_EN): it rises the cycle after the sticky bit is set
(within the 2-cycle bound of F12) and falls the cycle after the W1C or after IRQ_EN clears the
mask — clearing IRQ_EN never touches STATUS.

## 9. Traceability

| PRD | MAS element |
|---|---|
| F1, F7 | §4 DT/NSTEPS/NPAIRS/BODY/PAIR registers, §5 sequence |
| F8 | NSTEPS = 0 → DONE (STATUS) |
| F9, F10 | §4 pending/latched/committed rules, ERR_BUSY, writable-while-BUSY set |
| F11 | CTRL.ABORT, ABORTED within K1 + 8 cycles, STEPS_DONE, same-write rules (§8) |
| F12 | STATUS W1C, IRQ_EN/IRQ_STATUS, `irq` |
| F13 | FP_* sticky bits |
| F14 | CYCLES_LO/HI, STEPS_DONE |
| F15 | §3 reset |
| F16 | §2 AXI-Lite I/O, `cocotbext-axi` agent |
| F17 | ERR_PARAM, CTRL.DOORBELL rejection |
| K1 | CYCLES / STEPS_DONE (§4) |

## 10. Review findings

See `docs/review_mas.md` (written by `hw-review`).
