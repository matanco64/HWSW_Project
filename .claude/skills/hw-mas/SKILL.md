---
name: hw-mas
description: Write the Architecture Spec (external view: I/O, register map, DMA/stream, driver API, block diagram) for an accelerator module through a grilling interview (stage 2 of hw/FLOW.md). Use when hw-flow reaches the mas stage or the user asks for the interface spec, register map, or block diagram.
---

# hw-mas — stage 2, MAS

Inputs: `hw/<module>/docs/prd.md` (approved), `hw/CONTEXT.md`, ADRs, `report_<bench>.txt` §5
register-map sketch, `research/hw-algorithms-<bench>.md`. Outputs: `hw/<module>/docs/mas.md`,
`hw/<module>/docs/block_diagram.mmd` (Mermaid) rendered to `block_diagram.svg`
(`mmdc -i block_diagram.mmd -o block_diagram.svg`, or the Mermaid block pasted into the report).
MAS for the three modules is written in lockstep; the bus, clock and driver conventions are shared
ADRs.

## Procedure

1. `python3 tools/hw/status.py set <module> mas in_progress`.
2. Interview with `grill-with-docs`, agenda below. Terms → `hw/CONTEXT.md`; shared choices → ADR.
3. Write `docs/mas.md` sections: Context (where the block sits, host, memory); I/O table; Clock and
   reset; Register map; Data path protocol (DMA descriptor or stream); Driver API; Block diagram;
   Error and status behaviour; Traceability to `PRD-Fn`.
4. I/O table columns: signal, direction, width, clock, reset value, description. Register map
   columns: offset, name, bits, access (RO/RW/W1C/WO), reset, description; every field has a
   defined behaviour on write of reserved bits.
5. Driver API sketch as Python signatures (`load_state()`, `start()`, `wait_done()`, ...) — these
   names are reused by `hw-integrate` for `hw/<module>/driver/`.
6. `hw-review` spec mode; resolve `must` findings. Record gate rows; set `review`.

## Agenda (module-specific)

**All** — AXI-Lite MMIO for control/status (`cocotbext-axi` is the tb driver) vs custom; DMA
descriptor (address, length, bit offset, table pointer, doorbell) vs pure valid/ready streaming with
a host FIFO — decide per module, one ADR for the shared choice. Interrupt vs polling `STATUS`.
Single clock domain, `rst_n`. Endianness and bit order of every stream.
**grape_pipeline** — MMIO state-load window (5 bodies × pos/vel/mass, FP64 = 2 words each),
`DT`, `NSTEPS`, `START`, `STATUS/IRQ`, read-back window; pair-list input (10 pairs default, table
writable); data volume per `advance()` call ~280 B in, 240 B out.
**huffman_engine** — descriptor: `SRC_ADDR`, `SRC_BITOFF`, `TBL_ADDR` (258 × 5-bit lengths × ≤ 6
tables), `DST_ADDR`, `LEN`, `MODE` (bzip2/DEFLATE), `DOORBELL`; selector list input; output
symbol stream width (9-bit symbol + table id) and whether it streams straight into `mtf_cam`.
**mtf_cam** — input = symbol stream from `huffman_engine` (or DMA replay for standalone test);
output = L-vector bytes; initial-table load (256 B); `RUNA/RUNB` accumulator overflow policy;
end-of-block signalling.

## Gate (FLOW.md row 2)

| Criterion | Evidence |
|---|---|
| I/O table with widths + clock | `docs/mas.md §I/O` — every row has width and clock |
| register map (offset, name, bits, access, reset) | `docs/mas.md §Register map` — all five columns filled |
| DMA/stream protocol | `docs/mas.md §Data path protocol` + ADR id |
| driver API sketch | `docs/mas.md §Driver API` |
| block diagram | `docs/block_diagram.svg` exists |
| `hw-review` resolved | `docs/review_mas.md: N findings, 0 must open` |

```
python3 tools/hw/status.py gate <module> mas "<criterion>" pass "<evidence>"   # ×6
python3 tools/hw/status.py set <module> mas review
```
