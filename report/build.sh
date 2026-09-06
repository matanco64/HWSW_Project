#!/usr/bin/env bash
# Build the reports with Typst (two benchmark reports + the shared appendix).
#
#   ./build.sh                # build every report_*.typ (all three)
#   ./build.sh report_nbody   # build one (with or without .typ)
#
# Typst is run with --root at the repo root so the sources can reference
# /results/*.svg -- the flame graphs stay in results/ as the single source of
# truth rather than being copied into report/fig/.
#
# Typst embeds the flamegraph.pl and py-spy SVGs directly; no rasterization is
# needed. (Verified by rendering to PNG and looking at it -- an SVG that Typst
# cannot draw still compiles without error, so "it compiled" proves nothing.)
#
# Needs a typst binary. On the WSL dev box it lives at /root/bin/typst; override
# with TYPST=/path/to/typst. Install: https://github.com/typst/typst/releases
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
TYPST="${TYPST:-/root/bin/typst}"

command -v "$TYPST" >/dev/null 2>&1 || [ -x "$TYPST" ] || {
    echo "typst not found at '$TYPST' (set TYPST=...)" >&2; exit 1; }

build_one() {
    local base="${1%.typ}"
    local src="$HERE/$base.typ"
    [ -f "$src" ] || { echo "no such source: $src" >&2; return 1; }
    "$TYPST" compile --root "$ROOT" "$src" "$ROOT/$base.pdf"
    echo "wrote $base.pdf ($(stat -c%s "$ROOT/$base.pdf") bytes)"
}

if [ $# -gt 0 ]; then
    for f in "$@"; do build_one "$f"; done
else
    for f in "$HERE"/report_*.typ; do build_one "$(basename "$f")"; done
fi
