#!/usr/bin/env bash
# Runs on the VM after vm_rerun.sh has finished, so nothing here overlaps a
# rigorous timing run. Appends to the same run directory and steps.tsv.
set -uo pipefail
OUT="$(readlink -f "$HOME/hwsw-rerun-latest")"
FIX="$HOME/hwsw-rerun-79a0d12"
ORIG="$HOME/hwsw-rerun-3697a63"

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*" | tee -a "$OUT/driver.log"; }
step() {
    local name="$1" dir="$2"; shift 2
    log "START $name (in $(basename "$dir")): $*"
    local t0=$SECONDS rc=0
    ( cd "$dir" && "$@" ) > "$OUT/$name.log" 2>&1 || rc=$?
    printf '%s\t%s\t%ss\n' "$name" "$rc" "$((SECONDS - t0))" >> "$OUT/steps.tsv"
    log "END   $name rc=$rc ($((SECONDS - t0))s)"
}

# The --bodies failure at 3697a63 was the oracle calling a stale kernel with
# nbody_rs installed; 79a0d12 pins the Python backend while loading. Same host,
# same installed wheel, so this is the direct before/after.
step verify_nbody_79a0d12        "$FIX" python3 dev/nbody/verify.py --steps 20000
step verify_nbody_bodies_79a0d12 "$FIX" python3 dev/nbody/verify.py --steps 2000 --bodies 5,10,20

# A second, independent ablation trial on the same CPU: the first one changed a
# report conclusion, so it should be shown to reproduce before it is quoted.
step ablation_pyflate_trial2 "$ORIG" taskset -c 0 python3 dev/pyflate/ablate.py -r 7

cp "$0" "$OUT/post_suite.sh"
date -u +%FT%TZ > "$OUT/POST_DONE"
log "=== post-suite complete ==="
