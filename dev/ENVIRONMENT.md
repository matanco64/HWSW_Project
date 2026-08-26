# Local measurement environment (WSL2)

The course QEMU VM on the Technion servers is the *official* measurement target, but
it was unreachable while this work was done. Everything below is the local stand-in.
It is a genuinely good stand-in: same CPython minor version, same OS family, same
wheel ABI.

## Why WSL and not Windows

Windows-native measurement was tried first and rejected:

- The Windows-side `.venvs/py312` and `.venvs/py314` only get us CPython 3.12/3.14,
  which have adaptive specialization the VM's 3.10 does not — they systematically
  understate every interpreter-overhead optimization.
- No `perf`, so no flame graphs.
- No usable C toolchain for PyO3 (no MSVC build tools installed).

WSL2 Ubuntu 24.04 solves all three.

## What is installed

| Component | Version | Path |
|---|---|---|
| Ubuntu | 24.04.1 LTS (kernel 6.18.33.2-microsoft-standard-WSL2) | — |
| **CPython 3.10.21** | matches VM's 3.10.12 minor | `/root/hwsw-env/py310/bin/python` |
| CPython 3.12.14 | version-sensitivity cross-check | `/root/hwsw-env/py312/bin/python` |
| pyperf | 2.10.0 | in both venvs |
| pyperformance | 1.14.0 (same as VM) | in the py310 venv |
| numpy | 2.2.6 | in both venvs |
| Rust | 1.98.0 (rustup, stable) | `~/.cargo/bin` |
| maturin | 1.15.0 | `~/.local/bin` |
| perf | linux-tools 6.8.0-138 | `/usr/lib/linux-tools-6.8.0-138/perf` |
| FlameGraph | brendangregg, HEAD | `/root/FlameGraph/` |
| py-spy | 0.4.2 | `~/.local/bin` |

CPython 3.10 and 3.12 come from `uv python install` (python-build-standalone), not
from Ubuntu's apt. Absolute timings therefore differ from the VM's Ubuntu-built
python3.10 (different PGO/LTO configuration), but **relative speedups — the only
thing this project reports — carry over.**

## Working rule: edit on Windows, measure in WSL

The repo lives on OneDrive (`/mnt/c/...` from WSL). drvfs I/O is slow enough to
distort timings, so never measure in place. Sync into the native filesystem first:

```bash
/root/hwsw-env/sync.sh          # rsync Windows repo -> /root/hwsw (one-way, --delete)
cd /root/hwsw
```

The sync is **one way**. Anything produced under `/root/hwsw` is destroyed by the
next sync — copy artifacts you want to keep back to the Windows path explicitly.

## Measuring

```bash
PY=/root/hwsw-env/py310/bin/python
$PY benchmarks/bm_<bench>/run_benchmark.py --rigorous -o base.json
$PY benchmarks/bm_<bench>/run_benchmark.py --rigorous -o opt.json
$PY -m pyperf compare_to base.json opt.json --table
```

Quote the `compare_to` mean ± std dev and its t-test verdict, never a single timing.

## Profiling

```bash
PERF=/usr/lib/linux-tools-6.8.0-138/perf
$PERF record -F 999 -g -e cpu-clock -o p.data -- $PY benchmarks/bm_<bench>/run_benchmark.py --worker -l2 -w0 -n6
$PERF report --stdio -i p.data > perf_report.txt
$PERF script -i p.data | /root/FlameGraph/stackcollapse-perf.pl | /root/FlameGraph/flamegraph.pl > flame.svg
```

`-e cpu-clock` is required: the WSL2 kernel exposes no hardware PMU, so `cycles`
records nothing. (The course VM has the same constraint for a different reason —
its KVM guest PMU records zero samples for `cycles`.) Verified working: call
graphs unwind and symbolize.

CPython 3.10 has no `-X perf` trampoline (3.12+ only), so perf shows C-level
interpreter frames. Use `py-spy record -f flamegraph` for Python-level frames.

## Rust / PyO3

Verified end to end: `maturin build --release -i /root/hwsw-env/py310/bin/python`
produces `...-cp310-cp310-manylinux_2_34_x86_64.whl`, which imports and runs.

That wheel tag requires glibc ≥ 2.34; the course VM is Ubuntu 22.04 with glibc
2.35, **so wheels built here are directly usable on the VM.** Re-verify there once
the servers are reachable.

## Caveat to carry into the report

This is a shared desktop, not a tuned benchmark host — no CPU isolation, no
governor control, and `pyperf system tune` cannot do its usual work under WSL.
Std devs are correspondingly wide. Headline numbers must be re-measured
back-to-back on an otherwise-idle machine, and re-confirmed on the course VM
before they go in the report.
