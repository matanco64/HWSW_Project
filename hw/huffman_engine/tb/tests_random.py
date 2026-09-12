"""Constrained-random pyuvm tests for huffman_engine (dv_coverage stage).

HuffRandomTest: 16 back-to-back randomized invocations in one test — random
Kraft-complete tables (rand_tables.make_tables), random symbol streams with selector
switching, random START_BIT (0 / mod-32 / odd), random m_sym backpressure and random
bits/sel source gaps. HuffRandomBusyTest: one long backpressured run with mid-run
config writes and a second doorbell while BUSY. All correctness assertion lives in the
scoreboard (env.py v2); the sequences only drive legal stimulus and poll.

Seeding: SEED env var (default 1) — every random decision, including the pause
generators, derives from it."""
import os
import random

import cocotb
from pyuvm import uvm_root

from env import cov
from rand_tables import RandBusySeq, RandCfgSeq, make_stream, make_tables
from test_huffman_engine import HuffBaseTest

# first 7 invocations sweep every alphabet coverage bin deterministically
ALPHABETS = [288, 147, 50, 8, 3, 4, 5]


def _rand_pause(seed, p_pause):
    """Infinite seeded pause generator for cocotbext set_pause_generator."""
    rng = random.Random(seed)
    while True:
        yield rng.random() < p_pause


def _heavy_pause():
    """Deterministic ~5%-ready sink: stretches a decode ~20x so mid-run register abuse
    is guaranteed to land while BUSY."""
    n = 0
    while True:
        yield (n % 20) != 0
        n += 1


class HuffRandomTest(HuffBaseTest):
    """>= 15 randomized invocations back-to-back (testplan cg_cfg/cg_sel/cg_bits/cg_bp):
    n_tables sweeps 1..6 (incl. the required 6), alphabet sweeps {288,147,50,8,3,4,5}
    (incl. the required 288), n_symbols 60..400 (always >= 51: selector switches),
    START_BIT in {0, 32, 8844%64, random 1..199} with the filler bits packed into the
    stream by make_stream."""

    N_INV = 16

    async def main(self):
        seed = int(os.environ.get("SEED", "1"))
        rng = random.Random(seed)
        for i in range(self.N_INV):
            n_tables = (i % 6) + 1
            alphabet = ALPHABETS[i] if i < len(ALPHABETS) else rng.choice(ALPHABETS)
            n_symbols = rng.randrange(60, 401)
            if i == 2:
                start_bit = 32                       # mod-32 bin
            elif i == 3:
                start_bit = 8844 % 64                # 12: the bench block's odd class
            elif i == 4:
                start_bit = rng.randrange(1, 200)
            else:
                start_bit = rng.choice([0, 0, 0, 32, rng.randrange(1, 200)])
            tables = make_tables(rng, n_tables, alphabet)
            n_groups = (n_symbols + 49) // 50
            sels = [rng.randrange(n_tables) for _ in range(n_groups)]
            stream, sels = make_stream(rng, tables, sels, alphabet, n_symbols,
                                       start_bit=start_bit)

            # backpressure schedule: none / m_sym pauses / source gaps / (last) both
            sym_bp = i % 3 == 1 or i == self.N_INV - 1
            src_gap = i % 3 == 2 or i == self.N_INV - 1
            if sym_bp:
                self.env.sym_sink.set_pause_generator(
                    _rand_pause(rng.randrange(1 << 30), 0.5))
            else:
                self.env.sym_sink.set_pause_generator(None)
                self.env.sym_sink.pause = False      # unlatch a killed generator
            for src in (self.env.bits_source, self.env.sel_source):
                if src_gap:
                    src.set_pause_generator(_rand_pause(rng.randrange(1 << 30), 0.3))
                else:
                    src.set_pause_generator(None)
                    src.pause = False

            # tready is 0 until the doorbell's PREP: flush leftovers, queue the new
            # frames first, then run the sequence (frames park until accepted)
            self.env.flush_sources()
            await self.queue_streams(stream, bytes(sels))
            seq = RandCfgSeq(f"rand{i}", cfg=dict(
                alphabet=alphabet, n_tables=n_tables, lengths=tables,
                start_bit=start_bit))
            await seq.start(self.env.agent.sequencer)

            switches = sum(1 for a, b in zip(sels, sels[1:]) if a != b)
            cov("cg_sel", f"switches.{'none' if switches == 0 else 'few' if switches <= 3 else 'many'}")
            cov("cg_sel", f"groups.{'2_4' if n_groups <= 4 else '5_8'}")
            cov("cg_bp", "sym.pause" if sym_bp else "sym.free")
            cov("cg_bp", "src.gaps" if src_gap else "src.free")
            self.logger.info(
                f"rand[{i}] alphabet={alphabet} n_tables={n_tables} "
                f"n_symbols={n_symbols} start_bit={start_bit} switches={switches} "
                f"sym_bp={sym_bp} src_gap={src_gap} counters={seq.counters}")
        # leave the sink free for any later phase activity
        self.env.sym_sink.set_pause_generator(None)
        self.env.sym_sink.pause = False


@cocotb.test()
async def random_cfg(_dut):
    await uvm_root().run_test("HuffRandomTest")


class HuffRandomBusyTest(HuffBaseTest):
    """One long invocation under a ~5%-ready m_sym sink; mid-run the sequence writes
    config registers while BUSY (must be ignored) and doorbells again while BUSY
    (sticky ERR_BUSY, W1C'd while still BUSY); the run then finishes normally and the
    scoreboard replays it against the original config."""

    async def main(self):
        seed = int(os.environ.get("SEED", "1")) + 4242
        rng = random.Random(seed)
        alphabet, n_tables, n_symbols = 50, 3, 400
        tables = make_tables(rng, n_tables, alphabet)
        sels = [rng.randrange(n_tables) for _ in range((n_symbols + 49) // 50)]
        stream, sels = make_stream(rng, tables, sels, alphabet, n_symbols)
        self.env.sym_sink.set_pause_generator(_heavy_pause())
        self.env.flush_sources()
        await self.queue_streams(stream, bytes(sels))
        seq = RandBusySeq("busy", cfg=dict(alphabet=alphabet, n_tables=n_tables,
                                           lengths=tables), env=self.env)
        await seq.start(self.env.agent.sequencer)
        cov("cg_bp", "sym.heavy")
        self.logger.info(f"busy run counters={seq.counters}")
        self.env.sym_sink.set_pause_generator(None)
        self.env.sym_sink.pause = False


@cocotb.test()
async def random_busy(_dut):
    await uvm_root().run_test("HuffRandomBusyTest")
