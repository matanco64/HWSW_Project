# HWSW Final Project — pyflate, mdp & nbody

Benchmark optimization, analysis, and hardware acceleration proposal for
pyperformance benchmarks. Course: Hardware/Software Integration, Technion.

**The submission is pyflate + nbody.** A third benchmark, mdp, was optimized and
fully measured before the choice was made; it stays in the repo as evidence of
the selection process, but it has no report and is not part of the submission.

| Benchmark | What it is | Baseline | Optimized | Speedup | |
|---|---|---|---|---|---|
| **pyflate** | bzip2, optimized Python + Rust decoder | 1.13 s | 173.59 ms | **6.51x** | submitted |
| pyflate (Python tier) | optimized Python decoder | 1.13 s | 288.00 ms | 3.92x | supporting comparison |
| **nbody**   | N-body gravity simulation | 231 ms | 141 ms | **1.64x** | submitted |
| mdp         | exact-arithmetic Markov decision process solver | 4.98 s | 914 ms | 5.44x | candidate only |

Course VM (Ubuntu 22.04, CPython 3.10.12), rigorous pyperf measurements. Pyflate's
latest three-tier run uses the refactored Rust extension rebuilt on the VM:
`results/vm_release_20260907/` contains all 120-value JSONs and comparisons.
The combined Python/Rust path cuts runtime **84.6%**; Rust adds **1.66x** over
optimized Python. The Python tier alone cuts 74.5%, and nbody's Python changes
cut 38.9%, both exceeding the course's 7% requirement. Earlier nbody/mdp
comparisons remain in `results/compare_<bench>.txt`.

The pair was chosen on the hardware story rather than the software margin — mdp
has the larger speedup, but pyflate and nbody map onto the three accelerator
modules already scoped in `hw/` (`huffman_engine` + `mtf_cam` for pyflate,
`grape_pipeline` for nbody), and pyflate's decode engine has shipping-silicon
precedent in Intel IAA.

## Repository structure

```
report_pyflate.pdf / report_nbody.pdf   Per-benchmark reports (course deliverable, one per
                                        selected benchmark; built from report/)
script_pyflate.sh / script_nbody.sh     End-to-end runners (course deliverable); thin
                                        wrappers over tools/runner_common.sh
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
  runner_common.sh                      The one implementation of every runner stage
  build_wheel.sh                        Builds a crate and installs THAT wheel, recording
                                        the imported path/hash
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

The back end that actually ran is written into every result JSON's pyperf
metadata, along with the request that produced it and the binary that served it:

| metadata field | what it records |
|---|---|
| `hwsw_backend` | `python` or `native` — what the workers actually ran |
| `hwsw_backend_requested` | the `HWSW_BACKEND` value the workers *saw* |
| `hwsw_native_module` / `hwsw_native_sha256` | the loaded extension path and hash |

That is not decoration — the first native run compared native against native,
because `pyperf` re-executes its workers with a scrubbed environment and
`HWSW_BACKEND` never reached them. Two things now prevent a repeat:

- **The benchmark propagates its own configuration.** Each `run_benchmark.py`
  appends `HWSW_BACKEND` to pyperf's `inherit_environ` after parsing its
  arguments, so workers receive it whether or not the caller passed
  `--inherit-environ HWSW_BACKEND`. That flag is now belt-and-braces; it is also
  the only option for `pyperformance run`, which offers no way to forward it.
- **The scripts check the result rather than trusting the request.** The
  `native` stage asserts both `hwsw_backend` and `hwsw_backend_requested` on each
  JSON it produces, so a run whose environment never reached the workers fails
  loudly even when the fallback happened to pick the right path.

Every measured *and profiled* invocation is pinned, including `perf record`,
`py-spy` and `perf stat` on both the stock and optimized sides — an unpinned
profile would silently sample the Rust kernel on any host with the wheel
installed.

To build and install a wheel (Linux, CPython 3.10):

```bash
./tools/build_wheel.sh pyflate      # or nbody
```

One command on purpose. The obvious two-line version — `maturin build --release`
then `pip install wheels/*.whl` — installs a **different file from the one it
just built**: maturin writes to `target/wheels/`, while `wheels/` holds the
prebuilt wheel committed for the course VM. Both are version `0.1.0`, so pip
reports the same thing either way, and a reader following those two lines from a
fresh clone would compile the current source and then measure a saved binary of
it.

`tools/build_wheel.sh` builds into a fresh directory, refuses to continue unless
exactly one wheel landed there, installs **that path**, and then prints what
Python actually imported afterwards — the module path and its SHA-256, the
wheel's SHA-256, the crate source hashes and the toolchain versions. Pass
`--record <file>` to save that as JSON; `./script_<bench>.sh wheel` does, into
the run's results directory.

Prebuilt `cp310` manylinux wheels for the course VM are committed under
`rust/<crate>/wheels/`. They are a convenience for a host that cannot build, not
part of the reproduction route: installing one means the measurement describes
that committed binary rather than the source in the checkout.

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
print figures with `report/make_figures.py`: full original flame graphs retain
their frame geometry and context, with numbered highlights and enlarged detail
crops. Counts and source filenames are recorded in `report/fig/profile_counts.json`.
The original profile SVGs and their `*_full.svg` counterparts remain in `results/`.
The report also distinguishes current hardware implementation status from
unverified clock, area and performance targets.

Two summaries turn recorded evidence into report tables, without re-measuring
anything:

```bash
python report/summarize_distribution.py results/baseline_nbody.json ...   # appendix A5
python report/summarize_profiles.py --top 10                             # appendix A6
```

`summarize_distribution.py` reports the quantiles behind each `mean ± SD`, and
decomposes the variance into between-worker and within-worker components. The
120 values of a rigorous run come from 40 workers, three each, so they are not
120 independent observations; the tool prints the intraclass correlation, the
design effect and the corrected standard error. `summarize_profiles.py` produces
flat function tables with *self* and *inclusive* percentages named as such, from
`perf report`'s own columns and from the py-spy flame graphs. Its `--group
NAME=REGEX` sums a family of symbols and lists every contributor, so prose that
adds symbols up quotes a number a reader can reconstruct.

`report/check_txt_tables.py` runs at the end of both builds. The `.txt`
companions are named deliverables produced by `pdftotext -layout`, which
reconstructs table rows from glyph positions and gets it wrong on wide numeric
tables — silently, with a correct PDF. It caught two such tables here, one of
which had been printing each ablation's cost one row too high. The checker
requires every row's label and its own values to appear together, in order, and
rejects a companion that is not valid UTF-8.

Matched Python/native instruction, cycle, branch and generic cache counters are
preserved in `results/vm_release_20260907/counters/`; regenerate their validated summary
with `python report/summarize_counters.py --directory results/vm_release_20260907/counters`.
The earlier capture remains in `results/native_counters_20260907/`; invalid L1 events
from that capture are excluded and were not requested in the new one.
`report/check_pyflate_backend.py /path/to/repo` verifies actual Rust dispatch and
output in Python, native and auto modes using an interpreter with the wheel installed.

`python report/summarize_refresh.py` validates the latest timing metadata and source hashes.
`report/vm_refresh.py` starts an isolated remote build/run and fetches the resulting evidence;
connection details are CLI arguments, with private access instructions in `VM_GUIDE.local.md`.

## How to reproduce

Everything runs inside the course QEMU VM (Ubuntu 22.04, Python 3.10.12,
python3-dbg, perf, pyperformance 1.14.0):

```bash
./script_pyflate.sh all     # setup -> baseline -> profile -> optimized -> compare -> native
./script_nbody.sh all
./script_mdp.sh all         # candidate; no Rust crate, so no wheel/native stage
```

Stages can be run individually:
`setup | baseline | profile | optimized | compare | wheel | native`.

All three runners are thin wrappers over one implementation,
`tools/runner_common.sh`. They used to be three copies of the same 130 lines and
had drifted apart — one pinned the back end while profiling and one did not, and
their build instructions pointed at different directories — which changed what a
reader would actually measure depending on which script they ran.

- **Prerequisites are checked, not assumed.** Missing `pyperf` or `pyperformance`
  is an error; a CPython or pyperformance version other than the VM's is a
  warning saying the run is not comparable with `results/`. The versions, host
  and stock path are written to `environment_<bench>.txt` beside the results.
- **The stock benchmark is located programmatically** through the installed
  `pyperformance` package, falling back to a sibling source checkout, instead of
  a hard-coded `dist-packages` path.
- **Results go to a fresh directory,** `results/runs/<UTC stamp>_<bench>/`, with
  `results/runs/latest` pointing at the current one. The preserved captures in
  `results/` are what the reports quote, so a rerun must never land on top of
  them. `HWSW_RESULTS=<dir>` overrides the destination; promoting a run to
  authoritative is a deliberate copy.
- **`all` reports a missing native tier instead of swallowing it.** It used to
  end in `native || true`, which left an incomplete results directory looking
  complete. A native failure is now named on stderr, recorded in
  `stages_incomplete.txt`, and returned as a nonzero exit status — the
  stock/optimized comparison is still complete and still valid.

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
`tools/vm_run_all.sh` stamps each finished stage in `results/runs/vm/.stamps/` and skips
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

These are the configurations that worked *in these runs on this guest*. They are
observations, not established kernel or KVM behaviour; Appendix A3 states the
same limits and is the careful version — the two are meant to agree.

- `perf record` uses `-e cpu-clock`, a software timer that samples in
  proportion to elapsed CPU time — the right event for a "where does the time
  go" flame graph. The hardware PMU is nonetheless usable here: `perf stat -e
  cycles` counted correctly, and `perf record -e cycles -c 2000000` sampled
  correctly with clean symbols. What did *not* work is `perf record -e cycles
  -F <n>`, which returned zero samples at every frequency tried. The plausible
  reading is that perf's frequency mode auto-tunes the period from counter
  feedback and that loop does not converge on this vPMU, but that cause was not
  established — only the working configuration was. Use a fixed period (`-c`)
  for hardware events.
- `perf stat` returned zeros, rather than multiplexing, for events past the
  guest's **four** general-purpose counters, so counters are taken in **two
  passes** (`cycles:u,instructions:u`, then the cache/branch group) and
  concatenated into one `perf_stat_*` file. This, not a missing PMU, is why
  `cycles` once looked broken. Check the actual counts and the enabled/running
  time rather than assuming multiplexing happened.
- `pyperf system tune` sets `perf_event_max_sample_rate=1`, which throttles
  `perf record` to 1 Hz; the `profile` stage restores a usable rate first.
- Timings are always measured on release `python3`; profiles are taken with
  `python3-dbg` for symbols (debug build is ~2.5-3x slower and distorts the
  profile — it is never used for quoted numbers).
- `kernel.perf_event_paranoid=-1` must be re-applied after a VM reboot
  (`script_*.sh setup` does this).
