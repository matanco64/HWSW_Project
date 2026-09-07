"""Start, inspect and fetch isolated report measurements over a two-hop SSH relay.

Infrastructure is supplied via CLI, never stored in the report sources. Only
selected project sources are uploaded. Each start creates a new remote temp
directory; the existing checkout and installed wheels are not modified.
"""
import argparse
import base64
import io
from pathlib import Path, PurePosixPath
import shlex
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parent.parent


def remote(args, script):
    inner = shlex.join(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                        '-p', str(args.port), args.guest, 'python3 -'])
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                             args.jump, inner], input=script.encode(),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace'))
    return result.stdout.decode()


def unpack(data, destination):
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(fileobj=io.BytesIO(base64.b64decode(data)), mode='r:gz') as archive:
        for member in archive.getmembers():
            rel = PurePosixPath(member.name)
            if not member.isfile() or rel.is_absolute() or '..' in rel.parts:
                raise ValueError(f'Unsafe member: {member.name}')
            target = destination.joinpath(*rel.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as out:
                out.write(archive.extractfile(member).read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['start', 'status', 'fetch', 'archive-earlier'])
    ap.add_argument('--jump', required=True)
    ap.add_argument('--guest', default='ubuntu@127.0.0.1')
    ap.add_argument('--port', type=int, default=12222)
    ap.add_argument('--remote-directory')
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    if args.action == 'start':
        paths = subprocess.check_output([
            'git', '-c', f'safe.directory={ROOT.as_posix()}', 'ls-files',
            'rust/pyflate', 'dev/pyflate', 'benchmarks/bm_pyflate', 'benchmarks/bm_nbody',
            'report/measure_native_counters.py', 'report/check_pyflate_backend.py'], cwd=ROOT,
            text=True).splitlines()
        paths.append('report/vm_refresh_worker.py')
        payload = io.BytesIO()
        with tarfile.open(fileobj=payload, mode='w:gz') as archive:
            for name in paths:
                if '/wheels/' not in name:
                    archive.add(ROOT / name, arcname=name, recursive=False)
        encoded = base64.b64encode(payload.getvalue()).decode()
        script = f'''import base64, io, pathlib, subprocess, tarfile, tempfile
root = pathlib.Path(tempfile.mkdtemp(prefix="hwsw-release-check-"))
with tarfile.open(fileobj=io.BytesIO(base64.b64decode({encoded!r})), mode="r:gz") as archive:
    for member in archive.getmembers():
        rel = pathlib.PurePosixPath(member.name)
        assert member.isfile() and not rel.is_absolute() and ".." not in rel.parts
        target = root.joinpath(*rel.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.extractfile(member).read())
with (root / "run.log").open("wb") as log:
    process = subprocess.Popen(["python3", str(root / "report/vm_refresh_worker.py")],
        cwd=root, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True)
print(root)
print("pid", process.pid)
'''
        print(remote(args, script))
    elif args.action == 'status':
        script = f'''from pathlib import Path
root = Path({args.remote_directory!r})
print((root / "run.log").read_text()[-1800:])
logs = list((root / "results").glob("*.log"))
if logs:
    latest = max(logs, key=lambda p: p.stat().st_mtime)
    print("Latest:", latest.name)
    print(latest.read_text()[-1200:])
print("complete:", (root / "results/complete.json").exists())
'''
        print(remote(args, script))
    else:
        if args.output is None:
            ap.error('--output is required')
        if args.action == 'archive-earlier':
            script = '''import base64, io, pathlib, tarfile
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz") as archive:
    for name in ("nbody_python", "nbody_native", "pyflate_python", "pyflate_native"):
        path = pathlib.Path("/tmp/fresh2_" + name + ".json")
        archive.add(path, arcname=path.name, recursive=False)
print(base64.b64encode(buf.getvalue()).decode())
'''
        else:
            script = f'''import base64, io, pathlib, tarfile
root = pathlib.Path({args.remote_directory!r})
assert (root / "results/complete.json").exists(), "Run is not complete"
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz") as archive:
    archive.add(root / "run.log", arcname="run.log", recursive=False)
    for path in sorted((root / "results").rglob("*")):
        if path.is_file():
            archive.add(path, arcname=str(path.relative_to(root / "results")), recursive=False)
print(base64.b64encode(buf.getvalue()).decode())
'''
        unpack(remote(args, script), args.output)
        print('Saved', args.output)


if __name__ == '__main__':
    main()
