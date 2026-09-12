"""test_driver.py — huffman_engine driver model tests (stage 10, hw-integrate).

Run: `make -C hw/huffman_engine sim TESTCASE=test_driver` (cocotb picks up the
`test_*` cocotb tests) OR standalone:
    python3 hw/huffman_engine/driver/test_driver.py

Standalone mode exercises the driver against the `ModelBus` (no RTL): register
map consistency, ID round-trip, cycle-model equivalence to the signed-off
`docs/decode_model.py`, a full `decode_block` invocation (golden-decoded sink),
and the ERR_PARAM reject path.
"""
import os
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "golden"))
sys.path.insert(0, str(HERE.parent / "docs"))

import huffman_engine_driver as drv  # noqa: E402
from huffman_engine_driver import HuffmanDriver, ModelBus, cycle_model  # noqa: E402


def _canonical_codes(lengths):
    """Canonical Huffman codes (RFC/bzip2 order): by (length, symbol)."""
    order = sorted((l, s) for s, l in enumerate(lengths) if l)
    code = 0
    prev_len = order[0][0]
    out = {}
    for l, s in order:
        code <<= (l - prev_len)
        out[s] = (code, l)
        code += 1
        prev_len = l
    return out


def _pack_msb(bits):
    """List of bits (MSB-first per byte) -> bytes."""
    data = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for b in bits[i:i + 8]:
            byte = (byte << 1) | b
        byte <<= (8 - len(bits[i:i + 8]))
        data.append(byte)
    return bytes(data)


def _encode_bzip2(lengths, symbols):
    codes = _canonical_codes(lengths)
    bits = []
    for s in symbols:
        code, l = codes[s]
        bits.extend((code >> (l - 1 - i)) & 1 for i in range(l))
    return _pack_msb(bits)


def test_regmap():
    import check_regmap
    assert check_regmap.main() == 0, "check_regmap reported differences"
    print("PASS test_regmap: 0 differences vs docs/mas.md §4")


def test_id():
    d = HuffmanDriver(ModelBus())
    assert d._rd(drv.ID) == drv.ID_VALUE == 0x48554631
    print("PASS test_id: ID = 0x%08x ('HUF1')" % drv.ID_VALUE)


def test_cycle_model_matches_signoff():
    import decode_model as DM
    rng = random.Random(1)
    for _ in range(20):
        n = rng.randint(1, 400)
        lengths = [rng.randint(1, 20) for _ in range(n)]
        alphabet = rng.randint(3, 288)
        n_tables = rng.randint(1, 6)
        start_bit = rng.choice([0, 33, 8844])
        a = cycle_model(lengths, alphabet, n_tables, start_bit)
        b = DM.simulate(lengths, alphabet, n_tables, start_bit=start_bit)
        assert a == b, f"cycle_model diverged from decode_model: {a} != {b}"
    print("PASS test_cycle_model_matches_signoff: driver cycle model == docs/decode_model.py (20 cases)")


def test_decode_block():
    # 4-symbol, single-table bzip2 scenario: all length 2, EOB = 3.
    lengths = [2, 2, 2, 2]
    symbols = [0, 1, 2, 0, 3]          # last is EOB (symbols_in_use - 1)
    data = _encode_bzip2(lengths, symbols)
    d = HuffmanDriver(ModelBus())
    sink, bits = d.decode_block(data, 0, [lengths], selectors=[0],
                                mode=HuffmanDriver.MODE_BZIP2)
    assert sink == symbols, f"sink {sink} != {symbols}"
    assert d.status() & drv.ST_BUSY == 0
    exp = cycle_model([lengths[s] for s in symbols], 4, 1, 0)
    assert d.bus.cycles == exp["cycles"], f"cycles {d.bus.cycles} != {exp['cycles']}"
    assert bits == sum(lengths[s] for s in symbols)
    print(f"PASS test_decode_block: decoded {len(sink)} symbols, "
          f"cycles={d.bus.cycles}, bits={bits} (sink matches golden)")


def test_err_param():
    d = HuffmanDriver(ModelBus())
    # SYMBOL_LIMIT = 0 is rejected (MAS 0x110), and N_TABLES = 7 > 6.
    d.configure(HuffmanDriver.MODE_BZIP2, 0, alphabet=147, n_tables=7, symbol_limit=0)
    ok = d.start()
    assert not ok, "doorbell should be rejected"
    assert d.status() & drv.ST_ERR_PARAM, "ERR_PARAM expected"
    print("PASS test_err_param: doorbell rejected, ERR_PARAM set")


TESTS = [test_regmap, test_id, test_cycle_model_matches_signoff,
         test_decode_block, test_err_param]


def main():
    for t in TESTS:
        t()
    print(f"\nALL {len(TESTS)} DRIVER TESTS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
