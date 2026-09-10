#!/usr/bin/env bash
# Regenerate the flame graphs from captures that already exist, trimming them
# so the interesting band is not squeezed into the bottom of the figure.
#
# Run ON the VM. Does NOT re-record: `perf record` with DWARF took 20-36 min per
# benchmark, whereas re-folding an existing .perf.data is minutes. The py-spy
# folded files are reused too when present, so the figures stay consistent with
# the numbers already quoted in the reports.
#
# For each graph we keep both:
#   flame_<b>_<t>.svg       trimmed   -- the figure that goes in the report
#   flame_<b>_<t>_full.svg  untrimmed -- the honest full-depth artifact
# and the .folded files, which are small and make future re-plots instant.
#
# Trimming differs by profiler, because the height comes from different noise:
#
#   py-spy   samples taken while CPython was still importing `re`, `enum`,
#            `collections`... py-spy starts at process start, the benchmark
#            loop has not been entered yet. 1.6-6.7% of samples, and they are
#            what takes pyflate from depth 15 to depth 60. Default trim drops
#            exactly those. The shared prefix is KEPT -- it is the call path
#            (bench_nbody -> advance) the figure exists to show.
#
#   perf     C-level, starts at depth ~173: interpreter startup plus the nested
#            _PyEval_EvalFrameDefault ladder, and `perf script` interleaves
#            stray samples from other processes (`uname`, `file`). Here the
#            common prefix really is noise, so --prefix --dominant-root.
#            --min-share 0.95, not the 0.99 default: about 1.7% of samples are
#            partial DWARF unwinds that start mid-interpreter, and at 0.99 those
#            few fragments block the trim entirely (176 -> 168 rows). At 0.95 the
#            real shared prefix comes out: 104 frames of interpreter start-up and
#            pyperf harness, 176 -> 72 rows. 0.90 buys one more row, so 0.95 is
#            the knee, not a number picked to flatter the figure.
#            --cap 0.95 on top of that: even after the prefix goes, a thin
#            tower of deep stacks keeps the figure ~1250px tall, which is still
#            most of a page. Capping merges the tips of 4.4% of samples and
#            brings pyflate to 36 rows and nbody to 9. Unlike the prefix trim
#            this one does discard information, so the figure captions state
#            the cut depth and the truncated share, and the _full.svg beside it
#            keeps the uncut graph.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RES="$ROOT/results"
FG="$HOME/FlameGraph"
PYSPY="$(command -v py-spy || echo "$HOME/.local/bin/py-spy")"
# The stock benchmarks are found through the installed pyperformance, not a
# hard-coded dist-packages path -- the same rule as tools/runner_common.sh.
STOCK_ROOT="$(python3 -c 'import os, pyperformance; print(os.path.join(os.path.dirname(pyperformance.__file__), "data-files", "benchmarks"))' 2>/dev/null)"
[ -d "$STOCK_ROOT" ] || { echo "cannot locate pyperformance's stock benchmarks for python3" >&2; exit 1; }
mkdir -p "$RES/folded"

plot() {  # $1 folded file, $2 out svg, $3 title
    "$FG/flamegraph.pl" --title "$3" "$1" > "$2" && echo "  wrote $(basename "$2")"
}

# $1 folded, $2 basename, $3 title, rest: flags for trim_folded.py
trim_and_plot() {
    local folded="$1" base="$2" title="$3"; shift 3
    local trimmed="$RES/folded/$base.trimmed.folded"
    python3 "$ROOT/tools/trim_folded.py" "$@" "$folded" "$trimmed" 2>&1 | sed 's/^/  /'
    plot "$folded"  "$RES/${base}_full.svg" "$title (full depth)"
    plot "$trimmed" "$RES/$base.svg"        "$title"
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
            echo "=== perf $bench/$tag (from $(du -h "$data" | cut -f1) capture) ==="
            if [ ! -s "$folded" ]; then
                perf script -i "$data" 2>/dev/null | "$FG/stackcollapse-perf.pl" > "$folded"
            else
                echo "  reusing existing folded"
            fi
            trim_and_plot "$folded" "flame_${bench}_${tag}" \
                "$bench ($tag, perf / C frames)"                 --dominant-root --prefix --min-share 0.95 --cap 0.95
        else
            echo "=== perf $bench/$tag: no capture, skipping ==="
        fi

        # --- py-spy (Python-level) ------------------------------------------
        if [ -x "$PYSPY" ]; then
            echo "=== py-spy $bench/$tag ==="
            raw="$RES/folded/pyspy_${bench}_${tag}.folded"
            if [ ! -s "$raw" ]; then
                # Backend pinned inside sudo, which resets the environment.
                sudo env HWSW_BACKEND=python "$PYSPY" record -f raw -o "$raw" -- python3 "$script" $flags \
                    >/dev/null 2>&1 || { echo "  py-spy failed, skipping"; continue; }
            else
                echo "  reusing existing folded"
            fi
            trim_and_plot "$raw" "pyspy_${bench}_${tag}" \
                "$bench ($tag, py-spy / Python frames)"
        fi
    done
done

echo "=== done ==="
ls -la "$RES"/flame_*.svg "$RES"/pyspy_*.svg 2>/dev/null | awk '{print $5, $9}'
