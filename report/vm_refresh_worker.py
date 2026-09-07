"""Linux worker: build the current pyflate crate and collect matched VM evidence."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'results'


def run(command, name, env):
    print('RUN', name, flush=True)
    with (OUT / (name + '.log')).open('w') as log:
        subprocess.run([str(x) for x in command], cwd=ROOT, env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    print((OUT / (name + '.log')).read_text()[-1800:], flush=True)


def main():
    OUT.mkdir()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', LC_ALL='C',
               PYO3_PYTHON=sys.executable)
    env['PATH'] = str(Path.home() / '.cargo/bin') + os.pathsep + env['PATH']
    crate = ROOT / 'rust/pyflate'
    source_paths = sorted(p for p in crate.rglob('*') if p.is_file())
    protocol = dict(python=sys.version, cpu=min(os.sched_getaffinity(0)),
                    source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in source_paths},
                    benchmark_sha256={name: hashlib.sha256((ROOT / 'benchmarks' / ('bm_' + name) /
                                        'run_benchmark.py').read_bytes()).hexdigest()
                                      for name in ('nbody', 'pyflate')},
                    rustc=subprocess.check_output(['rustc', '--version'], env=env, text=True).strip(),
                    cargo=subprocess.check_output(['cargo', '--version'], env=env, text=True).strip(),
                    protocol='Sequential rigorous jobs; fixed guest CPU; explicit backend and inherited PYTHONPATH')
    (OUT / 'protocol.json').write_text(json.dumps(protocol, indent=2))
    manifest = crate / 'Cargo.toml'
    run(['cargo', 'test', '--locked', '--manifest-path', manifest, '--test', 'kernel'], 'rust_tests', env)
    run(['cargo', 'build', '--locked', '--release', '--manifest-path', manifest], 'rust_build', env)
    extension = crate / 'target/release/libpyflate_rs.so'
    native_dir = ROOT / 'native'
    native_dir.mkdir()
    shutil.copyfile(extension, native_dir / 'pyflate_rs.so')
    env['PYTHONPATH'] = str(native_dir)
    protocol['extension_sha256'] = hashlib.sha256(extension.read_bytes()).hexdigest()
    protocol['extension_file'] = 'native/pyflate_rs.so'
    (OUT / 'protocol.json').write_text(json.dumps(protocol, indent=2))
    run([sys.executable, crate / 'tests/python_api.py', extension], 'python_api', env)
    run([sys.executable, ROOT / 'report/check_pyflate_backend.py', ROOT], 'dispatch', env)

    import pyperformance
    stock = Path(pyperformance.__file__).parent / 'data-files/benchmarks/bm_pyflate/run_benchmark.py'
    assert stock.is_file(), stock
    protocol['stock_sha256'] = hashlib.sha256(stock.read_bytes()).hexdigest()
    (OUT / 'protocol.json').write_text(json.dumps(protocol, indent=2))
    for tag, source, backend in [
        ('pyflate_stock', stock, 'python'),
        ('pyflate_python', ROOT / 'benchmarks/bm_pyflate/run_benchmark.py', 'python'),
        ('pyflate_native', ROOT / 'benchmarks/bm_pyflate/run_benchmark.py', 'native'),
    ]:
        run([sys.executable, source, '--rigorous', '--affinity', protocol['cpu'],
             '--inherit-environ', 'HWSW_BACKEND,PYTHONPATH', '-o', OUT / (tag + '.json')],
            tag, dict(env, HWSW_BACKEND=backend))

    for a, b, tag in [('pyflate_stock', 'pyflate_python', 'stock_vs_python'),
                      ('pyflate_python', 'pyflate_native', 'python_vs_native'),
                      ('pyflate_stock', 'pyflate_native', 'stock_vs_native')]:
        run([sys.executable, '-m', 'pyperf', 'compare_to', OUT / (a + '.json'),
             OUT / (b + '.json'), '--table'], tag, env)
    run([sys.executable, ROOT / 'report/measure_native_counters.py', '--repo', ROOT,
         '--out', OUT / 'counters', '--cpu', protocol['cpu']], 'counters', env)
    (OUT / 'complete.json').write_text(json.dumps({'complete': True}))
    print('RELEASE_CHECK_COMPLETE', flush=True)


if __name__ == '__main__':
    main()
