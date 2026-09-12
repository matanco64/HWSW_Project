#!/usr/bin/env bash
# One-off verification of a committed revision on the course VM.
#
# Runs from the root of an isolated `git archive` copy of that revision, with a
# REVISION file beside it. It never touches ~/hwsw-project. It DOES replace the
# system-installed nbody_rs / pyflate_rs with wheels built from this revision
# (that is what the wheel stage is for), so the currently installed packages are
# copied to ~/wheel_backup_<stamp>/ first.
set -uo pipefail
ROOT="$(pwd)"
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
STAMP="$(date -u +%Y%m%d_%H%M%S)"
OUT="$ROOT/results/runs/vm_rerun_$STAMP"
mkdir -p "$OUT"
cp "$0" "$OUT/driver.sh"
cp REVISION "$OUT/REVISION"
: > "$OUT/steps.tsv"
ln -sfn "$OUT" "$HOME/hwsw-rerun-latest"

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*" | tee -a "$OUT/driver.log"; }
step() {
    local name="$1"; shift
    log "START $name: $*"
    local t0=$SECONDS rc=0
    "$@" > "$OUT/$name.log" 2>&1 || rc=$?
    printf '%s\t%s\t%ss\n' "$name" "$rc" "$((SECONDS - t0))" >> "$OUT/steps.tsv"
    log "END   $name rc=$rc ($((SECONDS - t0))s)"
}

chmod +x script_*.sh tools/*.sh
log "revision $(cat REVISION) on $(hostname), $(python3 -V 2>&1)"

# ---- 0. preserve what is installed before the wheel stage replaces it -------
BK="$HOME/wheel_backup_$STAMP"
mkdir -p "$BK"
SITE=/usr/local/lib/python3.10/dist-packages
for m in nbody_rs pyflate_rs; do
    sudo cp -a "$SITE/$m" "$BK/" 2>/dev/null
    sudo cp -a "$SITE"/${m}-*.dist-info "$BK/" 2>/dev/null
done
sudo chown -R "$(id -u):$(id -g)" "$BK"
( cd "$BK" && sha256sum */*.so ) > "$OUT/installed_before.sha256" 2>&1
ls -la "$HOME/.local/lib/python3.10/site-packages" 2>/dev/null | grep -i '_rs' \
    > "$OUT/user_site_rs_before.txt" || true
log "backed up installed extensions to $BK"

# ---- 1. correctness contracts (pure Python) --------------------------------
step verify_nbody        python3 dev/nbody/verify.py --steps 20000
step verify_nbody_bodies python3 dev/nbody/verify.py --steps 2000 --bodies 5,10,20

# ---- 2. the causal-evidence ablation, on the VM interpreter ----------------
CPU="$(python3 -c 'import os; print(min(os.sched_getaffinity(0)))')"
step ablation_pyflate    taskset -c "$CPU" python3 dev/pyflate/ablate.py -r 7

# ---- 3. the full reproduction route through the runner scripts -------------
step suite env HWSW_RESULTS="$OUT/suite" ./tools/vm_run_all.sh nbody pyflate

# ---- 4. native correctness against the wheels the suite just installed ------
step rs_check_nbody      python3 dev/nbody/rs_check.py
step rs_check_pyflate    python3 dev/pyflate/rs_check.py

# ---- 5. summaries over this run's own JSONs ---------------------------------
S="$OUT/suite"
step distributions python3 report/summarize_distribution.py \
    --json "$OUT/timing_distributions.json" \
    "$S/baseline_nbody.json" "$S/optimized_nbody.json" \
    "$S/fallback_nbody.json" "$S/native_nbody.json" \
    "$S/baseline_pyflate.json" "$S/optimized_pyflate.json" \
    "$S/fallback_pyflate.json" "$S/native_pyflate.json"

python3 - "$SITE" > "$OUT/installed_after.txt" 2>&1 <<'EOF'
import hashlib, importlib.machinery, os, sys
sfx = tuple(importlib.machinery.EXTENSION_SUFFIXES)
for m in ("nbody_rs", "pyflate_rs"):
    mod = __import__(m)
    d = os.path.dirname(mod.__file__)
    for fn in sorted(os.listdir(d)):
        if fn.endswith(sfx):
            p = os.path.join(d, fn)
            print(hashlib.sha256(open(p, "rb").read()).hexdigest(), p)
EOF

log "=== steps ==="
column -t "$OUT/steps.tsv" | tee -a "$OUT/driver.log"
date -u +%FT%TZ > "$OUT/DONE"
log "=== driver complete: $OUT ==="
