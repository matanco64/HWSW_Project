"""Validate backend/sample metadata and summarize preserved rigorous VM runs."""
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parent.parent


def summarize(path, expected_backend):
    data = json.loads(path.read_text())
    assert len(data['benchmarks']) == 1
    bench = data['benchmarks'][0]
    runs = [r for r in bench['runs'] if r.get('values')]
    values = [v for run in runs for v in run['values']]
    metadata = {**data.get('metadata', {}), **bench.get('metadata', {})}
    for run in runs:
        actual = {**metadata, **run.get('metadata', {})}.get('hwsw_backend')
        if expected_backend is not None:
            assert actual == expected_backend, (path, actual)
    assert len(values) == 120 and len(runs) == 40, (path, len(values), len(runs))
    return dict(values=len(values), workers=len(runs),
                mean_ms=statistics.mean(values)*1000,
                sd_ms=statistics.stdev(values)*1000,
                relative_sd_pct=statistics.stdev(values)/statistics.mean(values)*100,
                backend=metadata.get('hwsw_backend', 'stock (no backend switch)'),
                python=metadata.get('python_version'),
                affinity=metadata.get('cpu_affinity'),
                file_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    earlier = ROOT / 'results/vm_rerun_20260907'
    release = ROOT / 'results/vm_release_20260907'
    for directory in (earlier, release):
        if not directory.exists():
            continue
        prefix = 'fresh2_' if directory == earlier else ''
        output = {}
        names = [('nbody_python', 'python'), ('nbody_native', 'native'),
                 ('pyflate_python', 'python'), ('pyflate_native', 'native')]
        if directory == release:
            names = [('pyflate_stock', None), *names[2:]]
            protocol = json.loads((directory / 'protocol.json').read_text())
            for name, digest in protocol['source_sha256'].items():
                # Narrative docs may be updated after measuring; code, tests,
                # dependency lock and build settings must match the capture.
                if not name.endswith('.md'):
                    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
            for name, digest in protocol['benchmark_sha256'].items():
                assert hashlib.sha256((ROOT / 'benchmarks' / ('bm_' + name) /
                                      'run_benchmark.py').read_bytes()).hexdigest() == digest
            assert 'PASS Python API' in (directory / 'python_api.log').read_text()
            dispatch = [json.loads(line) for line in (directory / 'dispatch.log').read_text().splitlines()]
            assert [item['native_calls'] for item in dispatch] == [0, 1, 1]
            assert all(item['extension'].endswith('/native/pyflate_rs.so') for item in dispatch[1:])
        for name, backend in names:
            output[name] = summarize(directory / (prefix + name + '.json'), backend)
        (directory / 'summary.json').write_text(json.dumps(output, indent=2) + '\n')
        print(directory.name, json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
