#!/usr/bin/env bash
# Render the report HTML sources to PDF with headless Chrome.
#
#   ./build.sh              # build every report_*.html
#   ./build.sh report_nbody # build just one (with or without .html)
#
# Two quirks this works around:
#  - Chrome cannot write into the OneDrive-synced project folder ("Access is
#    denied"), so it renders to a temp file which we then copy into place.
#  - Headless Chrome aborts with "Missing headless user data directory" unless
#    --user-data-dir is given explicitly.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
CHROME="${CHROME:-/c/Program Files/Google/Chrome/Application/chrome.exe}"
OUTDIR="${OUTDIR:-$HERE/..}"   # PDFs land at the repo root, next to script_*.sh

build_one() {
    local base="${1%.html}"
    local src="$HERE/$base.html"
    [ -f "$src" ] || { echo "no such source: $src" >&2; return 1; }

    # Chrome must write somewhere outside OneDrive; mktemp -d gives us that
    # without depending on $USER, which Git Bash does not always set.
    local stage; stage="$(mktemp -d)"
    local tmp="$stage/${base}.pdf"
    local profile; profile="$(mktemp -d)"
    local url="file:///$(cygpath -m "$src" 2>/dev/null || echo "$src")"

    "$CHROME" --headless --disable-gpu --no-pdf-header-footer \
        --user-data-dir="$(cygpath -w "$profile" 2>/dev/null || echo "$profile")" \
        --print-to-pdf="$(cygpath -w "$tmp" 2>/dev/null || echo "$tmp")" "$url" 2>/dev/null
    rm -rf "$profile"

    cp -f "$tmp" "$OUTDIR/$base.pdf"
    rm -rf "$stage"
    echo "wrote $OUTDIR/$base.pdf ($(stat -c%s "$OUTDIR/$base.pdf") bytes)"
}

if [ $# -gt 0 ]; then
    for f in "$@"; do build_one "$f"; done
else
    for f in "$HERE"/report_*.html; do build_one "$(basename "$f")"; done
fi
