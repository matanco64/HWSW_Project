#!/usr/bin/env bash
# Build the reports with Typst (two benchmark reports + the shared appendix).
#
#   ./build.sh                # build every report_*.typ (all three)
#   ./build.sh report_nbody   # build one (with or without .typ)
#
# Original profiles in results/ are the source evidence. The generator writes
# full-frame overviews and annotated detail crops to report/fig/; geometry checks
# run before compilation. Typst embeds these as vectors, without rasterization.
# Render and visually review PDFs too: a successful build is not a layout check.
#
# Needs a typst binary. On the WSL dev box it lives at /root/bin/typst; override
# with TYPST=/path/to/typst. Install: https://github.com/typst/typst/releases
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
TYPST="${TYPST:-typst}"
if ! command -v "$TYPST" >/dev/null 2>&1 && [ -x /root/bin/typst ]; then
    TYPST=/root/bin/typst
fi

command -v "$TYPST" >/dev/null 2>&1 || [ -x "$TYPST" ] || {
    echo "typst not found at '$TYPST' (set TYPST=...)" >&2; exit 1; }

build_one() {
    local base="${1%.typ}"
    local src="$HERE/$base.typ"
    [ -f "$src" ] || { echo "no such source: $src" >&2; return 1; }
    "$TYPST" compile --root "$ROOT" "$src" "$ROOT/$base.pdf"
    pdftotext "$TXTMODE" -enc UTF-8 "$ROOT/$base.pdf" "$ROOT/$base.txt"
    echo "wrote $base.pdf ($(stat -c%s "$ROOT/$base.pdf") bytes)"
}

# The .txt companions depend on which pdftotext is installed. xpdf's has -table,
# which keeps a table row's cells together where its -layout shifted values by a
# row; poppler's has no -table, and its -layout output was intact. Whichever runs,
# check_txt_tables.py below gates the result.
# (`pdftotext -h` exits nonzero, which pipefail would turn into "no -table".)
if { pdftotext -h 2>&1 || true; } | grep -q -- '-table'; then TXTMODE=-table; else TXTMODE=-layout; fi
echo "pdftotext mode: $TXTMODE"

python3 "$HERE/make_figures.py"
python3 "$HERE/check_figures.py"
if [ $# -gt 0 ]; then
    for f in "$@"; do build_one "$f"; done
    python3 "$HERE/check_txt_tables.py" "$@"
else
    for f in "$HERE"/report_*.typ; do build_one "$(basename "$f")"; done
    python3 "$HERE/check_txt_tables.py"
fi
