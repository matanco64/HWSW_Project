#!/usr/bin/env bash
# Back-to-back A/B of stock vs optimized mdp under pyperf.
#   usage: bash dev/mdp/ab.sh [--fast|--rigorous] [python]
# Run from the repo root, after /root/hwsw-env/sync.sh.
set -euo pipefail
MODE="${1:---fast}"
PY="${2:-/root/hwsw-env/py310/bin/python}"
OUT="${OUT:-/tmp}"
"$PY" dev/mdp/stock_benchmark.py "$MODE" -o "$OUT/mdp_base.json" >/dev/null
"$PY" benchmarks/bm_mdp/run_benchmark.py "$MODE" -o "$OUT/mdp_opt.json" >/dev/null
"$PY" -m pyperf compare_to "$OUT/mdp_base.json" "$OUT/mdp_opt.json" --table
