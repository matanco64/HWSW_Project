#!/usr/bin/env bash
# HWSW final project — mdp: setup, baseline, profiling + flame graph,
# optimized run, comparison.
#
# mdp is the CANDIDATE benchmark, kept as evidence of the selection process; it
# is not part of the submission and has no report and no Rust crate, so it has
# no wheel or native stage.
#
#   ./script_mdp.sh setup|baseline|profile|optimized|compare|all
#
# Every stage is implemented once, in tools/runner_common.sh. Results land in
# results/runs/<UTC stamp>_mdp/; HWSW_RESULTS=<dir> overrides the destination.
BENCH=mdp
HAS_NATIVE=0
PROFILE_LOOPS=1          # profile workload: -l1 -w0 -n2
PROFILE_VALUES=2
. "$(dirname "$0")/tools/runner_common.sh"
run_stage "$@"
