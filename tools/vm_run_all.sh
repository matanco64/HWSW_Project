#!/usr/bin/env bash
# Run the full measurement suite for every benchmark on the course VM, detached.
#
# Designed to survive a dropped SSH connection: launch it with `vm_launch.sh`
# (or by hand under tmux/setsid) and it keeps running with nobody attached.
#
#   ./tools/vm_run_all.sh              # all benchmarks, all stages
#   ./tools/vm_run_all.sh nbody mdp    # only these
#   FORCE=1 ./tools/vm_run_all.sh      # re-run stages already marked done
#
# Resumable: each finished stage drops a marker in results/.stamps/, so a
# re-run after a crash, reboot or Ctrl-C picks up where it stopped instead of
# repeating hours of --rigorous runs. Delete a stamp to redo just that stage.
#
# Deliberately NOT `set -e`: one benchmark failing must not abort the others.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RES="$ROOT/results"
STAMPS="$RES/.stamps"
LOG="$ROOT/vm_run.log"
mkdir -p "$RES" "$STAMPS"

BENCHES=("$@")
[ ${#BENCHES[@]} -eq 0 ] && BENCHES=(nbody pyflate mdp)

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }

# The artifact each stage must have produced. A stamp on its own is not proof:
# results/ can be cleaned or archived out from under us, and skipping a stage
# whose output has since vanished silently leaves a gap (or worse, lets a later
# stage consume a stale file from a previous session).
stage_artifact() {
    case "$2" in
        baseline)  echo "$RES/baseline_$1.json" ;;
        profile)   echo "$RES/perf_report_$1.txt" ;;
        optimized) echo "$RES/optimized_$1.json" ;;
        compare)   echo "$RES/compare_$1.txt" ;;
        *)         echo "" ;;
    esac
}

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
    local t0=$SECONDS
    if "$ROOT/script_${bench}.sh" "$stage"; then
        date -u +%FT%TZ > "$stamp"
        log "OK    $bench/$stage ($((SECONDS - t0))s)"
    else
        log "FAIL  $bench/$stage (exit $?) — continuing"
        return 1
    fi
}

log "=== run starting on $(hostname), $(python3 -VV 2>&1 | head -1) ==="
log "benchmarks: ${BENCHES[*]}"

# `setup` touches sysctls and apt; do it once rather than per benchmark.
if [ ! -f "$STAMPS/_setup" ] || [ -n "${FORCE:-}" ]; then
    log "START setup"
    "$ROOT/script_${BENCHES[0]}.sh" setup && date -u +%FT%TZ > "$STAMPS/_setup" \
        && log "OK    setup" || log "FAIL  setup — continuing anyway"
fi

for bench in "${BENCHES[@]}"; do
    if [ ! -x "$ROOT/script_${bench}.sh" ]; then
        log "SKIP  $bench (no script_${bench}.sh)"
        continue
    fi
    for stage in baseline profile optimized compare; do
        run_stage "$bench" "$stage"
    done
done

log "=== summary ==="
for bench in "${BENCHES[@]}"; do
    f="$RES/compare_${bench}.txt"
    if [ -f "$f" ]; then
        echo "--- $bench ---"
        cat "$f"
    else
        echo "--- $bench: no comparison produced ---"
    fi
done

date -u +%FT%TZ > "$RES/.RUN_DONE"
log "=== all done; marker written to results/.RUN_DONE ==="
