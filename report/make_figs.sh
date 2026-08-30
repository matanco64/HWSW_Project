#!/usr/bin/env bash
# Rasterize the perf flame graphs into PNGs for the Typst reports.
#
# Typst can embed SVG, but flamegraph.pl output relies on font metrics and
# embedded JS that renderers handle inconsistently; rasterizing once here keeps
# the report build deterministic. Run inside WSL (needs rsvg-convert:
# apt-get install librsvg2-bin). Re-run whenever the profiles are re-recorded.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
RES="$HERE/../results"
OUT="$HERE/fig"
WIDTH="${WIDTH:-2400}"   # px; flame graphs are wide, so oversample for print

mkdir -p "$OUT"
for bench in nbody pyflate mdp; do
    for tag in stock opt; do
        src="$RES/flame_${bench}_${tag}.svg"
        [ -f "$src" ] || { echo "skip (missing): $(basename "$src")"; continue; }
        dst="$OUT/flame_${bench}_${tag}.png"
        rsvg-convert -w "$WIDTH" "$src" -o "$dst"
        echo "wrote $(basename "$dst")  $(stat -c%s "$dst") bytes"
    done
done
