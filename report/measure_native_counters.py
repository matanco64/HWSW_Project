"""Linux VM: matched-work Python/native counters, gated after warmup.

Run this file from any directory with --repo pointing at the project. All raw
perf output and worker metadata go to a NEW output directory. No saved result
or benchmark source is overwritten. perf's acknowledged FIFO control excludes
imports, initialization and warmup. Counts include the small enable/disable
handshake boundary. Four user-mode events per pass avoid vPMU oversubscription.
"""
import argparse
import gc
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import struct
import subprocess
import sys
import tempfile
import time

PASSES = {
    'core': 'cycles:u,instructions:u,branches:u,branch-misses:u',
    'cache': 'cache-references:u,cache-misses:u,L1-dcache-loads:u,L1-dcache-load-misses:u',
}


def worker(args):
    os.environ['HWSW_BACKEND'] = args.backend
    os.sched_setaffinity(0, {args.cpu})
    source = args.repo / 'benchmarks' / ('bm_' + args.benchmark) / 'run_benchmark.py'
    spec = importlib.util.spec_from_file_location('bench_under_test', source)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    if args.benchmark == 'nbody':
        initial = [(list(r), list(v), mass) for r, v, mass in m.SYSTEM]

        def prepare():
            if args.backend == 'native':
                system = m.nbody_rs.System(initial)
                system.offset_momentum(list(m.BODIES).index(m.DEFAULT_REFERENCE))

                def work():
                    system.energy()
                    system.advance(0.01, 20000)
                    system.energy()

                def state():
                    pos, vel, mass = system.state()
                    return [x for i in range(len(mass))
                            for x in (*pos[3*i:3*i+3], *vel[3*i:3*i+3], mass[i])]
            else:
                for dst, src in zip(m.SYSTEM, initial):
                    dst[0][:], dst[1][:] = src[0], src[1]
                m.offset_momentum(m.BODIES[m.DEFAULT_REFERENCE])

                def work():
                    m.report_energy()
                    m.advance(0.01, 20000)
                    m.report_energy()

                def state():
                    return [x for r, v, mass in m.SYSTEM for x in (*r, *v, mass)]
            return work, state

        warm, _ = prepare()
        warm()
        work, state = prepare()

        def digest():
            values = state()
            return hashlib.sha256(struct.pack('<' + 'd' * len(values), *values)).hexdigest()
    else:
        fp = open(source.parent / 'data' / 'interpreter.tar.bz2', 'rb')
        output = None

        def work():
            nonlocal output
            fp.seek(0)
            field = m.RBitfield(fp)
            assert field.readbits(16) == 0x425a
            output = m.bzip2_main(field)

        work()

        def digest():
            assert hashlib.md5(output).hexdigest() == 'afa004a630fe072901b1d9628b960974'
            return hashlib.sha256(output).hexdigest()

    gc.collect()
    control = os.open(args.ctl, os.O_WRONLY)
    ack = os.open(args.ack, os.O_RDONLY | os.O_NONBLOCK)

    def gate(command):
        os.write(control, (command + '\n').encode())
        if not select.select([ack], [], [], 15)[0]:
            raise RuntimeError('perf control acknowledgement timed out')
        reply = os.read(ack, 4096)
        if b'ack' not in reply:
            raise RuntimeError(f'Unexpected perf acknowledgement: {reply!r}')

    gate('enable')
    start = time.perf_counter()
    for _ in range(args.loops):
        work()
    elapsed = time.perf_counter() - start
    gate('disable')
    print(json.dumps(dict(benchmark=args.benchmark, backend=args.backend,
                          loops=args.loops, cpu=args.cpu, elapsed_s=elapsed,
                          ms_per_iteration=elapsed * 1000 / args.loops,
                          output_sha256=digest(), python=sys.version,
                          source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--rounds', type=int, default=3)
    ap.add_argument('--cpu', type=int, default=min(os.sched_getaffinity(0)))
    ap.add_argument('--perf', default='/usr/lib/linux-kvm-tools-5.15.0-1106/perf')
    ap.add_argument('--worker', action='store_true')
    ap.add_argument('--benchmark', choices=['nbody', 'pyflate'])
    ap.add_argument('--backend', choices=['python', 'native'])
    ap.add_argument('--loops', type=int)
    ap.add_argument('--ctl')
    ap.add_argument('--ack')
    args = ap.parse_args()
    if args.worker:
        worker(args)
        return
    args.out.mkdir(parents=True, exist_ok=False)
    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (args.out / 'protocol.json').write_text(json.dumps(dict(
        rounds=args.rounds, cpu=args.cpu, passes=PASSES, script_sha256=script_hash,
        perf=subprocess.check_output([args.perf, '--version'], text=True).strip(),
        scope='warm measured loop, acknowledged enable/disable, user-mode events',
        loops=dict(nbody=64, pyflate=16)), indent=2))
    for run in range(args.rounds):
        for benchmark, loops in [('nbody', 64), ('pyflate', 16)]:
            for part, events in PASSES.items():
                order = ['python', 'native'] if run % 2 == 0 else ['native', 'python']
                for backend in order:
                    name = f'{benchmark}_{backend}_{part}_{run+1}'
                    with tempfile.TemporaryDirectory(prefix='hwsw-counter-control-') as tmp:
                        ctl, ack = Path(tmp) / 'ctl', Path(tmp) / 'ack'
                        os.mkfifo(ctl)
                        os.mkfifo(ack)
                        keep = [os.open(p, os.O_RDWR | os.O_NONBLOCK) for p in (ctl, ack)]
                        command = [args.perf, 'stat', '-x', ';', '--no-big-num',
                                   '--delay=-1', '--control', f'fifo:{ctl},{ack}',
                                   '-e', events, '-o', str(args.out / (name + '.perf.csv')),
                                   '--', sys.executable, str(Path(__file__).resolve()),
                                   '--worker', '--repo', str(args.repo), '--benchmark', benchmark,
                                   '--backend', backend, '--loops', str(loops), '--cpu', str(args.cpu),
                                   '--ctl', str(ctl), '--ack', str(ack)]
                        try:
                            result = subprocess.run(command, text=True, capture_output=True,
                                                    timeout=180, env={**os.environ,
                                                    'PYTHONDONTWRITEBYTECODE': '1', 'LC_ALL': 'C'})
                        finally:
                            for fd in keep:
                                os.close(fd)
                        (args.out / (name + '.stdout')).write_text(result.stdout)
                        (args.out / (name + '.stderr')).write_text(result.stderr)
                        if result.returncode:
                            raise RuntimeError(f'{name}: {result.stderr}')
                        metadata = json.loads(result.stdout)
                        (args.out / (name + '.json')).write_text(json.dumps(metadata, indent=2))
                        print(f'{name}: {metadata["ms_per_iteration"]:.3f} ms/iter', flush=True)
    print('COUNTER_RUN_COMPLETE', flush=True)


if __name__ == '__main__':
    main()
