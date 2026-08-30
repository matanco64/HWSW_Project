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
report_pyflate.txt / report_nbody.txt   Per-benchmark reports (course deliverable, one per
                                        selected benchmark)
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
rust/nbody/                             PyO3 crate: native advance(). Built and measured, deliberately
                                        NOT wired into the measured benchmark (see below)
report/                                 Report sources (report.html + common.css) and build.sh -> report.pdf
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

### `rust/nbody/` — built, measured, not wired in

A PyO3 crate implementing `advance()` natively: **25.8x on the kernel**, output
**bit-for-bit identical** to CPython after 20,000 steps (`dev/nbody/rs_check.py`).
It is deliberately **not** imported by `benchmarks/bm_nbody/run_benchmark.py`.
The pure-Python tier already clears the required speedup on its own, and an
optional import with a silent Python fallback would make the measured
configuration ambiguous — the number would depend on whether a wheel happened to
be installed. It is kept as an optimization tier and as the behavioural spec for
the GRAPE-style accelerator in `hw/`.

### `report/`

`report.html` + `common.css` are the report sources; `./report/build.sh` renders
them to `report.pdf` with headless Chrome. Chrome cannot write into the
OneDrive-synced project folder (access denied), so build.sh prints to a temp path
and copies the PDF into place.

## How to reproduce

Everything runs inside the course QEMU VM (Ubuntu 22.04, Python 3.10.12,
python3-dbg, perf, pyperformance 1.14.0):

```bash
./script_pyflate.sh all     # setup -> baseline -> profile+flamegraph -> optimized -> compare
./script_nbody.sh all
./script_mdp.sh all
```

Stages can be run individually: `setup | baseline | profile | optimized | compare`.

- **Baseline** = stock benchmark via `pyperformance run --rigorous`.
- **Optimized** = this repo's `benchmarks/` via `--manifest benchmarks/MANIFEST`
  (same benchmark names, so the comparison matches by name).
- **Evidence** = `results/compare_<bench>.txt`: mean ± std dev for both runs,
  the speedup factor, and pyperf's t-test significance verdict.

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

- `perf record` must use `-e cpu-clock` — the guest's `cycles` PMU event
  records zero samples.
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
