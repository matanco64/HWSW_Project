---
status: accepted
date: 2026-09-07
---

# huffman_engine: single-cycle decode loop, folded counts, six table register sets

The decode recurrence — symbol N+1's window position depends on symbol N's decoded length —
is the only serial dependency in the engine and therefore sets K1 (≤ 1.1 cycles/symbol).
Decisions (uArch interview 2026-09-07, Q1..Q7):

1. **1-cycle decode loop** (Q1a): window barrel-shift, 20 parallel `first_code[len]` compares,
   priority-encode and length-consume close combinationally in one cycle; symtab lookup and
   beat emission pipeline BEHIND the loop (2 stages) and never feed it. Documented retreat if
   sky130 STA fails at 50 MHz: II=2 loop (2.0 cycles/symbol — busts K1, requires KPI
   renegotiation; grape precedent says fix the RTL first).
2. **Aligner** (Q2): 64-bit shift buffer + barrel shifter, peek MAXLEN / consume ≤ 20 per
   cycle, 32-bit refill concurrent with consume; DEFLATE reverses the 15-bit peek window
   combinationally (input lanes stay MSB-first-addressed for START_BIT).
3. **One shared symtab** (Q3a): 6×288×9-bit flop array indexed
   `table_base[tab] + base[len] + (code − first_code[len])` — single read port, one adder,
   no per-table read-mux fabric (grape area lesson).
4. **Counts folded into config writes** (Q4): the per-length count array increments as
   software writes the length window, removing the counts pass from the build FSM: build =
   ALPHABET + MAXLEN ≈ 167 cycles/table vs the K2 bound 2×ALPHABET+MAXLEN = 314 (was
   zero-margin serial; now ~1.9× margin).
5. **Six (first_code, base) register sets** (Q5), selector prefetched into a 1-deep skid →
   0-cycle table switch. Rejected: re-derive on switch (~0.8 cycles/symbol at 2,965 switches —
   busts K1 alone).
6. **DEFLATE extra bits via post-decode sub-FSM** (Q6): +1..2 stall cycles per length/distance
   symbol in DEFLATE mode only; K1 binds on bzip2. Folding into the shifter deferred until a
   DEFLATE KPI exists.
7. **2-deep output skid** on `m_sym` (Q7): tvalid decoupled from tready (PRD-F6); ADR-0006
   withdrawal = skid flush on ERR/ABORT/doorbell; backpressure freezes the loop via one stall.

K1 is derived by cycle simulation over the real benchmark trace (docs/decode_model.py on
golden `trace_benchmark()` — 148,271 symbols), never a stage-sum (grape sign-off lesson).
