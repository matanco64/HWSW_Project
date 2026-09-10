#!/usr/bin/env bash
# HWSW final project — nbody: setup, baseline, profiling + flame graph,
# optimized run, wheel build, native comparison.
#
# Run INSIDE the course QEMU VM (Ubuntu 22.04, python3.10). Stages:
#   ./script_nbody.sh setup|baseline|profile|optimized|compare|wheel|native|all
#
# Every stage is implemented once, in tools/runner_common.sh; this file is the
# nbody configuration of it. The runners previously held three copies of the
# same logic and drifted apart in ways that changed what got measured.
#
# Results land in results/runs/<UTC stamp>_nbody/ (results/runs/latest points
# at the current one), never on top of the preserved captures in results/.
# HWSW_RESULTS=<dir> overrides the destination.
BENCH=nbody
PROFILE_LOOPS=2          # profile workload: -l2 -w0 -n6
PROFILE_VALUES=6
. "$(dirname "$0")/tools/runner_common.sh"
run_stage "$@"
