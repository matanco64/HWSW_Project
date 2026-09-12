#!/usr/bin/env bash
# Re-record every profile the reports cite, from one revision, through the
# documented profile stage. Runs from the root of a `git archive` copy with a
# REVISION file. Nothing outside that copy is modified.
set -uo pipefail
ROOT="$(pwd)"
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
OUT="$ROOT/results/runs/profiles_$(date -u +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"
cp REVISION "$OUT/REVISION"
cp "$0" "$OUT/driver.sh"
ln -sfn "$OUT" "$HOME/hwsw-profiles-latest"
: > "$OUT/steps.tsv"

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
log "revision $(cat REVISION) on $(hostname)"

# perf C-frame captures, py-spy recordings and perf stat, both sides, backend
# pinned to Python -- exactly the documented `profile` stage.
step profile env HWSW_RESULTS="$OUT/suite" STAGES=profile ./tools/vm_run_all.sh nbody pyflate

# The reports read flamegraph.pl renderings of the folded stacks (*_full.svg);
# py-spy's own SVG uses percentage coordinates the figure tooling does not parse.
# Remove the direct py-spy SVGs so the remake records raw stacks and renders them
# the same way as the preserved figures.
rm -f "$OUT"/suite/pyspy_*.svg
step remake env HWSW_RESULTS="$OUT/suite" ./tools/vm_remake_flames.sh

python3 - "$OUT" > "$OUT/provenance.json" 2>&1 <<'EOF'
import hashlib, json, os, subprocess, sys
import pyperformance
out = sys.argv[1]
root = os.getcwd()

def sha(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()

def cmd(*c):
    try:
        return subprocess.run(c, capture_output=True, text=True).stdout.strip().splitlines()[0]
    except Exception as exc:
        return "unavailable (%s)" % exc

stock = os.path.join(os.path.dirname(pyperformance.__file__), "data-files", "benchmarks")
print(json.dumps({
    "revision": open(os.path.join(root, "REVISION")).read().strip(),
    "benchmark_sha256": {b: sha(os.path.join(root, "benchmarks", "bm_" + b, "run_benchmark.py"))
                         for b in ("nbody", "pyflate")},
    "stock_sha256": {b: sha(os.path.join(stock, "bm_" + b, "run_benchmark.py"))
                     for b in ("nbody", "pyflate")},
    "python3_dbg": cmd("python3-dbg", "-V"),
    "perf": cmd("perf", "--version"),
    "py_spy": cmd(os.path.expanduser("~/.local/bin/py-spy"), "--version"),
    "flamegraph_commit": cmd("git", "-C", os.path.expanduser("~/FlameGraph"), "rev-parse", "HEAD"),
    "protocol": ("perf record -F 999 --call-graph dwarf,16384 -e cpu-clock on python3-dbg; "
                 "py-spy record -f raw on release python3; HWSW_BACKEND=python for every "
                 "recording; stacks rendered with FlameGraph's flamegraph.pl"),
}, indent=2))
EOF

log "=== steps ==="
column -t "$OUT/steps.tsv" | tee -a "$OUT/driver.log"
date -u +%FT%TZ > "$OUT/DONE"
log "=== profiles complete: $OUT ==="
