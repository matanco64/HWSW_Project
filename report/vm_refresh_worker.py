"""Linux worker for the canonical course-VM measurement run.

Timing goes through `tools/vm_run_all.sh` -- the stage scripts the README
documents -- with every timed run pinned to one guest CPU. This worker used to
time pyflate itself, with its own pyperf invocations and an extension selected
through PYTHONPATH, while the README documented the scripts: two routes to one
headline, and a reader following the documented one could not reproduce the
quoted protocol. Now there is one route, and the worker adds only the evidence
the scripts do not produce:

  * crate tests, a Python API test and a dispatch check against a fresh
    `cargo build` of pyflate, before anything is installed
  * the wheels the suite built and installed, with their provenance records,
    copied beside the results so they can be committed
  * timing distributions for every JSON, and `tools/check_all.sh --require-native`
    against the installed wheels
  * optionally, the matched CPU counters

    python3 report/vm_refresh_worker.py [--benches nbody pyflate] [--cpu N]
                                        [--out DIR] [--counters]
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
TIMED_STAGES = 'baseline optimized compare wheel native'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, name, env, out):
    print('RUN', name, flush=True)
    log_path = out / (name + '.log')
    with log_path.open('w') as log:
        subprocess.run([str(x) for x in command], cwd=ROOT, env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    print(log_path.read_text()[-1800:], flush=True)


def revision():
    marker = ROOT / 'REVISION'
    if marker.exists():
        return marker.read_text().strip()
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                       text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return 'unknown'


def crate_sources(bench):
    crate = ROOT / 'rust' / bench
    return {str(p.relative_to(ROOT)): sha256(p) for p in sorted(crate.rglob('*'))
            if p.is_file() and not {'target', 'wheels'} & set(p.relative_to(crate).parts)}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--benches', nargs='+', default=['nbody', 'pyflate'],
                    choices=['nbody', 'pyflate'])
    ap.add_argument('--cpu', type=int, help='guest CPU for timed runs '
                    '(default: lowest CPU this process may use)')
    ap.add_argument('--out', type=Path, help='default: results/runs/release_<UTC stamp>')
    ap.add_argument('--counters', action='store_true',
                    help='also collect the matched Python/native CPU counters')
    args = ap.parse_args()

    cpu = args.cpu if args.cpu is not None else min(os.sched_getaffinity(0))
    out = args.out or ROOT / 'results' / 'runs' / time.strftime(
        'release_%Y%m%d_%H%M%S', time.gmtime())
    out.mkdir(parents=True)

    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', LC_ALL='C',
               PYO3_PYTHON=sys.executable)
    env.pop('PYTHONPATH', None)       # nothing but the installed wheels may answer
    home = Path.home()
    env['PATH'] = os.pathsep.join([str(home / '.cargo/bin'), str(home / '.local/bin'),
                                   env['PATH']])

    import pyperformance
    stock_root = Path(pyperformance.__file__).parent / 'data-files' / 'benchmarks'

    def tool(*cmd):
        return subprocess.check_output(cmd, env=env, text=True).strip()

    protocol = dict(
        revision=revision(), python=sys.version, cpu=cpu, benches=args.benches,
        source_sha256={k: v for b in args.benches for k, v in crate_sources(b).items()},
        benchmark_sha256={b: sha256(ROOT / 'benchmarks' / ('bm_' + b) / 'run_benchmark.py')
                          for b in args.benches},
        stock_sha256={b: sha256(stock_root / ('bm_' + b) / 'run_benchmark.py')
                      for b in args.benches},
        rustc=tool('rustc', '--version'), cargo=tool('cargo', '--version'),
        protocol=('Timing through tools/vm_run_all.sh (stages: %s); rigorous pyperf; '
                  'every timed run pinned to guest CPU %d; wheels built from this '
                  'revision and installed system-wide by tools/build_wheel.sh; '
                  'backend, request and CPU affinity asserted on every JSON.'
                  % (TIMED_STAGES, cpu)))

    def save_protocol():
        (out / 'protocol.json').write_text(json.dumps(protocol, indent=2))

    save_protocol()

    # Crate-level evidence against a fresh cargo build, before anything is installed.
    if 'pyflate' in args.benches:
        crate = ROOT / 'rust' / 'pyflate'
        manifest = crate / 'Cargo.toml'
        run(['cargo', 'test', '--locked', '--manifest-path', manifest, '--test', 'kernel'],
            'rust_tests', env, out)
        run(['cargo', 'build', '--locked', '--release', '--manifest-path', manifest],
            'rust_build', env, out)
        extension = crate / 'target' / 'release' / 'libpyflate_rs.so'
        cargo_dir = out / 'cargo_build'
        cargo_dir.mkdir()
        shutil.copyfile(extension, cargo_dir / 'pyflate_rs.so')
        protocol['cargo_extension_sha256'] = sha256(extension)
        save_protocol()
        isolated = dict(env, PYTHONPATH=str(cargo_dir))
        run([sys.executable, crate / 'tests' / 'python_api.py', extension],
            'python_api', isolated, out)
        run([sys.executable, ROOT / 'report' / 'check_pyflate_backend.py', ROOT],
            'dispatch', isolated, out)

    # Timing: the documented route, not a private one.
    suite = out / 'suite'
    run([ROOT / 'tools' / 'vm_run_all.sh', *args.benches], 'suite',
        dict(env, HWSW_RESULTS=str(suite), HWSW_CPU=str(cpu), STAGES=TIMED_STAGES), out)

    wheels = out / 'wheels'
    wheels.mkdir()
    protocol['installed_extension_sha256'] = {}
    for b in args.benches:
        record = json.loads((suite / ('wheel_%s.json' % b)).read_text())
        shutil.copy2(record['wheel'], wheels / Path(record['wheel']).name)
        shutil.copy2(suite / ('wheel_%s.json' % b), wheels / ('%s_rs.provenance.json' % b))
        protocol['installed_extension_sha256'][b] = record['loaded_sha256']
    save_protocol()

    jsons = [suite / ('%s_%s.json' % (tag, b))
             for b in args.benches for tag in ('baseline', 'optimized', 'fallback', 'native')]
    run([sys.executable, ROOT / 'report' / 'summarize_distribution.py',
         '--json', out / 'timing_distributions.json', *jsons],
        'timing_distributions', env, out)

    run([ROOT / 'tools' / 'check_all.sh', '--require-native'], 'check_all', env, out)

    if args.counters:
        run([sys.executable, ROOT / 'report' / 'measure_native_counters.py', '--repo', ROOT,
             '--out', out / 'counters', '--cpu', cpu], 'counters', env, out)

    (out / 'complete.json').write_text(json.dumps(
        {'complete': True, 'revision': protocol['revision']}))
    print('RELEASE_CHECK_COMPLETE', out, flush=True)


if __name__ == '__main__':
    main()
