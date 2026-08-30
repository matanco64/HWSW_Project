---
status: accepted
---
# Register-map conventions shared by all accelerator modules

Every module owns a 4 KB AXI-Lite window with the same header so the three Python drivers share
one base class (`AccelDriver`) and one testbench register agent:

| Offset | Name | Access | Meaning |
|---|---|---|---|
| 0x000 | ID | RO | ASCII tag (`GRP1`, `HUF1`, `MTF1`) |
| 0x004 | VERSION | RO | git short SHA of the RTL at synthesis (0 in simulation unless set) |
| 0x008 | CTRL | WO pulse | bit 0 DOORBELL, bit 1 ABORT (write-1 pulses, read 0; both set → ABORT wins) |
| 0x00C | STATUS | RO / W1C | bit 0 BUSY (RO); sticky, W1C: bit 1 DONE, bit 2 ABORTED, bits 8.. ERR_* per module |
| 0x010 | IRQ_EN | RW | mask over the STATUS sticky bits; `irq` = |(STATUS & IRQ_EN) |
| 0x014 | IRQ_STATUS | RO | STATUS & IRQ_EN |
| 0x040.. | counters | RO | 64-bit values as two words, low word at the lower offset |
| 0x100.. | module registers | per MAS | configuration, latched at the accepted doorbell |

Rules: reserved bits and listed reserved words write-ignored / read-0 with OKAY; offsets outside
the window, and in-window words a module's map lists as unmapped, → SLVERR; configuration
registers may be written in any order and are latched when the doorbell is accepted (writes while
BUSY are ignored with ERR_BUSY); the doorbell's write response is returned only after acceptance
or rejection is visible in STATUS, so a STATUS read after `start()` is never stale; configuration
reads while BUSY return the latched values, STATUS and counters are live; reset zeroes every
register. Chosen over per-module ad-hoc maps because three modules × one course team cannot afford
three drivers, and over a generated register file (e.g. SystemRDL) because the shared
`axi_lite_regs.sv` cell already exists and the maps are small.
