"""Start, inspect and fetch the canonical course-VM run over a two-hop SSH relay.

`start` uploads `git archive HEAD` -- exactly the committed revision, plus a
REVISION file -- into a new remote temp directory and launches
report/vm_refresh_worker.py there, detached. The worker times through
tools/vm_run_all.sh, the route the README documents, so the numbers it produces
are the numbers a reader following the README would get. Uncommitted changes
are not uploaded, and `start` says so rather than measuring something that has
no revision.

The existing ~/hwsw-project checkout is not touched. The system-installed
nbody_rs / pyflate_rs ARE replaced by wheels built from the uploaded revision:
that is the wheel stage's job, and the installed extension's hash is recorded
with every native result. Infrastructure is supplied via CLI, never stored in
the report sources.

    python report/vm_refresh.py start  --jump USER@HOST [--benches ...] [--cpu N] [--counters]
    python report/vm_refresh.py status --jump USER@HOST --remote-directory DIR
    python report/vm_refresh.py fetch  --jump USER@HOST --remote-directory DIR --output PATH
"""
import argparse
import base64
import io
from pathlib import Path, PurePosixPath
import shlex
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parent.parent

LATEST_RUN = '''from pathlib import Path
root = Path({root!r})
runs = sorted((root / "results" / "runs").glob("release_*"))
out = runs[-1] if runs else None
'''


def remote(args, script, timeout=90):
    inner = shlex.join(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                        '-p', str(args.port), args.guest, 'python3 -'])
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                             args.jump, inner], input=script.encode(),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
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


def git(*cmd):
    return subprocess.check_output(['git', '-c', f'safe.directory={ROOT.as_posix()}', *cmd],
                                   cwd=ROOT)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('action', choices=['start', 'status', 'fetch'])
    ap.add_argument('--jump', required=True)
    ap.add_argument('--guest', default='ubuntu@127.0.0.1')
    ap.add_argument('--port', type=int, default=12222)
    ap.add_argument('--remote-directory')
    ap.add_argument('--output', type=Path)
    ap.add_argument('--benches', nargs='+', default=['nbody', 'pyflate'])
    ap.add_argument('--cpu', type=int)
    ap.add_argument('--counters', action='store_true')
    args = ap.parse_args()

    if args.action == 'start':
        rev = git('rev-parse', 'HEAD').decode().strip()
        if git('status', '--porcelain', '--untracked-files=no').strip():
            print('WARNING: uncommitted changes are NOT uploaded; measuring', rev)
        encoded = base64.b64encode(git('archive', '--format=tar.gz', 'HEAD')).decode()
        worker = ['--benches', *args.benches]
        if args.cpu is not None:
            worker += ['--cpu', str(args.cpu)]
        if args.counters:
            worker.append('--counters')
        script = f'''import base64, io, os, pathlib, subprocess, tarfile, tempfile
root = pathlib.Path(tempfile.mkdtemp(prefix="hwsw-release-", dir=pathlib.Path.home()))
with tarfile.open(fileobj=io.BytesIO(base64.b64decode({encoded!r})), mode="r:gz") as archive:
    for member in archive.getmembers():
        rel = pathlib.PurePosixPath(member.name)
        assert not rel.is_absolute() and ".." not in rel.parts, member.name
        target = root.joinpath(*rel.parts)
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
        elif member.isfile():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.extractfile(member).read())
            os.chmod(target, member.mode & 0o777)
(root / "REVISION").write_text({rev!r} + "\\n")
with (root / "run.log").open("wb") as log:
    process = subprocess.Popen(["python3", str(root / "report/vm_refresh_worker.py"), *{worker!r}],
        cwd=root, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True)
print(root)
print("revision", {rev!r})
print("pid", process.pid)
'''
        print(remote(args, script, timeout=900))
    elif args.action == 'status':
        if not args.remote_directory:
            ap.error('--remote-directory is required')
        script = LATEST_RUN.format(root=args.remote_directory) + '''
print((root / "run.log").read_text()[-1800:])
if out is not None:
    logs = list(out.glob("*.log"))
    if logs:
        latest = max(logs, key=lambda p: p.stat().st_mtime)
        print("Latest:", latest.name)
        print(latest.read_text()[-1200:])
    print("run:", out)
    print("complete:", (out / "complete.json").exists())
'''
        print(remote(args, script))
    else:
        if args.output is None or not args.remote_directory:
            ap.error('--remote-directory and --output are required')
        # perf.data captures run to hundreds of megabytes and are not evidence
        # the reports quote; everything else in the run directory comes back.
        script = LATEST_RUN.format(root=args.remote_directory) + '''
import base64, io, tarfile
assert out is not None and (out / "complete.json").exists(), "Run is not complete"
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz") as archive:
    archive.add(root / "run.log", arcname="run.log", recursive=False)
    for path in sorted(out.rglob("*")):
        if path.is_file() and not path.name.endswith(".perf.data"):
            archive.add(path, arcname=str(path.relative_to(out)), recursive=False)
print(base64.b64encode(buf.getvalue()).decode())
'''
        unpack(remote(args, script, timeout=900), args.output)
        print('Saved', args.output)


if __name__ == '__main__':
    main()
