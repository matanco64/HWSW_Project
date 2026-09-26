# Slide B08 (BACKUP)

Layout: "Title and body". Insert at the end of the deck (backup section).

Title (exact text, do not shorten or rephrase):

    The HW/SW interface is one register-map convention over AXI4-Lite, AXI4-Stream for bulk data, and per-module driver models that match their maps with 0 diffs

Body: insert this table exactly (Insert → Table), header row bold with #1F4E79 fill and white text, body rows 16 pt, columns auto-fit, no other formatting:

| Offset | Register | Access | Meaning (huffman_engine, MAS §4) |
|---|---|---|---|
| 0x000 | ID | RO | ASCII `HUF1`; same header on every module (ADR-0005) |
| 0x008 | CTRL | write-1 pulse | bit 0 DOORBELL, bit 1 ABORT; ignored with ERR_BUSY while BUSY |
| 0x00C | STATUS | RO / W1C | BUSY live; sticky DONE, ABORTED, ERR_* |
| 0x040 | CYCLES_LO | RO | accepted doorbell → DONE, low word of a 64-bit counter |
| 0x104 | START_BIT | RW | first code bit inside the s_bits buffer |
| 0x400 + 4·w | LEN[w] | RW | length window, 288 words of six 5-bit fields |

Footer tracker on this slide: make the current stage bold and #1F4E79, leave the others grey:

    Analyze   ·   Profile   ·   Optimize   ·   **Accelerate**   ·   Trade-offs

Speaker notes (exact text, paste into the notes pane):

    Every module owns a 4 KB AXI4-Lite window with the same header (ID, VERSION, CTRL, STATUS, IRQ_EN, counters at 0x040, module registers from 0x100), so three Python drivers share one base class and one testbench register agent (ADR-0005). Bulk data never goes through registers: huffman takes the compressed bytes and selectors as AXI4-Stream, hands symbols to mtf_cam as 32-bit beats, and mtf_cam's 64-bit L-vector stream goes to platform DMA (ADR-0001). Each driver's offsets and fields are generated from its MAS §4 and check_regmap.py reports 0 diffs for all three. How far each driver was exercised, honestly: grape's is co-simulated against the RTL through the AXI-Lite agent, reading back all 35 state components bit-identical with CYCLES = 250; mtf's passes 16/16 in RTL co-simulation; huffman's is checked against the signed-off cycle model, not the RTL. Per block the huffman configuration is ≈ 157 AXI-Lite transactions, ≈ 628 cycles, with the streams overlapped by DMA; the DMA sink is assumed to sustain W = 8 bytes per cycle, ≈ 300 MB/s at 37.5 MHz. What remains unmeasured is T_if: configuration, DMA setup and the copies of the input and the 336,184 L-vector bytes. No software calls the hardware yet.

Done when: the title matches exactly, the body content is fully visible without overflow or
clipping, the tracker highlights "Accelerate", and the notes are saved. Reply with a screenshot of
the slide in edit view, then the STATUS block for B08 (expected: position end of deck, body table 7x4,
notes_set yes, tracker Accelerate highlighted).
