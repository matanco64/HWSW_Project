#!/usr/bin/env bash
# Run the full measurement suite for every benchmark on the course VM, detached.
#
# Designed to survive a dropped SSH connection: launch it with `vm_launch.sh`
# (or by hand under tmux/setsid) and it keeps running with nobody attached.
#
#   ./tools/vm_run_all.sh              # all benchmarks, all stages
#   ./tools/vm_run_all.sh nbody mdp    # only these
#   FORCE=1 ./tools/vm_run_all.sh      # re-run stages already marked done
#   HWSW_RESULTS=<dir> ./tools/vm_run_all.sh   # somewhere other than results/runs/vm
#   STAGES="baseline optimized compare wheel native" ./tools/vm_run_all.sh
#                                      # only these stages (timing without profiling)
#   HWSW_CPU=<n>|none                  # CPU for timed stages (see runner_common.sh)
#
# One results directory for the whole run, shared by every stage of every
# benchmark: results/runs/vm/ by default. It has to be exported, because each
# stage script otherwise opens its own fresh directory under results/runs/ (see
# tools/runner_common.sh) -- which would scatter one run across a dozen
# directories and leave the artifact checks below looking in the wrong place.
# It is a fixed path rather than a timestamp so that a re-run resumes.
#
# Resumable: each finished stage drops a marker in <results>/.stamps/, so a
# re-run after a crash, reboot or Ctrl-C picks up where it stopped instead of
# repeating hours of --rigorous runs. Delete a stamp to redo just that stage.
#
# Deliberately NOT `set -e`: one benchmark failing must not abort the others.
# But a failure is never silent either: failed stages are listed in
# <results>/stages_failed.txt and the exit status is nonzero.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export HWSW_RESULTS="${HWSW_RESULTS:-$ROOT/results/runs/vm}"
RES="$HWSW_RESULTS"
STAMPS="$RES/.stamps"
mkdir -p "$RES" "$STAMPS"
rm -f "$RES/.RUN_DONE" "$RES/stages_failed.txt"

BENCHES=("$@")
[ ${#BENCHES[@]} -eq 0 ] && BENCHES=(nbody pyflate mdp)

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }

# The artifact each stage must have produced. A stamp on its own is not proof:
# results can be cleaned or archived out from under us, and skipping a stage
# whose output has since vanished silently leaves a gap (or worse, lets a later
# stage consume a stale file from a previous session).
stage_artifact() {
    case "$2" in
        baseline)  echo "$RES/baseline_$1.json" ;;
        profile)   echo "$RES/perf_report_$1_stock.txt" ;;
        optimized) echo "$RES/optimized_$1.json" ;;
        compare)   echo "$RES/compare_$1.txt" ;;
        wheel)     echo "$RES/wheel_$1.json" ;;
        native)    echo "$RES/compare_$1_native.txt" ;;
        *)         echo "" ;;
    esac
}

FAILED=0
run_stage() {
    local bench="$1" stage="$2"
    local stamp="$STAMPS/${bench}_${stage}"
    local artifact; artifact="$(stage_artifact "$bench" "$stage")"
    if [ -f "$stamp" ] && [ -z "${FORCE:-}" ]; then
        if [ -z "$artifact" ] || [ -e "$artifact" ]; then
            log "SKIP  $bench/$stage (already done — FORCE=1 to redo)"
            return 0
        fi
        log "REDO  $bench/$stage (stamped, but $(basename "$artifact") is missing)"
        rm -f "$stamp"
    fi
    log "START $bench/$stage"
    local t0=$SECONDS rc=0
    "$ROOT/script_${bench}.sh" "$stage" || rc=$?
    if [ "$rc" -eq 0 ] && { [ -z "$artifact" ] || [ -e "$artifact" ]; }; then
        date -u +%FT%TZ > "$stamp"
        log "OK    $bench/$stage ($((SECONDS - t0))s)"
    else
        [ "$rc" -eq 0 ] && rc="missing $(basename "$artifact")"
        log "FAIL  $bench/$stage ($rc) — continuing"
        echo "$bench/$stage: $rc" >> "$RES/stages_failed.txt"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

log "=== run starting on $(hostname), $(python3 -VV 2>&1 | head -1) ==="
log "benchmarks: ${BENCHES[*]}"
log "results:    $RES"

# `setup` touches sysctls and apt; do it once rather than per benchmark.
if [ ! -f "$STAMPS/_setup" ] || [ -n "${FORCE:-}" ]; then
    log "START setup"
    if "$ROOT/script_${BENCHES[0]}.sh" setup; then
        date -u +%FT%TZ > "$STAMPS/_setup"; log "OK    setup"
    else
        log "FAIL  setup — continuing anyway"
        echo "setup" >> "$RES/stages_failed.txt"; FAILED=$((FAILED + 1))
    fi
fi

for bench in "${BENCHES[@]}"; do
    if [ ! -x "$ROOT/script_${bench}.sh" ]; then
        log "SKIP  $bench (no script_${bench}.sh)"
        continue
    fi
    if [ -n "${STAGES:-}" ]; then
        read -r -a stages <<< "$STAGES"
    else
        stages=(baseline profile optimized compare wheel native)
    fi
    for stage in "${stages[@]}"; do
        # The native tier exists only where there is a crate to build.
        case "$stage" in
            wheel|native)
                if [ ! -d "$ROOT/rust/$bench" ]; then
                    log "SKIP  $bench/$stage (no rust/$bench crate)"
                    continue
                fi ;;
        esac
        run_stage "$bench" "$stage"
    done
done

log "=== summary ==="
for bench in "${BENCHES[@]}"; do
    for f in "$RES/compare_${bench}.txt" "$RES/compare_${bench}_native.txt"; do
        [ "$f" = "$RES/compare_${bench}_native.txt" ] && [ ! -d "$ROOT/rust/$bench" ] && continue
        if [ -f "$f" ]; then
            echo "--- $(basename "$f") ---"
            cat "$f"
        else
            echo "--- $(basename "$f"): not produced ---"
        fi
    done
done

date -u +%FT%TZ > "$RES/.RUN_DONE"
if [ "$FAILED" -ne 0 ]; then
    log "=== done with $FAILED failed stage(s): see $RES/stages_failed.txt ==="
    exit 1
fi
log "=== all done; marker written to $RES/.RUN_DONE ==="
