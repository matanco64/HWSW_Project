"""test_deflate (F-25, un-gated after the B8 fix): DEFLATE-mode top-level tests.

Streams are RFC 1951 bit-packed (LSB-first per byte; Huffman code bits MSB-of-code first,
extra-bit fields LSB-first) — the TB encoder derives every code from golden
`canonical_model.Table` (never re-derived) and every stream round-trips through
`decode_deflate_symbols` before it is driven. Software presents the byte stream as-is
(the aligner bit-reverses per byte in DEFLATE mode — R23)."""
import zlib

import canonical_model as cm
import cocotb
from cocotbext.axi import AxiStreamFrame
from pyuvm import uvm_root

from env import (ALPHABET, BITS, MODE, N_TABLES, ST_DONE, ST_ESYM, START_BIT, STATUS,
                 SYMBOL_LIMIT, SYMBOLS, STICKY_MASK, ST_ELIMIT)
from smoke import HuffBaseSeq, pack_lengths
from test_huffman_engine import HuffBaseTest

# RFC 1951 §3.2.6 fixed-Huffman code lengths
FIXED_LIT = [8] * 144 + [9] * 112 + [7] * 24 + [8] * 8      # 288 entries
FIXED_DIST = [5] * 30


class _BitPacker:
    """LSB-first-per-byte bit sink (RFC 1951 packing)."""

    def __init__(self):
        self.bits = []

    def code(self, table, lengths, sym):
        """Append sym's canonical code, MSB of the code first (RFC Huffman order)."""
        l = lengths[sym]
        assert l, f"symbol {sym} has no code"
        rank = sum(1 for s in range(sym) if lengths[s] == l)
        c = table.first_code[l] + rank
        for k in range(l - 1, -1, -1):
            self.bits.append((c >> k) & 1)

    def raw(self, value, n):
        """Append an n-bit extra field, LSB first."""
        for k in range(n):
            self.bits.append((value >> k) & 1)

    def bytes(self):
        out = bytearray((len(self.bits) + 7) // 8)
        for i, b in enumerate(self.bits):
            out[i >> 3] |= b << (i & 7)
        return bytes(out)


def deflate_encode(events, lit_lengths, dist_lengths):
    """Encode ('lit',b)/('copy',L,D)/('eob',) events; round-trip-checked by the caller."""
    lit_t = cm.Table(lit_lengths, cm.MAXLEN_DEFLATE)
    dist_t = cm.Table(dist_lengths, cm.MAXLEN_DEFLATE)
    pk = _BitPacker()
    for ev in events:
        if ev[0] == "lit":
            pk.code(lit_t, lit_lengths, ev[1])
        elif ev[0] == "eob":
            pk.code(lit_t, lit_lengths, 256)
        elif ev[0] == "sym":                      # raw lit/len symbol (error injection)
            pk.code(lit_t, lit_lengths, ev[1])
        else:
            _, length, distance = ev
            i = next(k for k in range(29) if cm._LEN_BASE[k] <= length
                     and (k == 28 or cm._LEN_BASE[k + 1] > length))
            pk.code(lit_t, lit_lengths, 257 + i)
            pk.raw(length - cm._LEN_BASE[i], cm._LEN_EXTRA[i])
            d = next(k for k in range(30) if cm._DIST_BASE[k] <= distance
                     and (k == 29 or cm._DIST_BASE[k + 1] > distance))
            pk.code(dist_t, dist_lengths, d)
            pk.raw(distance - cm._DIST_BASE[d], cm._DIST_EXTRA[d])
    return pk.bytes()


class DeflateSeq(HuffBaseSeq):
    def __init__(self, name, lit_lengths, dist_lengths, start_bit=0, limit=1 << 20,
                 outcome=ST_DONE):
        super().__init__(name)
        self.lit = lit_lengths
        self.dist = dist_lengths
        self.start_bit = start_bit
        self.limit = limit
        self.outcome = outcome

    async def body(self):
        await self.wr(MODE, 1)
        await self.wr(START_BIT, self.start_bit)
        await self.wr(ALPHABET, 288)
        await self.wr(N_TABLES, 2)
        await self.wr(SYMBOL_LIMIT, self.limit)
        # lit lengths at stride 0, dist at stride 1 (MAS §4: DEFLATE table 1 = 30 entries)
        for w, val in sorted(pack_lengths([self.lit], 288).items()):
            await self.wr(0x400 + 4 * w, val)
        dist_padded = self.dist + [0] * (288 - len(self.dist))
        for w, val in sorted({48 + i: v for i, v in
                              pack_lengths([dist_padded[:30 + (6 - 30 % 6)]], 36).items()}.items()):
            await self.wr(0x400 + 4 * w, val)
        await self.run_to_done(max_polls=8000, outcome_mask=self.outcome)
        await self.wr(STATUS, STICKY_MASK)          # W1C everything
        await self.rd(SYMBOLS)
        await self.rd(BITS)


class HuffDeflateFixedTest(HuffBaseTest):
    """Fixed-Huffman zlib fragment (ground truth) + a custom-table stream + ERR_SYMBOL
    directed cases + a LIMIT-on-copy case, back-to-back."""

    async def main(self):
        env = self.env
        # 1. zlib fixed-Huffman block (BTYPE=1), body starts at bit 3
        payload = b"ABCDABCDABCDABCD_the_quick_brown_fox" * 3
        co = zlib.compressobj(9, zlib.DEFLATED, -15)
        raw = co.compress(payload) + co.flush()
        b0 = raw[0]
        assert (b0 >> 1) & 3 == 1, "expected a fixed-Huffman block"
        ev, end, _ = cm.decode_deflate_symbols(raw, 3, FIXED_LIT, FIXED_DIST)
        await env.bits_source.send(AxiStreamFrame(raw))
        await DeflateSeq("dfl_fixed", FIXED_LIT, FIXED_DIST, start_bit=3).start(
            env.agent.sequencer)

        # 2. custom tables, TB-encoded stream with copies and big distances
        lit = [0] * 288
        for s, l in [(65, 2), (66, 2), (67, 3), (280, 3), (256, 3)]:
            lit[s] = l
        lit[257 + 20] = 3                            # length code 277 (base 67, 4 extra)
        dist = [0] * 30
        dist[0], dist[20], dist[29] = 1, 2, 2       # distances 1, 1025+ext, 24577+ext
        events = ([("lit", 65), ("lit", 66), ("copy", 70, 1), ("lit", 67),
                   ("copy", 70, 1500), ("copy", 70, 30000), ("eob",)])
        stream = deflate_encode(events, lit, dist)
        chk, _, _ = cm.decode_deflate_symbols(stream, 0, lit, dist)
        assert chk == events, f"encoder round-trip: {chk} != {events}"
        env.flush_sources()
        await env.bits_source.send(AxiStreamFrame(stream))
        await DeflateSeq("dfl_custom", lit, dist).start(env.agent.sequencer)

        # 3. ERR_SYMBOL: reserved lit/len code 286 as the first symbol
        lit286 = list(FIXED_LIT)
        stream = deflate_encode([("sym", 286)], lit286, FIXED_DIST)
        env.flush_sources()
        await env.bits_source.send(AxiStreamFrame(stream + b"\x00\x00"))
        await DeflateSeq("dfl_err286", lit286, FIXED_DIST, outcome=ST_ESYM).start(
            env.agent.sequencer)

        # 4. LIMIT hits on a copy beat (SYMBOL_LIMIT=2: lit, copy | stop)
        events = [("lit", 65), ("copy", 70, 1), ("lit", 66), ("eob",)]
        stream = deflate_encode(events, lit, dist)
        chk, _, _ = cm.decode_deflate_symbols(stream, 0, lit, dist)
        env.flush_sources()
        await env.bits_source.send(AxiStreamFrame(stream))
        await DeflateSeq("dfl_limit", lit, dist, limit=2, outcome=ST_ELIMIT).start(
            env.agent.sequencer)


@cocotb.test()
async def deflate(_dut):
    await uvm_root().run_test("HuffDeflateFixedTest")
