"""Trace real decoder dispatch without changing benchmark source or timing data."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

repo = Path(sys.argv[1]).resolve()
source = repo / 'benchmarks/bm_pyflate/run_benchmark.py'
for backend in ('python', 'native', 'auto'):
    os.environ['HWSW_BACKEND'] = backend
    spec = importlib.util.spec_from_file_location('checked_pyflate', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []
    original = module._decode_symbols_native

    def traced(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    module._decode_symbols_native = traced
    with (source.parent / 'data/interpreter.tar.bz2').open('rb') as stream:
        field = module.RBitfield(stream)
        assert field.readbits(16) == 0x425a
        output = module.bzip2_main(field)
    digest = hashlib.md5(output).hexdigest()
    assert digest == 'afa004a630fe072901b1d9628b960974'
    assert len(calls) == (0 if backend == 'python' else 1)
    print(json.dumps(dict(requested_backend=backend, native_calls=len(calls),
                         output_md5=digest, output_bytes=len(output),
                         source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                         extension=module.pyflate_rs.__file__ if module.pyflate_rs else None)))
