# Inverse BWT in Rust, course VM, 2026-10-05

**Post-submission experiment, branch `experiment/bwt-rust` only.** Write-up: `report_bwt_rust.md`.

Course VM (Xeon E5-2630 v3, CPython 3.10.12), everything pinned with `taskset -c 0`.
The submitted `pyflate_rs` in the system Python was left untouched; the experimental
build was unpacked into `/tmp/bwt_exp/site` and loaded through `PYTHONPATH`.

| File | Contents |
|---|---|
| `run_vm.sh` | The full run: build, correctness check, stage split, kernels, phases, pyperf. |
| `run.log` | Build, the 10-input correctness check (all OK), stage split submitted vs experiment (159.5 → 16.6 ms). Stopped at the kernel step: the capture scripts hooked the Python `bwt_reverse`, which the new default path no longer calls. |
| `rest.log` | Kernel timings after that fix (commit cd9730c, scripts only): Python 124.5 ms, Rust port 6.07, packed 5.04, two chains 3.91, RLE4 23.3 → 0.74 ms. Stopped at the phase step (`rustc` not on PATH). |
| `rest2.log` | Phase split (histogram 0.24, build 0.84, walk 2.64 ms; two-steps-per-lookup slower) and pyperf: **161 ms → 14.6 ms, 11.06x**. The script exits after the comparison table on a `grep` with no match; nothing was skipped. |
| `pf_submitted.json`, `pf_experiment.json` | pyperf results. `hwsw_native_module` in the metadata shows which `pyflate_rs` each run loaded. |
| `phases_ends.txt` | BWT end pointers of the two blocks used by the phase split. |

The code under test is the same in all three logs (commit 2a00336); cd9730c changed only the
capture scripts.
