# huffman_engine — RTL block contracts (binding for parallel implementation)

Authoritative inputs: `docs/uarch.md` (blocks, formats, FSMs — U/N review-proven),
`docs/mas.md` §2/§4/§8 **including the 2026-09-08 amendments** (per-table 48-word lengths
strides, wstrb rule, DBG FILL rule), ADR-0006/0008. Style: `claude-skill-verilog`
(always_ff simple assignments, logic in always_comb, sized literals, Yosys 0.68 subset — no
unpacked localparam arrays, no fn-call bit-selects, no struct arrays; packed localparam
vectors fold, case-functions don't scale — see hw/docs/lessons.md 2026-09-05).
Oracles: `golden/canonical_model.py` (CanonicalTable: first_code/base/limits/decode),
`golden/pyflate_ref.py` (trace). Do NOT modify golden/, this file, uarch.md or mas.md.

Common: `clk`, `rst_n` (sync active-low). One always-valid global `stall` freezes the decode
pipeline (driven by top from skid-full / DEFLATE resolve / selector wait).

## huff_regs (`rtl/huff_regs.sv`) — pattern: `hw/grape_pipeline/rtl/grape_regs.sv`

AXI side: the register bus from shared `axi_lite_if` (req_wr, wr_addr[9:0] word address,
wr_data, wr_strb, wr_err, wr_resp_hold, req_rd, rd_addr, rd_data, rd_err) — exactly grape's.
Implements MAS §4: ID/VERSION/CTRL/STATUS/IRQ_EN/IRQ_STATUS header (ADR-0005 semantics:
doorbell WP + BRESP hold ≤ 4, W1C sticky, registered irq), MODE/START_BIT/ALPHABET/N_TABLES/
SYMBOL_LIMIT config (pending; latched on accepted doorbell), CYCLES/SYMBOLS/BITS/BUILD_CYCLES
counters (live inputs), DBG regs, and the **lengths window** at per-table 48-word strides:
6×5b fields per word, RMW on write (full wstrb only, else ignored whole): maintain
`count[6][20]` bins + per-table `invalid` bin (field > MAXLEN) + DEFLATE-16..20 usable via
bins. Doorbell checks: ERR_PARAM (MAS §4 list) and ERR_TABLE for nonzero invalid bins (and
DEFLATE bins 16..20 of used tables). Outputs to core:
`cfg_*` latched fields, `doorbell_o`/`abort_o` pulses, `lengths_rd` port (builder: addr
{t[2:0], sym[8:0]} → 5b, 1-cycle), `counts_rd` port ((t,l) → 9b comb), status set pulses in
(`done_set_i, aborted_set_i, err_set_i[6:0]` one-hot per MAS bits), counter inputs, `busy_i`.
Unit TB `tb/unit/test_regs.py` (pattern: grape's test_regs): map round-trips, stride
addressing, counts RMW (write/rewrite/decrement), invalid bins → ERR_TABLE at doorbell,
ERR_PARAM cases, W1C/IRQ, writes-while-busy ignored + ERR_BUSY, BRESP hold. TB wrapper
`rtl/huff_regs_tb_top.sv` (regs + axi_lite_if, core signals as ports — grape pattern).

## huff_aligner (`rtl/huff_aligner.sv`)

```
input  s_axis_bits_tdata[31:0], tkeep[3:0], tlast, tvalid; output tready
input  start_i (begin skip: cfg_start_bit_i[31:0]), mode_deflate_i
input  consume_i[4:0] (0..20, valid when consume_en_i), skid of control: enable_i (DECODE)
output window_o[19:0]   // top-aligned peek; DEFLATE: bit-reversed 15b in [19:5], [4:0]=0
output occ_ok_o         // occ >= MAXLEN, or zero-padded tail after TLAST
output skip_done_o, underrun_o (consume past last_valid bit), bits_consumed_o[31:0]
```
64b buffer + 2-beat FIFO (accepted-unconsumed ≤ 128b — MAS cap; tready = FIFO not full &
enabled). MSB-first bit order: byte 0 bit 7 is the stream's first bit (bzip2); maintain
last_valid from TLAST+tkeep; zero-pad after. SKIP: discard floor(start/32) words 1/beat, then
sub-word remainder via consume. Unit TB `tb/unit/test_aligner.py`: random bitstreams + random
consume sequences vs a Python bit-slicer oracle; skip offsets incl. word-aligned/±1; tail/
underrun; DEFLATE reversal; tkeep partial last beat; backpressure (tvalid gaps).

## huff_builder + huff_tables (`rtl/huff_builder.sv`, `rtl/huff_tables.sv`)

builder: FSM per uArch §3.2. Reads `lengths_rd`/`counts_rd` from regs; per table t <
n_tables: PREFIX (l = 1..MAXLEN: first_code/base/limit_la regs written into set t; Kraft
overflow → err_table_o pulse, abort build), FILL (s = 0..alphabet−1: symtab write
{valid=1, s[8:0]} at table_base+base[l]+next[l]; EOB latch when s == alphabet−1 (bzip2) /
256 (DEFLATE, table 0 only)). All eob_len cleared at start. `build_done_o`,
`build_cycles_o[15:0]` (max per-table). symtab entries not written in an invocation keep old
data but are unreachable (index math bounded) — no clear pass.
tables: storage + read view:
```
input  set_wr (from builder: set idx, l, first_code[19:0], limit_la[20:0], base[10:0]; table_base[10:0]/eob per set)
input  symtab_wr (addr[10:0], data[9:0]) ; input cur_set_i[2:0]
output limit_la_o[20:0][20]? -> flat: active set's 20 limit_la as [20*21-1:0], first_code flat, base flat, table_base, eob_len[4:0], eob_code[19:0]
input  symtab_rd_addr[10:0] -> output symtab_rd_data[9:0] (registered, 1 cycle — C1)
DBG: dbg_rd_addr/data valid outside FILL (else 0)
```
Unit TB `tb/unit/test_builder.py`: random length sets (+ benchmark's real 6 tables from
golden trace) → compare first_code/base/limit_la/symtab/eob against
`canonical_model.CanonicalTable`; Kraft violations → err_table; build_cycles == alphabet +
MAXLEN (K2 row evidence).

## huff_decoder (`rtl/huff_decoder.sv`) — built by the integrator (serial core)

C0 comb: window + active-set arrays → match mask (w < limit_la[l]), priority-min l, code_l,
eob_hit (l==eob_len && code_l==eob_code && eob_len!=0), nocode, index = table_base + base[l]
+ (code_l − first_code[l]); consume_o = l gated by issue.

## huff_selector / huff_out / huff_deflate / huff_ctrl / huffman_engine — integrator.

Interfaces per uArch §1/§3; m_sym beat per MAS §2 (ADR-0006); withdrawal = skid flush
(ERR_LIMIT exempt). SYMBOLS counts handshaken beats; BITS from aligner.

## Makefile note

Unit sims: `make -C hw/huffman_engine sim TOPLEVEL=<top> MODULE=unit.test_<x>
VERILOG_SOURCES="rtl/<files>"` (PYTHONPATH provides tb/, golden/, common/tb — grape pattern).
`tb/unit/__init__.py` must exist (create if missing).
