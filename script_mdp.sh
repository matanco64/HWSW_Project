#!/usr/bin/env bash
# HWSW final project — mdp: setup, baseline, profiling + flame graph, optimized run, comparison.
# Run INSIDE the course QEMU VM (Ubuntu 22.04, python3.10). Stages are selectable:
#   ./script_mdp.sh setup|baseline|profile|optimized|compare|all
set -euo pipefail
BENCH=mdp
ROOT="$(cd "$(dirname "$0")" && pwd)"
RES="$ROOT/results"
BM_STOCK="/usr/local/lib/python3.10/dist-packages/pyperformance/data-files/benchmarks/bm_$BENCH"
mkdir -p "$RES"

setup() {
    sudo apt-get install -y python3-dbg linux-tools-generic git >/dev/null || true
    [ -d "$HOME/FlameGraph" ] || git clone --depth 1 https://github.com/brendangregg/FlameGraph "$HOME/FlameGraph"
    # KVM guest quirks: allow perf sampling; NOTE not persisted across VM reboots.
    sudo sysctl -w kernel.perf_event_paranoid=-1 kernel.kptr_restrict=0
    sudo python3 -m pyperf system tune || true
}

baseline() {
    # Stock benchmark, release python3, full rigor — the "before" evidence.
    # pyperformance aborts if the output file exists; clear any stale one so the
    # stage is re-runnable.
    rm -f "$RES/baseline_$BENCH.json"
    python3 -m pyperformance run --rigorous -b "$BENCH" -o "$RES/baseline_$BENCH.json"
    python3 -m pyperf stats "$RES/baseline_$BENCH.json" | tee "$RES/baseline_${BENCH}_stats.txt"
}

_profile_one() {
    # $1 = tag (stock|opt), $2 = run_benchmark.py to profile.
    # Same flags for both sides so the two flame graphs are directly comparable.
    # --call-graph dwarf, NOT -g: Ubuntu's python3-dbg has no frame pointers, so
    # frame-pointer unwinding walks into freed memory and yields chains of
    # 0xfdfdfd.. (Py_DEBUG fill bytes) -- an unusable flame graph.
    perf record -F 999 --call-graph dwarf,16384 -e cpu-clock -o "$RES/${BENCH}_$1.perf.data" -- \
        python3-dbg "$2" --worker -l1 -w0 -n2
    perf report --stdio -i "$RES/${BENCH}_$1.perf.data" > "$RES/perf_report_${BENCH}_$1.txt"
    perf script -i "$RES/${BENCH}_$1.perf.data" \
        | "$HOME/FlameGraph/stackcollapse-perf.pl" \
        | "$HOME/FlameGraph/flamegraph.pl" --title "$BENCH ($1, python3-dbg)" \
        > "$RES/flame_${BENCH}_$1.svg"
    # Python-level flame graph. CPython 3.10 has no -X perf trampoline, so perf
    # can only ever show C frames; py-spy samples the interpreter frame stack
    # and names the actual Python functions.
    PYSPY="$(command -v py-spy || echo "$HOME/.local/bin/py-spy")"
    if [ -x "$PYSPY" ]; then
        sudo "$PYSPY" record -f flamegraph -o "$RES/pyspy_${BENCH}_$1.svg" -- python3 "$2" --worker -l1 -w0 -n2 || echo "py-spy failed ($1), non-fatal"
    fi
    # Hardware counters on release python3 (guest PMU counts <=4 events per pass).
    { perf stat -e cycles:u,instructions:u -- python3 "$2" --fast 2>&1 | tail -20
      perf stat -e cache-references,cache-misses,branches,branch-misses -- python3 "$2" --fast 2>&1 | tail -20
    } > "$RES/perf_stat_${BENCH}_$1.txt"
}

profile() {
    # Profile shape with python3-dbg (symbols); timings here are NOT quotable.
    # KVM guest: the 'cycles' PMU event records zero samples — MUST use -e cpu-clock.
    # NOTE: 'pyperf system tune' (setup) sets perf_event_max_sample_rate=1, which
    # throttles perf record to 1 Hz — restore a usable rate before recording.
    sudo sysctl -w kernel.perf_event_max_sample_rate=100000 \
                  kernel.perf_event_paranoid=-1 kernel.kptr_restrict=0
    # Both sides: 'stock' is the Initial Analysis evidence, 'opt' shows the
    # hotspot actually moving after the optimizations.
    _profile_one stock "$BM_STOCK/run_benchmark.py"
    _profile_one opt   "$ROOT/benchmarks/bm_$BENCH/run_benchmark.py"
}

optimized() {
    # Our modified benchmark from benchmarks/ via custom manifest (same benchmark name).
    rm -f "$RES/optimized_$BENCH.json"
    python3 -m pyperformance run --rigorous --manifest "$ROOT/benchmarks/MANIFEST" \
        -b "$BENCH" -o "$RES/optimized_$BENCH.json"
}

compare() {
    python3 -m pyperf compare_to "$RES/baseline_$BENCH.json" "$RES/optimized_$BENCH.json" \
        --table | tee "$RES/compare_$BENCH.txt"
}

case "${1:-all}" in
    setup) setup ;;
    baseline) baseline ;;
    profile) profile ;;
    optimized) optimized ;;
    compare) compare ;;
    all) setup; baseline; profile; optimized; compare ;;
    *) echo "usage: $0 setup|baseline|profile|optimized|compare|all"; exit 1 ;;
esac
