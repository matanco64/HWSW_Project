# pyflate_accel — huffman_engine -> mtf_cam chain (integration check)
`rtl/pyflate_accel.sv`: logic-free wrapper, one `clk`/`rst_n`, `huffman_engine.m_sym` wired straight
to `mtf_cam.s_sym` (ADR-0006), AXI4-Lite slaves `h_axi_*` / `m_axi_*`, inputs `s_axis_bits` /
`s_axis_sel`, output `m_axis_l` (W=8), `h_irq` / `m_irq`. No existing file was changed.

Run (Verilator, ~30 s incl. build): `cd <repo> && source ./hw/env.sh && make -C hw/pyflate_accel sim`

`tb/test_chain.py` (plain cocotb) programs both modules like their own full-benchmark sequences,
doorbells mtf_cam first then huffman_engine, streams the real benchmark block (interpreter.tar.bz2
block 0, 148,271 symbols) and compares `m_l` (TKEEP honoured) with the golden L-vector from
`hw/mtf_cam/golden/mtf_ref.trace_benchmark()`.

Measured 2026-09-19: PASS, 336,184 / 336,184 bytes exact, 0 mismatches, both always-ready and with
random 50% `m_l` back-pressure. Chain cycles (huffman doorbell accepted -> mtf DONE): **159,303**
(huffman CYCLES 159,294, mtf CYCLES 159,314; standalone 149,276 / 158,441); 189,448 under
back-pressure. ~ mtf standalone + huffman's 1,008-cycle start-up (mtf's 145-cycle INIT overlaps it).

Link statistics, always-ready run (logged by `tb/test_chain.py`): 148,271 symbol beats on the
internal link, 0 malformed; the decoder is stalled by `mtf_cam` (`tready` low) on 10,013 cycles and
`mtf_cam` starves (no valid beat) on 873 — the chain runs at `mtf_cam`'s rate.
