#!/usr/bin/env bash
# Regenerate the flame graphs from captures that already exist, trimming the
# common interpreter prefix so the interesting band is not pushed off the page.
#
# Run ON the VM. Does NOT re-record: `perf record` with DWARF took 20-36 min per
# benchmark, whereas re-folding an existing .perf.data is minutes and re-running
# py-spy is seconds.
#
# For each graph we keep both:
#   flame_<b>_<t>.svg       trimmed  -- the figure that goes in the report
#   flame_<b>_<t>_full.svg  untrimmed -- the honest full-depth artifact
# and the .folded files, which are small and make future re-plots instant.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RES="$ROOT/results"
FG="$HOME/FlameGraph"
PYSPY="$(command -v py-spy || echo "$HOME/.local/bin/py-spy")"
STOCK_ROOT=/usr/local/lib/python3.10/dist-packages/pyperformance/data-files/benchmarks
mkdir -p "$RES/folded"

plot() {  # $1 folded file, $2 out svg, $3 title
    "$FG/flamegraph.pl" --title "$3" "$1" > "$2" && echo "  wrote $(basename "$2")"
}

trim_and_plot() {  # $1 folded, $2 basename, $3 title
    local trimmed="$RES/folded/$2.trimmed.folded"
    python3 "$ROOT/tools/trim_folded.py" "$1" "$trimmed" | sed 's/^/  /'
    plot "$1"       "$RES/$2_full.svg" "$3 (full depth)"
    plot "$trimmed" "$RES/$2.svg"      "$3"
}

for bench in nbody pyflate; do
    case "$bench" in
        nbody)   flags="--worker -l2 -w0 -n6" ;;
        pyflate) flags="--worker -l1 -w0 -n3" ;;
    esac
    for tag in stock opt; do
        case "$tag" in
            stock) script="$STOCK_ROOT/bm_$bench/run_benchmark.py" ;;
            opt)   script="$ROOT/benchmarks/bm_$bench/run_benchmark.py" ;;
        esac

        # --- perf (C-level) -------------------------------------------------
        data="$RES/${bench}_${tag}.perf.data"
        if [ -f "$data" ]; then
            folded="$RES/folded/flame_${bench}_${tag}.folded"
            echo "=== perf $bench/$tag (folding $(du -h "$data" | cut -f1)) ==="
            if [ ! -s "$folded" ]; then
                perf script -i "$data" 2>/dev/null | "$FG/stackcollapse-perf.pl" > "$folded"
            else
                echo "  reusing existing folded"
            fi
            trim_and_plot "$folded" "flame_${bench}_${tag}" "$bench ($tag, perf/python3-dbg)"
        else
            echo "=== perf $bench/$tag: no capture, skipping ==="
        fi

        # --- py-spy (Python-level) ------------------------------------------
        if [ -x "$PYSPY" ]; then
            echo "=== py-spy $bench/$tag ==="
            raw="$RES/folded/pyspy_${bench}_${tag}.folded"
            sudo "$PYSPY" record -f raw -o "$raw" -- python3 "$script" $flags >/dev/null 2>&1 \
                && trim_and_plot "$raw" "pyspy_${bench}_${tag}" "$bench ($tag, py-spy/Python frames)" \
                || echo "  py-spy failed, skipping"
        fi
    done
done

echo "=== done ==="
ls -la "$RES"/flame_*.svg "$RES"/pyspy_*.svg 2>/dev/null | awk '{print $5, $9}'
