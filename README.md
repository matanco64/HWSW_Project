# HWSW Final Project — pyflate, mdp & nbody

Benchmark optimization, analysis, and hardware acceleration proposal for
pyperformance benchmarks. Course: Hardware/Software Integration, Technion.

**The submission is pyflate + nbody.** A third benchmark, mdp, was optimized and
fully measured before the choice was made; it stays in the repo as evidence of
the selection process, but it has no report and is not part of the submission.

| Benchmark | What it is | Baseline | Optimized | Speedup | |
|---|---|---|---|---|---|
| **pyflate** | pure-Python bzip2 decompressor | 1.13 s | 288 ms | **3.93x** | submitted |
| **nbody**   | N-body gravity simulation | 231 ms | 141 ms | **1.64x** | submitted |
| mdp         | exact-arithmetic Markov decision process solver | 4.98 s | 914 ms | 5.44x | candidate only |

Course VM (Ubuntu 22.04, CPython 3.10.12), `pyperformance run --rigorous`, all
three significant under pyperf's t-test; see `results/compare_<bench>.txt`. The
requirement is a 7% improvement on two benchmarks: pyflate cuts runtime 74.5%
and nbody 39.0%, i.e. 10.6x and 5.6x the bar.

The pair was chosen on the hardware story rather than the software margin — mdp
has the larger speedup, but pyflate and nbody map onto the three accelerator
modules already scoped in `hw/` (`huffman_engine` + `mtf_cam` for pyflate,
`grape_pipeline` for nbody), and pyflate's decode engine has shipping-silicon
precedent in Intel IAA.

## Repository structure

```
report_pyflate.pdf / report_nbody.pdf   Per-benchmark reports (course deliverable, one per
                                        selected benchmark; built from report/)
script_pyflate.sh / script_nbody.sh     End-to-end runners (course deliverable)
script_mdp.sh                           Same runner for mdp (candidate, not submitted)
prompt.txt                              AI-tool prompt log (course deliverable)
project_instructions.pdf / .md          Course assignment handout (+ text transcription)
skills-lock.json                        Pinned sources/hashes of the imported skills (`npx skills update`)
.claude/                                Claude Code project config: hook wiring + skills (log-prompt,
                                        and a subset of mattpocock/skills: grilling, teach, research, ...)
benchmarks/
  MANIFEST                              pyperformance custom-benchmark manifest (pyflate, nbody, mdp)
  bm_pyflate/ bm_nbody/ bm_mdp/         Benchmark copies — optimizations land here
dev/
  ENVIRONMENT.md                        The local WSL2 measurement environment (interpreters, perf, Rust)
  <bench>/                              Optimization ladder T0..T3, verification + analysis scripts,
                                        FINDINGS.md — working notes, not a deliverable
rust/nbody/                             PyO3 crate: native advance(). Imported by the benchmark when
                                        available; pure-Python fallback otherwise (see below)
rust/pyflate/                           PyO3 crate: native symbol decode (bit reader, Huffman, MTF,
                                        RUNA/RUNB). Same wiring; also the golden model for hw/
report/                                 Report sources (report_<bench>.typ, figures) + build.sh
results/                                Authoritative course-VM measurements (see below)
results/wsl/                            SUPERSEDED WSL2 cross-check runs — never quote as a result
tools/
  vm_launch.sh / vm_run_all.sh          Detached remote runner for the course VM
  log_prompt_hook.py                    Claude Code hook: auto-appends session prompts to prompt.txt
  hw/                                   Claude Code hooks + status/progress scripts for the HW flow
hw/                                     Hardware accelerator designs (SystemVerilog) + the stage-gated
                                        HW flow: hw/FLOW.md (definition), hw/PLAN.md (steps),
                                        hw/PROGRESS.md (generated status), hw/setup.sh (toolchain)
research/                               Cited research notes (agent skills/toolchain, nbody & pyflate algorithms)
```

`benchmarks/bm_*` start as byte-identical copies of the stock pyperformance
1.14.0 benchmarks (see git history); every optimization is a visible diff
against that baseline. The `[tool.pyperformance] name` fields are kept
identical to the stock names so `pyperf compare_to` lines up before/after.

### `dev/<bench>/` — the optimization ladder

Each benchmark's optimizations were developed as independently measurable tiers
(`t0_stock.py` … `t3_*.py`, plus anti-results such as `tanti_numpy.py`), with a
`bench.py` interleaved timing harness and a `verify.py` correctness oracle
alongside. `FINDINGS.md` records what each tier bought, which ideas were
measured and rejected, and why the shipped tier is the one that ships. This is
evidence and working notes — the deliverable is `benchmarks/`.

Local development and measurement happen under WSL2, not on Windows; the
interpreters, perf setup, and the edit-here/measure-there rule are documented in
**`dev/ENVIRONMENT.md`**. WSL numbers are provisional by construction — the
quotable numbers all come from the course VM.

### `rust/` — the native tier, and how it is selected

Two PyO3 crates, both **bit/byte-exact** against the Python they replace:

| crate | replaces | checked by |
|---|---|---|
| `rust/nbody` | `advance()` — state resident in a `#[pyclass] System` | `dev/nbody/rs_check.py` |
| `rust/pyflate` | bit reader → canonical Huffman → MTF → RUNA/RUNB | `dev/pyflate/rs_check.py` |

Both are **imported, never required**. This is the accelerator interface the
course's Lecture 5 prescribes: the user's command line does not change (Rule 1),
all native code sits in a separate crate behind one call (Rule 2), and a host
without the wheel runs the Python path instead of failing (Rule 3).

An optional import does cost clarity about *what was measured*, so the choice is
explicit and recorded:

```bash
HWSW_BACKEND=auto     # default: prefer native, fall back to Python
HWSW_BACKEND=python   # force the pure-Python path
HWSW_BACKEND=native   # force native; fails loudly if the wheel is missing
```

The back end that actually ran is written into the `hwsw_backend` field of every
result JSON's pyperf metadata. That is not decoration — the first native run
compared native against native, because `pyperf` re-executes its workers with a
scrubbed environment and `HWSW_BACKEND` never reached them. Anything invoking the
benchmark with this variable must pass `--inherit-environ HWSW_BACKEND`, as the
`native` stage in the scripts does.

To build and install a wheel (Linux, CPython 3.10):

```bash
cd rust/pyflate && maturin build --release      # or rust/nbody
sudo python3 -m pip install wheels/*.whl
```

Prebuilt `cp310` manylinux wheels for the course VM are committed under
`rust/<crate>/wheels/`.

### `report/`

One Typst source per benchmark plus `report_appendix.typ`, with shared typography
in `report/style.typ`. Both PDF and `.txt` companions are generated at the repo
root; the text files fulfill the named course deliverables, while PDFs include
figures and diagrams. The appendix records timing provenance, phase-counter
scope, profile transformations, correctness checks and reproduction commands.

Build on Linux/WSL with `./report/build.sh` (optionally set `TYPST`), or on Windows:

```powershell
./report/build.ps1 -Typst 'C:/path/to/typst.exe'
```

Both builds require Typst, Python and Poppler's `pdftotext`. They regenerate
print figures with `report/make_figures.py`: source-line frames in saved py-spy
SVGs are grouped by function and the benchmark subtree is shown with readable
labels. Counts and source filenames are recorded in `report/fig/profile_counts.json`.
The original profile SVGs and their `*_full.svg` counterparts remain in `results/`.
The report also distinguishes current hardware implementation status from
unverified clock, area and performance targets.

## How to reproduce

Everything runs inside the course QEMU VM (Ubuntu 22.04, Python 3.10.12,
python3-dbg, perf, pyperformance 1.14.0):

```bash
./script_pyflate.sh all     # setup -> baseline -> profile+flamegraph -> optimized -> compare
./script_nbody.sh all
./script_mdp.sh all
```

Stages can be run individually:
`setup | baseline | profile | optimized | compare | native`.

- **Baseline** = stock benchmark via `pyperformance run --rigorous`.
- **Optimized** = this repo's `benchmarks/` via `--manifest benchmarks/MANIFEST`
  (same benchmark names, so the comparison matches by name).
- **Native** = the Rust back end against the pure-Python fallback *of the same
  file*, same interpreter and same rigor, so `HWSW_BACKEND` is the only
  difference. Not run through `pyperformance`, which builds its own venv that has
  no extension wheel in it.
- **Evidence** = `results/compare_<bench>.txt`: mean ± std dev for both runs,
  the speedup factor, and pyperf's t-test significance verdict.
  `results/compare_<bench>_native.txt` is the same for the native tier.

### Driving the VM remotely

`tools/vm_launch.sh` runs the whole suite on the VM from a laptop:

```bash
./tools/vm_launch.sh start [bench...]   # sync the repo up, launch the suite detached
./tools/vm_launch.sh status             # running? which stages are done?
./tools/vm_launch.sh tail               # follow the log (Ctrl-C detaches, job keeps running)
./tools/vm_launch.sh fetch              # copy results/ back to this machine
./tools/vm_launch.sh stop
./tools/vm_launch.sh shell "cmd"        # one command on the VM
```

The job runs under **tmux on the VM**, so a dropped SSH connection (or a closed
laptop) does not kill a multi-hour `--rigorous` run. It is **resumable**:
`tools/vm_run_all.sh` stamps each finished stage in `results/.stamps/` and skips
it on a re-run — unless the stage's artifact has since gone missing, in which
case it redoes it. `FORCE=1` redoes everything.

Topology is two hops. The VM is a QEMU guest reachable only as a port forward on
the Technion host's loopback, so every operation relays through the host:

```
laptop  --ssh-->  naranja14  --ssh -p 12222-->  guest VM (127.0.0.1:12222)
```

## `results/` — what is authoritative

Course-VM measurements, and the only numbers to quote:

- `baseline_<bench>.json` / `optimized_<bench>.json` — pyperf runs, plus
  `baseline_<bench>_stats.txt`
- `compare_<bench>.txt` — the headline before/after table
- **before/after profiling pairs**, same flags on both sides so they are directly
  comparable: `flame_<bench>_{stock,opt}.svg`,
  `perf_report_<bench>_{stock,opt}.txt`, `perf_stat_<bench>_{stock,opt}.txt`

**`results/wsl/` is not a result.** Those are superseded WSL2 cross-check runs
(Ubuntu 24.04, CPython 3.10.21) taken while the Technion servers were
unreachable, on a noisy host with 10-25% std devs. They are kept only for the
cross-version (3.10 vs 3.12) discussion in the report. Never quote a WSL number
as a measurement.

### Measurement notes (KVM guest quirks)

- `perf record` uses `-e cpu-clock`, a software timer that samples in
  proportion to elapsed CPU time — the right event for a "where does the time
  go" flame graph. The hardware PMU is nonetheless available: `perf stat -e
  cycles` counts correctly, and `perf record -e cycles -c 2000000` samples
  correctly with clean symbols. What does *not* work is `perf record -e cycles
  -F <n>`, which returns zero samples at any frequency, because perf's
  frequency mode auto-tunes the period from counter feedback and that loop does
  not converge on the KVM vPMU. Use a fixed period (`-c`) for hardware events.
- `perf stat` silently returns zeros for events past the guest's **four**
  general-purpose counters instead of multiplexing them, so request at most
  four hardware events per pass. (This, not a missing PMU, is why `cycles` once
  looked broken.)
- `perf stat` silently returns **zeros past 4 events** in the guest, so counters
  are taken in **two passes** (`cycles:u,instructions:u`, then the
  cache/branch group) and concatenated into one `perf_stat_*` file.
- `pyperf system tune` sets `perf_event_max_sample_rate=1`, which throttles
  `perf record` to 1 Hz; the `profile` stage restores a usable rate first.
- Timings are always measured on release `python3`; profiles are taken with
  `python3-dbg` for symbols (debug build is ~2.5-3x slower and distorts the
  profile — it is never used for quoted numbers).
- `kernel.perf_event_paranoid=-1` must be re-applied after a VM reboot
  (`script_*.sh setup` does this).
