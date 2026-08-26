#!/usr/bin/env bash
# Non-rigorous pyperf A/B for the nbody tiers.  Relative ordering only --
# the final rigorous run is done separately on a quiet machine.
#
#   bash dev/nbody/measure_ab.sh [PYTHON] [PYPERF_FLAG]
#
# Defaults to the WSL py310 venv and --fast.
set -euo pipefail

PY="${1:-/root/hwsw-env/py310/bin/python}"
FLAG="${2:---fast}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${OUT:-/tmp/nbody_ab}"
mkdir -p "$OUT"

STOCK=$("$PY" -c 'import pyperformance, os; print(os.path.join(os.path.dirname(pyperformance.__file__), "data-files", "benchmarks", "bm_nbody", "run_benchmark.py"))')
echo "python : $("$PY" -c 'import sys; print(sys.version.split()[0])')"
echo "flag   : $FLAG"
echo "stock  : $STOCK"
echo

"$PY" "$STOCK"                                  "$FLAG" -o "$OUT/stock.json"    2>&1 | tail -2
"$PY" "$ROOT/benchmarks/bm_nbody/run_benchmark.py" "$FLAG" -o "$OUT/opt.json"   2>&1 | tail -2
"$PY" "$ROOT/dev/nbody/run_benchmark_sqrt.py"   "$FLAG" -o "$OUT/opt_sqrt.json" 2>&1 | tail -2

echo
echo "=== stock vs opt (bit-exact, shipped) ==="
"$PY" -m pyperf compare_to "$OUT/stock.json" "$OUT/opt.json" --table
echo
echo "=== stock vs opt (sqrt variant, not shipped) ==="
"$PY" -m pyperf compare_to "$OUT/stock.json" "$OUT/opt_sqrt.json" --table