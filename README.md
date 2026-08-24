# HWSW Final Project — pyflate & nbody

Benchmark optimization, analysis, and hardware acceleration proposal for two
pyperformance benchmarks: **pyflate** (pure-Python bzip2 decompressor) and
**nbody** (N-body gravity simulation). Course: Hardware/Software Integration,
Technion.

## Repository structure

```
report_pyflate.txt / report_nbody.txt   Benchmark reports (course deliverable)
script_pyflate.sh  / script_nbody.sh    End-to-end runners (course deliverable)
prompt.txt                              AI-tool prompt log (course deliverable)
project_instructions.pdf / .md          Course assignment handout (+ text transcription)
tools/log_prompt_hook.py                Claude Code hook: auto-appends session prompts to prompt.txt
.claude/                                Claude Code project config: hook wiring + skills (log-prompt,
                                        and a subset of mattpocock/skills: grilling, teach, research, ...)
skills-lock.json                        Pinned sources/hashes of the imported skills (`npx skills update`)
benchmarks/
  MANIFEST                              pyperformance custom-benchmark manifest
  bm_pyflate/                           Benchmark copy — optimizations land here
  bm_nbody/                             Benchmark copy — optimizations land here
hw/                                     Hardware accelerator designs (Verilog/SystemVerilog)
rust/                                   Rust/PyO3 acceleration crates (stage-2 optimizations)
results/                                Measured data: pyperf JSONs, perf reports, flame graphs
```

`benchmarks/bm_*` start as byte-identical copies of the stock pyperformance
1.14.0 benchmarks (see git history); every optimization is a visible diff
against that baseline. The `[tool.pyperformance] name` fields are kept
identical to the stock names so `pyperf compare_to` lines up before/after.

## How to reproduce

Everything runs inside the course QEMU VM (Ubuntu 22.04, Python 3.10.12,
python3-dbg, perf, pyperformance 1.14.0):

```bash
./script_pyflate.sh all     # setup -> baseline -> profile+flamegraph -> optimized -> compare
./script_nbody.sh all
```

Stages can be run individually: `setup | baseline | profile | optimized | compare`.

- **Baseline** = stock benchmark via `pyperformance run --rigorous`.
- **Optimized** = this repo's `benchmarks/` via `--manifest benchmarks/MANIFEST`
  (same benchmark names, so the comparison matches by name).
- **Evidence** = `results/compare_<bench>.txt`: mean ± std dev for both runs,
  the speedup factor, and pyperf's t-test significance verdict.

### Measurement notes (KVM guest quirks)

- `perf record` must use `-e cpu-clock` — the guest's `cycles` PMU event
  records zero samples. `perf stat` counts at most 4 events per pass.
- Timings are always measured on release `python3`; profiles are taken with
  `python3-dbg` for symbols (debug build is ~2.5-3x slower and distorts the
  profile — it is never used for quoted numbers).
- `kernel.perf_event_paranoid=-1` must be re-applied after a VM reboot
  (`script_*.sh setup` does this).
