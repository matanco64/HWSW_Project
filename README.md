# HWSW Final Project — pyflate & nbody

Benchmark optimization, analysis, and hardware acceleration proposal for
pyperformance benchmarks. Course: Hardware/Software Integration, Technion.

Repository: <https://github.com/matanco64/HWSW_Project>

## Start here

Deliverables, in reading order: `report_nbody.txt` and `report_pyflate.txt` (the PDF
editions carry the figures), `report_appendix.txt` (methods, provenance and the limits of
every measurement), `hw/docs/hardware_report.md` (the three accelerators against §7 of the
brief, with the toolchain and a source for every number), and `prompt.txt` (every AI prompt
used). Reproduce the headline comparisons with one command per benchmark, inside the course
VM:

```bash
./script_nbody.sh all      # setup → baseline → profile → optimized → compare (→ native)
./script_pyflate.sh all
```

**How AI tools were used.** Claude Code (Anthropic) throughout and, for one report-revision
pass, OpenAI Codex; every prompt is in `prompt.txt`, auto-logged by a hook from 2026-08-24.
Yuval Kogan directed the hardware flow (PRD → architecture → RTL → verification → PPA),
reviewed each stage gate, and wrote and edited the reports' hardware sections; Matan Cohen
designed and measured the software optimization ladder, ran the course-VM measurements, and
wrote the reports' software sections. The agent drafted RTL, testbenches, flow documents and
report text under those directions; every number in the reports is regenerated from files in
`results/` and `hw/`. The submission archive is the repository minus agent tooling,
flow-gate documents and tool logs (`.gitattributes` `export-ignore`); the public repository
keeps them.

**The project and submission cover pyflate and nbody.**

| Benchmark | What it is | Baseline | Optimized | Speedup | |
|---|---|---|---|---|---|
| **pyflate** | bzip2, optimized Python + Rust decoder | 1.12 s | 170.01 ms | **6.61x** | submitted |
| pyflate (Python tier) | optimized Python decoder | 1.12 s | 281.16 ms | 4.00x | supporting comparison |
| **nbody**   | N-body gravity simulation | 231 ms | 143 ms | **1.62x** | submitted |

Course VM (Ubuntu 22.04, CPython 3.10.12), rigorous pyperf measurements, every timed
run pinned to one guest CPU. Both benchmarks' figures come from one canonical run of
revision 2c8c754 through the documented scripts, with the Rust extensions built from
that revision: `results/vm_canonical_20260910_2c8c754/` holds every 120-value JSON and
comparison. The combined Python/Rust pyflate path cuts runtime **84.9%**; Rust adds
**1.67x** over the Python back end. The Python tier alone cuts 75.0%, and nbody's Python
changes cut 38.1%, both exceeding the course's 7% requirement. Earlier captures,
including pyflate's `vm_release_20260907/`, remain in `results/`.

The benchmarks offer complementary hardware boundaries: pyflate's streaming symbol
pipeline and nbody's stateful force/integration loop. Their accelerator designs live in `hw/`.

All three accelerators have SystemVerilog implementations, recorded verification
and synthesis results. Physical-design runs stopped before routed sign-off; the
frequencies below are preliminary timing estimates, not measured silicon. The reports
separate simulation cycles, mapped area and timing evidence from design targets:

| module | benchmark | cells | area | Fmax | tests |
|---|---|---|---:|---:|---:|
| `grape_pipeline` | nbody | 584,454 | 4.08 mm² | 19.5 MHz | 9/9 |
| `huffman_engine` | pyflate | 151,058 | 1.63 mm² | 39.9 MHz | 17/17 |
| `mtf_cam` | pyflate | 18,814 | 0.19 mm² | 37.5 MHz | 16/16 |

All three frequencies are **post-CTS** static-timing estimates (cells and the clock tree
placed, signal wires not routed) from runs that met their constraint; none has completed 50 MHz
routed sign-off, and each module's 50 MHz run is kept as the second evidence point. The grape area
is a plain Yosys figure from before the final rewrite of its issue-selection logic; the OpenLane
synthesis of the final RTL gives 446,932 cells / 4.66 mm²
(`hw/grape_pipeline/synth/evidence/area_openlane.txt`). The two pyflate
modules are also simulated together as one chain (`hw/pyflate_accel/`): byte-exact over the
benchmark block's 336,184 output bytes in 159,303 cycles.

Reproduce the hardware checks (after `source hw/env.sh`; tools are installed by
`hw/setup.sh`): `make -C hw/pyflate_accel sim` runs the whole pyflate chain in about 30 s;
`make -C hw/<module> sim` runs a module's regression; `make -C hw/<module> area` re-runs
synthesis. [The hardware report](hw/docs/hardware_report.md) ([PDF](hw/docs/hardware_report.pdf)) covers all three modules
against the brief's hardware items, with the toolchain and a source for every number.
Per-module detail is in `hw/<module>/docs/ppa.md` and `integration.md`.

## Repository structure

| Path | What it is |
|---|---|
| `report_<bench>.txt` / `.pdf` | The per-benchmark reports (course deliverable); `.txt` is the named one |
| `report_appendix.txt` / `.pdf` | Measurement protocol, evidence levels and provenance |
| `script_<bench>.sh` | The end-to-end runners (course deliverable) |
| `prompt.txt` | AI-tool prompt log (course deliverable) |
| `benchmarks/` | The two pyperformance benchmarks; every optimization is a diff against the original |
| `rust/` | The optional native tier for each benchmark, plus the built wheels |
| `dev/` | The optimization ladder T0..T3 and the analysis scripts behind the reports |
| `results/` | Every measurement, with the canonical run identified below |
| `report/` | Typst sources and figures for the reports, and the tooling that builds them |
| `hw/` | The three SystemVerilog accelerators, their testbenches, synthesis evidence and the consolidated hardware report |
| `tools/` | Shared runner, correctness gate and VM helpers |
| `research/` | Cited background notes |

The full inventory, the optimization ladder, how the native tier is selected, how the
reports build and how the course VM is driven are in
[docs/repository-layout.md](docs/repository-layout.md).


## Checks

```bash
./tools/check_all.sh                   # every correctness check, one exit status
./tools/check_all.sh --require-native  # fail, rather than skip, without the wheels
python3 -m unittest discover -s tests -v
```

`check_all.sh` runs the unit tests, both nbody contracts (`verify.py` at N = 5
and at N = 5, 10, 20), both native contracts (`rs_check.py`) and the report
text-export check, and names anything it skipped. `tests/test_software.py`
turns each failure this project actually hit into a regression test: a
tolerance-only pass accepted as exact, a missing original reference reported as a
pass, the oracle checking a stale kernel when `nbody_rs` is installed, metadata
hashing maturin's `__init__.py` instead of the compiled extension, a text export
that shifted table rows, and runner assertions for wrong, unpinned or
mis-pinned runs.

A GitHub Actions workflow (repository only, not in the archive) runs the same on Ubuntu 22.04 with
CPython 3.10 after building both wheels from the checkout with
`tools/build_wheel.sh`. It measures nothing: shared runners are not a timing
platform.

## Packaging the submission

Running make_submission.sh from the repository (it is not in the archive; `--check`
verifies only) writes
`submission/hwsw_submission_<date>_<rev>.zip`: `git archive HEAD` minus the paths listed in
`.gitattributes` as `export-ignore` (agent tooling, flow-gate documents, tool logs, the
solver scratch under `hw/**/synth/formal*/` and the counter captures' console spill), plus
the generated `ids.pdf`. Each proof's `PASS` and `config.sby` are kept, as are the per-run
`*.json` and `*.perf.csv` that `counters/summary.json` was computed from. It refuses a dirty tree,
reports older than their sources (asked from git history, not timestamps), a missing
`report/ids.local`, or a failing `tools/check_all.sh`; the header comment of the script has
the full rationale.

## How to reproduce

Everything runs inside the course QEMU VM (Ubuntu 22.04, Python 3.10.12,
python3-dbg, perf, pyperformance 1.14.0):

```bash
./script_pyflate.sh all     # setup -> baseline -> profile -> optimized -> compare -> native
./script_nbody.sh all
```

Stages can be run individually:
`setup | baseline | profile | optimized | compare | wheel | native`.

Both runners are thin wrappers over one implementation,
`tools/runner_common.sh`. They used to be three copies of the same 130 lines and
had drifted apart — one pinned the back end while profiling and one did not, and
their build instructions pointed at different directories — which changed what a
reader would actually measure depending on which script they ran.

- **Prerequisites are checked, not assumed.** Missing `pyperf` or `pyperformance`
  is an error; a CPython or pyperformance version other than the VM's is a
  warning saying the run is not comparable with `results/`. The versions, host
  and original path are written to `environment_<bench>.txt` beside the results.
- **The original benchmark is located programmatically** through the installed
  `pyperformance` package, falling back to a sibling source checkout, instead of
  a hard-coded `dist-packages` path.
- **Results go to a fresh directory,** `results/runs/<UTC stamp>_<bench>/`, with
  `results/runs/latest` pointing at the current one. The preserved captures in
  `results/` are what the reports quote, so a rerun must never land on top of
  them. `HWSW_RESULTS=<dir>` overrides the destination; promoting a run to
  authoritative is a deliberate copy.
- **Timed stages run on one guest CPU.** `baseline`, `optimized` and `native`
  pass `--affinity` to pyperf/pyperformance — the protocol the preserved pyflate
  headline was measured with, which the scripts previously omitted.
  `HWSW_CPU=<n>` chooses the CPU, `HWSW_CPU=none` disables pinning, and every
  JSON's recorded `cpu_affinity` is asserted along with its back end.
- **`all` reports a missing native tier instead of swallowing it.** It used to
  end in `native || true`, which left an incomplete results directory looking
  complete. A native failure is now named on stderr, recorded in
  `stages_incomplete.txt`, and returned as a nonzero exit status — the
  original/optimized comparison is still complete and still valid. The file is written
  into the run's results directory by `tools/runner_common.sh`; it does not exist until a
  native stage has actually been skipped.

- **Baseline** = original benchmark via `pyperformance run --rigorous`.
- **Optimized** = this repo's `benchmarks/` via `--manifest benchmarks/MANIFEST`
  (same benchmark names, so the comparison matches by name).
- **Native** = the Rust back end against the pure-Python fallback *of the same
  file*, same interpreter and same rigor, so `HWSW_BACKEND` is the only
  difference. Not run through `pyperformance`, which builds its own venv that has
  no extension wheel in it.
- **Evidence** = `results/compare_<bench>.txt`: pyperf's `compare_to --table` output
  (mean per run and the speedup factor); the per-run JSONs carry the 120 values
  and their metadata.
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

- `vm_canonical_20260910_2c8c754/` — the pinned canonical run of revision 2c8c754
  (a pre-rewrite revision ID — see [docs/history-rewrite.md](docs/history-rewrite.md))
  through the documented scripts: source of both headlines (appendix A7)
- `vm_release_20260907/` — pyflate's earlier pinned capture; its counter data
  (appendix A2) are still quoted
- `baseline_<bench>.json` / `optimized_<bench>.json` — pyperf runs, plus
  `baseline_<bench>_stats.txt`
- `compare_<bench>.txt` — the headline before/after table
- For nbody and pyflate these top-level timing files **are** the canonical run,
  promoted out of `vm_canonical_20260910_2c8c754/suite/` by a deliberate copy.
  They used to be an older capture, so the first table a reader opened
  (1.64x nbody, 3.93x pyflate) disagreed with the reports (1.62x, 4.00x). The
  superseded capture is in git history.
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
