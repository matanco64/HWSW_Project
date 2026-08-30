#!/usr/bin/env bash
# Record Python-level flame graphs with py-spy, for the two submitted benchmarks.
#
# Why this exists separately from script_<bench>.sh profile:
#   perf can only ever show C frames here -- CPython 3.10 has no -X perf
#   trampoline (that landed in 3.12) -- so the perf flame graph is a tower of
#   _PyEval_EvalFrameDefault with the Python call structure invisible. py-spy
#   samples the interpreter's own frame stack and names the Python functions,
#   which is the readable half of the story.
#
# Run ON the VM.  Cheap: seconds per recording, versus ~20-35 min for a DWARF
# perf capture, so it is worth re-running on its own rather than redoing perf.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RES="$ROOT/results"
PYSPY="$(command -v py-spy || echo "$HOME/.local/bin/py-spy")"
mkdir -p "$RES"

[ -x "$PYSPY" ] || { echo "py-spy not found (pip3 install --user py-spy)" >&2; exit 1; }

# bench:stock_path:opt_path:flags
STOCK_ROOT=/usr/local/lib/python3.10/dist-packages/pyperformance/data-files/benchmarks

record() {
    local bench="$1" tag="$2" script="$3" flags="$4"
    local out="$RES/pyspy_${bench}_${tag}.svg"
    echo "=== py-spy $bench/$tag ==="
    # sudo: py-spy needs ptrace on the child it spawns.
    if sudo "$PYSPY" record -f flamegraph --nonblocking -o "$out" -- python3 "$script" $flags; then
        echo "wrote $out ($(stat -c%s "$out") bytes)"
    else
        echo "FAILED $bench/$tag" >&2
    fi
}

for bench in nbody pyflate; do
    case "$bench" in
        nbody)   flags="--worker -l2 -w0 -n6" ;;
        pyflate) flags="--worker -l1 -w0 -n3" ;;
    esac
    record "$bench" stock "$STOCK_ROOT/bm_$bench/run_benchmark.py" "$flags"
    record "$bench" opt   "$ROOT/benchmarks/bm_$bench/run_benchmark.py" "$flags"
done

echo "=== done ==="
ls -la "$RES"/pyspy_*.svg 2>/dev/null | awk '{print $5, $9}'
