# Repository layout

Reference for someone browsing the repository. `README.md` is the entry point and
carries the reading order, the headline results and the commands; this file is the
detail behind them: the full file inventory, the optimization ladder, how the native
tier is selected, how the reports build and how the course VM is driven.

Entries marked [repo only] are development scaffolding that `.gitattributes` keeps out
of the submission archive.

## File inventory

This describes the **public repository**. Entries marked [repo only] are development
scaffolding that `.gitattributes` keeps out of the submission archive, so they are listed
here for someone browsing the repository, not for someone reading the zip.

```
report_pyflate.txt / report_nbody.txt   Per-benchmark reports (course deliverable, one per
report_pyflate.pdf / report_nbody.pdf   selected benchmark; .txt is the named deliverable, .pdf
                                        carries the figures; both built from report/)
script_pyflate.sh / script_nbody.sh     End-to-end runners (course deliverable); thin
                                        wrappers over tools/runner_common.sh
make_submission.sh                      Verify the deliverables and package them (see below)  [repo only]
prompt.txt                              AI-tool prompt log (course deliverable)
project_instructions.pdf / .md          Course assignment handout (+ text transcription)  [repo only]
skills-lock.json                        Pinned sources/hashes of the imported skills  [repo only]
.claude/                                Claude Code project config: hook wiring + skills (hw-*,
                                        and a subset of mattpocock/skills: grilling, teach, research, ...)  [repo only]
benchmarks/
  MANIFEST                              pyperformance custom-benchmark manifest (pyflate, nbody)
  bm_pyflate/ bm_nbody/         Benchmark copies — optimizations land here
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
  hw/                                   Claude Code hooks + status/progress scripts for the HW flow
hw/                                     Hardware accelerator designs (SystemVerilog) + the stage-gated
                                        HW flow: FLOW.md (definition), PLAN.md (steps),
                                        PROGRESS.md (generated status) [all repo only];
                                        hw/setup.sh (toolchain) ships
research/                               Cited research notes (agent skills/toolchain, nbody & pyflate algorithms)
```

`benchmarks/bm_*` start as byte-identical copies of the original pyperformance
1.14.0 benchmarks (see git history); every optimization is a visible diff
against that baseline. The `[tool.pyperformance] name` fields are kept
identical to the original names so `pyperf compare_to` lines up before/after.

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
`py-spy` and `perf stat` on both the original and optimized sides — an unpinned
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

Prebuilt `cp310` manylinux wheels are committed under `rust/<crate>/wheels/`. They
are the binaries the canonical VM run built and measured, and the `PROVENANCE.json`
beside each records the revision it was built from, the wheel and extension SHA-256
and the run directory. Installing one reproduces that binary, not a fresh build of
the checkout; `tools/build_wheel.sh --record` rebuilds from source, and comparing its
extension hash with `PROVENANCE.json` shows whether the build reproduces the
measured binary.

### `report/`

One Typst source per benchmark plus `report_appendix.typ`, with shared typography
in `report/style.typ`. Both PDF and `.txt` companions are generated at the repo
root; the text files fulfill the named course deliverables, while PDFs include
figures and diagrams. The appendix records timing provenance, phase-counter
scope, profile transformations, correctness checks and reproduction commands.

The reports include checked before/after examples, a Huffman lookup walkthrough,
BWT/MTF/RLE examples and an nbody dependency diagram. Run
`python3 report/verify_examples.py` to check those examples against the shipped
functions without installing benchmark dependencies.
[Defense guide](report/defense_guide.md) provides a 23-minute presentation route,
26 questions with answers, evidence links and demonstration commands.
[AI prompt log](prompt.txt) is the single prompt log for the project; its "merged log"
block holds the detailed report-revision requests and per-improvement instructions.

### Names and ID numbers

The reports carry names only. This repository is public, so ID numbers are kept
out of every committed file; git history would keep them even after a later
deletion, and the course brief does not ask for them.

ID numbers live on their own page, `report/ids.typ`, which is the convention
HW1 and HW2 used: HW1's report said "Names / IDs — see separate PDF", and HW2
built a separate `ids.pdf` from a gitignored `ids.local`. The reports
themselves name the authors once, in the byline, and carry no numbers.

Create the local file once:

```bash
printf 'MATAN_ID=012345678\nYUVAL_ID=087654321\n' > report/ids.local
```

The packaging script sources it, compiles the page and adds it to the archive as
`ids.pdf` at the top level. Both the file and the generated PDF are gitignored, so ID numbers
exist only while an archive is being built. `./report/build.sh` is unaffected
and never touches them.

### Building the reports

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
companions are named deliverables produced by `pdftotext`, which reconstructs
table rows from glyph positions, and the result depends on the implementation:
the companions built with poppler's `-layout` were intact, while a rebuild with
xpdf's `pdftotext` 4.00 `-layout` shifted values by one row in several tables —
silently, with a correct PDF. The builds use `-table` where the installed
`pdftotext` has it (xpdf) and `-layout` otherwise (poppler), and the checker gates
whichever ran: every row's label must be followed by its own values before the
next row's label appears, and the companion must be valid UTF-8.

Matched Python/native instruction, cycle, branch and generic cache counters are
preserved in `results/vm_release_20260907/counters/`; regenerate their validated summary
with `python report/summarize_counters.py --directory results/vm_release_20260907/counters`.
The earlier capture remains in `results/native_counters_20260907/`; invalid L1 events
from that capture are excluded and were not requested in the new one.
`report/check_pyflate_backend.py /path/to/repo` verifies actual Rust dispatch and
output in Python, native and auto modes using an interpreter with the wheel installed.

### Driving the course VM

`python report/summarize_refresh.py` validates the latest timing metadata and source hashes.
`report/vm_refresh.py start` uploads `git archive HEAD` — the committed revision,
never uncommitted edits — to a fresh directory on the VM and launches
`report/vm_refresh_worker.py`. The worker is not a second timing route: it runs
the timed stages through `tools/vm_run_all.sh`, pinned to one CPU, and adds only
what the stage scripts do not produce — pyflate's crate tests and dispatch check
against a fresh cargo build, the built wheels with their provenance records,
timing distributions, and `tools/check_all.sh --require-native`. `status` and
`fetch` follow the run; connection details are CLI arguments, with private
access instructions kept outside the repository in an untracked `*.local.md` note.

