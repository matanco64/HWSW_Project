"""Cross-check a built extension without installing or replacing any wheel.

Run from the repository root after `cargo build --release` in rust/pyflate:
    python3 rust/pyflate/tests/python_api.py \
        rust/pyflate/target/release/libpyflate_rs.so

An explicit extension path ensures this tests the new build, not an older
installed wheel. All fixtures are deterministic; timings are not benchmarks.
"""

import bz2
import hashlib
import importlib.util
from pathlib import Path
import random
import sys
import tempfile


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: python_api.py PATH_TO_EXTENSION")
    extension = Path(sys.argv[1]).resolve()
    spec = importlib.util.spec_from_file_location("pyflate_rs", extension)
    native = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = native
    spec.loader.exec_module(native)

    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / "dev" / "pyflate"))
    import rs_check as reference

    raw = Path(reference.DATA).read_bytes()
    fixtures = {
        "course input": raw,
        "single-symbol runs": bz2.compress(b"a" * 10000),
        "all byte values": bz2.compress(bytes(range(256)) * 100),
        "mixed runs": bz2.compress(b"a" * 500 + b"bc" * 301 + b"d" * 1000),
        "multiple blocks": bz2.compress(random.Random(882).randbytes(220000), compresslevel=1),
    }
    nblocks = 0
    with tempfile.TemporaryDirectory(prefix="pyflate-rust-tests-") as temp:
        for name, data in fixtures.items():
            expected = bz2.decompress(data)
            blocks = reference.parse_blocks(data)
            if name == "multiple blocks":
                assert len(blocks) > 1
            for i, block in enumerate(blocks):
                args = (
                    data,
                    [bytes(lengths) for lengths in block["code_lengths"]],
                    bytes(block["selectors"]),
                    block["symbols_in_use"],
                    bytes(block["favourites"]),
                )
                decoder = native.BlockDecoder(*args)
                want = block["L"], block["end"]
                assert decoder.decode(block["start"]) == want
                assert decoder.decode(block["start"]) == want, "decoder must be reusable"
                assert native.decode_block(args[0], block["start"], *args[1:]) == want
                assert decoder.num_groups == len(block["code_lengths"])
                assert decoder.primary_bits == native.PRIMARY_BITS == 11
                assert len(decoder.group_tables()) == decoder.num_groups
                assert repr(decoder).startswith("BlockDecoder(groups=")
                trace = str(Path(temp) / f"block-{i}.pft")
                nsym, nout, end = decoder.trace(block["start"], trace)
                ok, info = reference.check_trace(trace, block, block["L"])
                assert ok and nsym == info["n_sym"] and nout == len(block["L"])
                assert end == block["end"]
                nblocks += 1
            assert reference.hybrid_decompress(data) == expected
            assert reference.py_decompress(data) == expected
            print(f"PASS {name}: {len(blocks)} blocks, {len(expected)} output bytes")

    try:
        native.BlockDecoder(b"", [b"\x01\x01\x01"] * 2, b"\x00", 3, b"a")
    except ValueError as error:
        assert "oversubscribed" in str(error)
    else:
        raise AssertionError("oversubscribed tables must raise ValueError")

    assert hashlib.md5(bz2.decompress(raw)).hexdigest() == reference.MD5
    print(f"PASS Python API, kernel/end-bit parity, trace and pipeline: {nblocks} blocks")
    print(f"Tested extension: {extension}")


if __name__ == "__main__":
    main()
