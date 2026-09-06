#!/usr/bin/env bash
# pyperf A/B of stock vs optimized at a given --bodies N.
#
# Iterations are scaled so every N does the same total pair-updates as the
# stock benchmark does at its own N = 5 (20,000 steps x 10 pairs = 200,000),
# and the SAME count is given to both sides, so the comparison is exact.
#
#     bash dev/nbody/measure_ab_n.sh [python] [--fast|--rigorous] N [N...]
#
# Defaults: the WSL py310 venv, --fast, N = 5.
set -euo pipefail
cd "$(dirname "$0")"

PY="${1:-/root/hwsw-env/py310/bin/python}"; shift || true
MODE="${1:---fast}"; shift || true
NS=("$@"); [ ${#NS[@]} -eq 0 ] && NS=(5)

OPT=../../benchmarks/bm_nbody/run_benchmark.py
OUT="${OUT:-/tmp/nbody_ab_n}"
mkdir -p "$OUT"

for N in "${NS[@]}"; do
  PAIRS=$(( N * (N - 1) / 2 ))
  ITERS=$(( 200000 / PAIRS )); [ "$ITERS" -lt 1 ] && ITERS=1
  echo "=== N=$N  pairs=$PAIRS  iterations=$ITERS  ($MODE) ==="
  "$PY" stock_n_benchmark.py "$MODE" --bodies "$N" --iterations "$ITERS" \
        -o "$OUT/stock_$N.json" >/dev/null
  "$PY" "$OPT"                "$MODE" --bodies "$N" --iterations "$ITERS" \
        -o "$OUT/opt_$N.json" >/dev/null
  "$PY" -m pyperf compare_to "$OUT/stock_$N.json" "$OUT/opt_$N.json"
  echo
done
