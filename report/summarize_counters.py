"""Import the VM's base64 tar stream, validate it, and summarize raw perf data."""
import argparse
import base64
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import statistics
import sys
import tarfile

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / 'results' / 'native_counters_20260907'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--import-base64', action='store_true')
    ap.add_argument('--directory', type=Path, default=DEST,
                    help='Capture directory (a new directory when importing)')
    args = ap.parse_args()
    dest = args.directory.resolve()
    if args.import_base64:
        archive = tarfile.open(fileobj=io.BytesIO(base64.b64decode(sys.stdin.read())), mode='r:gz')
        members = [m for m in archive.getmembers() if m.isfile()]
        pending = []
        for member in members:
            rel = PurePosixPath(member.name)
            if rel.is_absolute() or '..' in rel.parts or member.issym() or member.islnk():
                raise ValueError('Unsafe archive member')
            name = rel.name
            if rel.parts[0] != 'results' and name != 'run.log':
                raise ValueError(f'Unexpected archive member {member.name}')
            target = dest / name
            if target.exists():
                raise FileExistsError(target)
            pending.append((target, archive.extractfile(member).read()))
        dest.mkdir(parents=True, exist_ok=False)
        for target, data in pending:
            target.write_bytes(data)
    output = {'protocol': json.loads((dest / 'protocol.json').read_text()), 'benchmarks': {},
              'excluded_events': {}, 'scope_note': 'L1 load denominator is zero in this capture; '
              'exclude both L1 events. Retain independently valid core and generic cache events.'}
    for benchmark in ['nbody', 'pyflate']:
        output['benchmarks'][benchmark] = {}
        digests = set()
        source = ROOT / 'benchmarks' / ('bm_' + benchmark) / 'run_benchmark.py'
        expected_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        for backend in ['python', 'native']:
            runs = []
            for run in range(1, output['protocol']['rounds'] + 1):
                metrics = {}
                for part in ['core', 'cache']:
                    stem = f'{benchmark}_{backend}_{part}_{run}'
                    metadata = json.loads((dest / (stem + '.json')).read_text())
                    assert metadata['source_sha256'] == expected_hash
                    assert metadata['backend'] == backend
                    assert metadata['benchmark'] == benchmark
                    assert metadata['loops'] == output['protocol']['loops'][benchmark]
                    assert metadata['cpu'] == output['protocol']['cpu']
                    digests.add(metadata['output_sha256'])
                    metrics[part + '_ms'] = metadata['ms_per_iteration']
                    for line in (dest / (stem + '.perf.csv')).read_text().splitlines():
                        if not line or line.startswith('#'):
                            continue
                        cells = line.split(';')
                        if len(cells) < 5 or not cells[2]:
                            continue
                        if cells[2].startswith('L1-dcache-'):
                            output['excluded_events'].setdefault(stem, []).append(line)
                            continue
                        value = float(cells[0])
                        running = float(cells[4])
                        if not math.isfinite(value) or value < 0 or not 99.9 <= running <= 100.0:
                            raise ValueError(f'Invalid or multiplexed counter: {stem}: {line}')
                        metrics[cells[2]] = value / metadata['loops']
                for event in ('instructions:u', 'cycles:u', 'branches:u', 'cache-references:u'):
                    if metrics[event] <= 0:
                        raise ValueError(f'Invalid denominator {event}: {benchmark}/{backend}/{run}')
                metrics['ipc'] = metrics['instructions:u'] / metrics['cycles:u']
                metrics['branch_miss_pct'] = 100 * metrics['branch-misses:u'] / metrics['branches:u']
                metrics['cache_miss_pct'] = 100 * metrics['cache-misses:u'] / metrics['cache-references:u']
                runs.append(metrics)
            output['benchmarks'][benchmark][backend] = {
                'median': {key: statistics.median(r[key] for r in runs) for key in runs[0]},
                'min': {key: min(r[key] for r in runs) for key in runs[0]},
                'max': {key: max(r[key] for r in runs) for key in runs[0]},
                'runs': runs,
            }
        if len(digests) != 1:
            raise ValueError(f'Python/native final-output digest mismatch for {benchmark}: {digests}')
        output['benchmarks'][benchmark]['output_sha256'] = digests.pop()
    if not output['excluded_events']:
        output['scope_note'] = 'Core and generic cache events; no L1 events reported.'
    (dest / 'summary.json').write_text(json.dumps(output, indent=2) + '\n')
    for benchmark, configs in output['benchmarks'].items():
        print(benchmark)
        for backend in ['python', 'native']:
            m = configs[backend]['median']
            print(backend, json.dumps(m))
    count = 8 * output['protocol']['rounds']
    print(f'Validated all {count} runs: source hashes, requested backend, output equality, '
          'loop counts, CPU selection and retained events running >=99.9%. No L1 claim is supported.')


if __name__ == '__main__':
    main()
