"""pyflate_accel chain check (plain cocotb, quick integration test, no pyuvm/scoreboard).

The real benchmark bzip2 block (interpreter.tar.bz2, block 0) goes into huffman_engine's
s_bits/s_sel streams; huffman_engine.m_sym feeds mtf_cam.s_sym on chip; the m_l byte stream is
reassembled (TKEEP honoured) and compared byte-exact against the frozen golden L-vector
(hw/mtf_cam/golden/mtf_ref.trace_benchmark().l_vector). Golden models are oracles only.

Programming mirrors each module's own full-benchmark sequence (huffman tb/sequences/bench.py,
mtf tb/sequences/smoke.py BenchSeq); mtf_cam is doorbelled BEFORE huffman_engine (mtf PRD-F4).
"""
import json
import pathlib
import random
import sys
import time

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, First, ReadOnly, RisingEdge, Timer
from cocotb.utils import get_sim_time
from cocotbext.axi import (AxiLiteBus, AxiLiteMaster, AxiStreamBus, AxiStreamFrame,
                           AxiStreamSink, AxiStreamSource)

HW = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HW / "mtf_cam" / "golden"))
import mtf_ref  # noqa: E402  (frozen golden tracer; pulls in huffman_engine/golden/pyflate_ref)

CLK_NS = 20
W = 8
TIMEOUT_CYCLES = 3_000_000

# huffman_engine register map (MAS §4, == hw/huffman_engine/tb/env.py)
H_CTRL, H_STATUS = 0x008, 0x00C
H_CYCLES_LO, H_CYCLES_HI, H_SYMBOLS, H_BITS, H_BUILD_CYCLES, H_OVERFETCH = \
    0x040, 0x044, 0x048, 0x04C, 0x050, 0x054
H_MODE, H_START_BIT, H_ALPHABET, H_N_TABLES, H_SYMBOL_LIMIT = 0x100, 0x104, 0x108, 0x10C, 0x110
H_LEN_BASE = 0x400
# mtf_cam register map (MAS §4, == hw/mtf_cam/tb/env.py)
M_CTRL, M_STATUS = 0x008, 0x00C
M_CYCLES_LO, M_CYCLES_HI, M_SYMBOLS_IN, M_BYTES_OUT, M_INIT_CYCLES, M_MAX_RUN = \
    0x040, 0x044, 0x048, 0x04C, 0x050, 0x054
M_SYMBOL_LIMIT, M_BYTES_LIMIT, M_USED_BASE = 0x100, 0x104, 0x200
ST_BUSY, ST_DONE = 1, 2

_CACHE = {}


def vectors():
    """Benchmark block inputs (huffman tb vectors, dumped from the golden tracer) + golden L."""
    if not _CACHE:
        vecdir = HW / "huffman_engine" / "tb" / "vectors"
        _CACHE["vec"] = json.loads((vecdir / "bench_block.json").read_text())
        _CACHE["stream"] = (vecdir / "bench_stream.bin").read_bytes()
        _CACHE["mt"] = mtf_ref.trace_benchmark()
    return _CACHE["vec"], _CACHE["stream"], _CACHE["mt"]


def pack_lengths(all_lengths, alphabet):
    """== hw/huffman_engine/tb/sequences/smoke.py pack_lengths (48-word stride per table)."""
    words = {}
    for t, lens in enumerate(all_lengths):
        assert len(lens) == alphabet
        for w in range(48 * t, 48 * t + (alphabet + 5) // 6):
            words[w] = 0
        for s, l in enumerate(lens):
            words[48 * t + s // 6] |= (l & 0x1F) << (5 * (s % 6))
    return words


async def wr(axil, addr, data):
    resp = await axil.write(addr, int(data).to_bytes(4, "little"))
    assert int(resp.resp) == 0, f"AXI-Lite write 0x{addr:x} resp {resp.resp}"


async def rd(axil, addr):
    resp = await axil.read(addr, 4)
    assert int(resp.resp) == 0, f"AXI-Lite read 0x{addr:x} resp {resp.resp}"
    return int.from_bytes(resp.data, "little")


class LMonitor:
    """Passive m_l monitor (RisingEdge+ReadOnly, same sampling as the module envs)."""

    def __init__(self, dut):
        self.dut = dut
        self.data = bytearray()
        self.beats = 0
        self.keeps_bad = []          # (beat index, keep) for non-full keep on a non-last beat
        self.last_seen = 0
        self.stalled_beats = 0       # cycles with tvalid && !tready
        self.t_first = None
        self.t_last = None

    async def run(self):
        d = self.dut
        full = (1 << W) - 1
        while True:
            await RisingEdge(d.clk)
            await ReadOnly()
            if int(d.rst_n.value) == 0 or int(d.m_axis_l_tvalid.value) == 0:
                continue
            if int(d.m_axis_l_tready.value) == 0:
                self.stalled_beats += 1
                continue
            keep = int(d.m_axis_l_tkeep.value)
            word = int(d.m_axis_l_tdata.value)
            last = int(d.m_axis_l_tlast.value)
            if self.t_first is None:
                self.t_first = get_sim_time("ns")
            assert self.last_seen == 0, "m_l beat after TLAST"
            for lane in range(W):
                if keep & (1 << lane):
                    self.data.append((word >> (8 * lane)) & 0xFF)
            contiguous = keep != 0 and (keep & (keep + 1)) == 0
            if not contiguous or (keep != full and not last):
                self.keeps_bad.append((self.beats, keep))
            self.beats += 1
            if last:
                self.last_seen = 1
                self.t_last = get_sim_time("ns")


class SymProbe:
    """Passive probe of the on-chip m_sym -> s_sym link (wrapper-internal wires)."""

    def __init__(self, dut):
        self.dut = dut
        self.beats = 0
        self.valid_not_ready = 0     # huffman offering, mtf stalling
        self.ready_not_valid = 0     # mtf waiting, huffman has nothing
        self.bad_type = 0
        self.last_beat = None
        self.tlast_count = 0
        self.t_first_valid = None
        self.t_first_hs = None

    async def run(self):
        d = self.dut
        while True:
            await RisingEdge(d.clk)
            await ReadOnly()
            v, r = int(d.sym_tvalid.value), int(d.sym_tready.value)
            if v and self.t_first_valid is None:
                self.t_first_valid = get_sim_time("ns")
            if v and r:
                if self.t_first_hs is None:
                    self.t_first_hs = get_sim_time("ns")
                word = int(d.sym_tdata.value)
                last = int(d.sym_tlast.value)
                typ = (word >> 9) & 7
                if typ not in (0, 3) or (word >> 28) or ((typ == 3) != bool(last)):
                    self.bad_type += 1
                self.beats += 1
                self.tlast_count += last
                self.last_beat = (word, last)
            elif v:
                self.valid_not_ready += 1
            elif r:
                self.ready_not_valid += 1


async def run_chain(dut, *, backpressure, seed=1):
    wall0 = time.time()
    vec, stream, mt = vectors()
    golden = bytes(mt.l_vector)
    used_bytes = [b for b in range(256) if mt.used[b]]
    assert mt.alphabet == vec["alphabet"], (mt.alphabet, vec["alphabet"])
    dut._log.info(f"benchmark block: start_bit={vec['start_bit']} alphabet={vec['alphabet']} "
                  f"tables={vec['n_tables']} selectors={len(vec['selectors'])} "
                  f"symbols={vec['n_symbols']} stream={len(stream)}B golden L={len(golden)}B")

    cocotb.start_soon(Clock(dut.clk, CLK_NS, "ns").start())
    dut.rst_n.value = 0
    h_axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "h_axi"), dut.clk, dut.rst_n,
                           reset_active_level=False)
    m_axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "m_axi"), dut.clk, dut.rst_n,
                           reset_active_level=False)
    bits_src = AxiStreamSource(AxiStreamBus.from_prefix(dut, "s_axis_bits"), dut.clk, dut.rst_n,
                               reset_active_level=False)
    sel_src = AxiStreamSource(AxiStreamBus.from_prefix(dut, "s_axis_sel"), dut.clk, dut.rst_n,
                              reset_active_level=False)
    l_sink = AxiStreamSink(AxiStreamBus.from_prefix(dut, "m_axis_l"), dut.clk, dut.rst_n,
                           reset_active_level=False)
    await ClockCycles(dut.clk, 8)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 4)

    if backpressure:
        rng = random.Random(seed)

        def pauses():
            while True:
                yield rng.random() < 0.5
        l_sink.set_pause_generator(pauses())

    lmon, sprobe = LMonitor(dut), SymProbe(dut)
    cocotb.start_soon(lmon.run())
    cocotb.start_soon(sprobe.run())

    # streams queued up front; they wait on tready (0 until huffman's doorbell PREP)
    await bits_src.send(AxiStreamFrame(stream))
    await sel_src.send(AxiStreamFrame(bytes(vec["selectors"])))

    # ---- program mtf_cam (== MtfBaseSeq.program_used) ----
    words = [0] * 8
    for b in used_bytes:
        words[b >> 5] |= 1 << (b & 31)
    for w in range(8):
        await wr(m_axil, M_USED_BASE + 4 * w, words[w])
    await wr(m_axil, M_SYMBOL_LIMIT, 1 << 20)
    await wr(m_axil, M_BYTES_LIMIT, 1 << 20)
    # ---- program huffman_engine (== HuffBaseSeq.program) ----
    await wr(h_axil, H_MODE, 0)
    await wr(h_axil, H_START_BIT, vec["start_bit"])
    await wr(h_axil, H_ALPHABET, vec["alphabet"])
    await wr(h_axil, H_N_TABLES, vec["n_tables"])
    await wr(h_axil, H_SYMBOL_LIMIT, 1 << 20)
    for w, val in sorted(pack_lengths(vec["lengths"], vec["alphabet"]).items()):
        await wr(h_axil, H_LEN_BASE + 4 * w, val)

    # ---- event timestamps on the modules' own accepted-doorbell / DONE pulses ----
    ev = {}

    async def stamp(name, sig):
        await RisingEdge(sig)
        ev[name] = get_sim_time("ns")

    for name, sig in (("m_doorbell", dut.u_mtf.doorbell), ("h_doorbell", dut.u_huff.doorbell),
                      ("h_done", dut.u_huff.done_set), ("m_done", dut.u_mtf.done_set)):
        cocotb.start_soon(stamp(name, sig))

    # ---- doorbells: mtf_cam FIRST, then huffman_engine ----
    await wr(m_axil, M_CTRL, 1)
    st = await rd(m_axil, M_STATUS)
    dut._log.info(f"mtf STATUS after doorbell: 0x{st:x}")
    await wr(h_axil, H_CTRL, 1)

    # ---- wait for mtf DONE (timeout-guarded), then let m_l drain its TLAST beat ----
    done = RisingEdge(dut.u_mtf.done_set)
    got = await First(done, Timer(TIMEOUT_CYCLES * CLK_NS, "ns"))
    timed_out = got is not done
    for _ in range(2000):
        if lmon.last_seen or timed_out:
            break
        await ClockCycles(dut.clk, 1)
    await ClockCycles(dut.clk, 8)

    h_st, m_st = await rd(h_axil, H_STATUS), await rd(m_axil, M_STATUS)
    hc = {n: await rd(h_axil, a) for n, a in (
        ("cycles_lo", H_CYCLES_LO), ("cycles_hi", H_CYCLES_HI), ("symbols", H_SYMBOLS),
        ("bits", H_BITS), ("build_cycles", H_BUILD_CYCLES), ("overfetch", H_OVERFETCH))}
    mc = {n: await rd(m_axil, a) for n, a in (
        ("cycles_lo", M_CYCLES_LO), ("cycles_hi", M_CYCLES_HI), ("symbols_in", M_SYMBOLS_IN),
        ("bytes_out", M_BYTES_OUT), ("init_cycles", M_INIT_CYCLES), ("max_run", M_MAX_RUN))}
    h_cycles = hc["cycles_lo"] | (hc["cycles_hi"] << 32)
    m_cycles = mc["cycles_lo"] | (mc["cycles_hi"] << 32)

    # ---- compare ----
    got_bytes = bytes(lmon.data)
    n_cmp = min(len(got_bytes), len(golden))
    mism = [i for i in range(n_cmp) if got_bytes[i] != golden[i]]
    tag = "BACKPRESSURE" if backpressure else "ALWAYS-READY"
    log = dut._log.info
    log(f"[{tag}] STATUS huffman=0x{h_st:x} mtf=0x{m_st:x} timed_out={timed_out}")
    log(f"[{tag}] huffman counters: CYCLES={h_cycles} {hc}")
    log(f"[{tag}] mtf counters:     CYCLES={m_cycles} {mc}")
    log(f"[{tag}] events (ns): {ev}")
    if "h_doorbell" in ev and "m_done" in ev:
        chain = (ev["m_done"] - ev["h_doorbell"]) / CLK_NS
        log(f"[{tag}] CHAIN CYCLE COUNT (huffman doorbell accepted -> mtf DONE) = {chain:.0f}")
        if "m_doorbell" in ev:
            log(f"[{tag}] mtf doorbell -> mtf DONE = {(ev['m_done'] - ev['m_doorbell']) / CLK_NS:.0f}"
                f" ; mtf doorbell -> huffman doorbell = "
                f"{(ev['h_doorbell'] - ev['m_doorbell']) / CLK_NS:.0f} cycles")
        if "h_done" in ev:
            log(f"[{tag}] huffman doorbell -> huffman DONE = "
                f"{(ev['h_done'] - ev['h_doorbell']) / CLK_NS:.0f} ; huffman DONE -> mtf DONE = "
                f"{(ev['m_done'] - ev['h_done']) / CLK_NS:.0f} cycles")
        if lmon.t_last is not None:
            log(f"[{tag}] huffman doorbell -> m_l TLAST beat accepted = "
                f"{(lmon.t_last - ev['h_doorbell']) / CLK_NS:.0f} cycles")
    log(f"[{tag}] sym link: beats={sprobe.beats} tlast={sprobe.tlast_count} "
        f"bad_format={sprobe.bad_type} last_beat={sprobe.last_beat and hex(sprobe.last_beat[0])} "
        f"valid&!ready={sprobe.valid_not_ready} ready&!valid={sprobe.ready_not_valid} "
        f"first_valid@{sprobe.t_first_valid}ns first_handshake@{sprobe.t_first_hs}ns")
    log(f"[{tag}] m_l: beats={lmon.beats} bytes={len(got_bytes)} tlast={lmon.last_seen} "
        f"stall_cycles={lmon.stalled_beats} bad_keep={lmon.keeps_bad[:4]}")
    log(f"[{tag}] COMPARE: got={len(got_bytes)} golden={len(golden)} compared={n_cmp} "
        f"mismatches={len(mism)} first_mismatch={mism[0] if mism else None}")
    log(f"[{tag}] wall time {time.time() - wall0:.1f} s")
    if mism:
        i = mism[0]
        log(f"[{tag}] around first mismatch {i}: got={got_bytes[max(0, i - 8):i + 8].hex()} "
            f"golden={golden[max(0, i - 8):i + 8].hex()}")

    assert not timed_out, "mtf_cam DONE not seen (timeout)"
    assert (h_st & 0xFF06) == ST_DONE, f"huffman STATUS 0x{h_st:x} != DONE only"
    assert (m_st & 0x3F06) == ST_DONE, f"mtf STATUS 0x{m_st:x} != DONE only"
    assert len(golden) == 336_184, len(golden)
    assert len(got_bytes) == len(golden), f"length {len(got_bytes)} != {len(golden)}"
    assert not mism, f"{len(mism)} byte mismatches, first at {mism[0]}"
    assert lmon.last_seen and not lmon.keeps_bad, "m_l TLAST/TKEEP protocol"
    assert sprobe.beats == vec["n_symbols"] and sprobe.tlast_count == 1 and not sprobe.bad_type
    assert hc["symbols"] == vec["n_symbols"] and mc["symbols_in"] == vec["n_symbols"]
    assert mc["bytes_out"] == len(golden)
    # cross-check with the cocotbext sink's own (tkeep-compacted) frame
    frame = l_sink.recv_nowait()
    assert bytes(frame.tdata) == golden, "cocotbext sink frame != golden"
    log(f"[{tag}] PASS: {len(got_bytes)} bytes byte-exact vs golden L-vector")


@cocotb.test()
async def chain_full_benchmark(dut):
    await run_chain(dut, backpressure=False)


@cocotb.test()
async def chain_full_benchmark_backpressure(dut):
    await run_chain(dut, backpressure=True, seed=20260919)
