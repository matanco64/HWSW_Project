#!/usr/bin/env bash
# HWSW final project — pyflate: setup, baseline, profiling + flame graph,
# optimized run, wheel build, native comparison.
#
# Run INSIDE the course QEMU VM (Ubuntu 22.04, python3.10). Stages:
#   ./script_pyflate.sh setup|baseline|profile|optimized|compare|wheel|native|all
#
# Every stage is implemented once, in tools/runner_common.sh; this file is the
# pyflate configuration of it. The runners previously held three copies of the
# same logic and drifted apart in ways that changed what got measured.
#
# Results land in results/runs/<UTC stamp>_pyflate/ (results/runs/latest points
# at the current one), never on top of the preserved captures in results/.
# HWSW_RESULTS=<dir> overrides the destination.
BENCH=pyflate
PROFILE_LOOPS=1          # profile workload: -l1 -w0 -n3 (one decode is ~0.3 s)
PROFILE_VALUES=3
. "$(dirname "$0")/tools/runner_common.sh"
run_stage "$@"
