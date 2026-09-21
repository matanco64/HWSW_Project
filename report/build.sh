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

# stat(1) takes different flags on GNU and BSD userlands, and this builds on
# both (WSL/Linux for the release build, macOS for a local check).
_filesize() { stat -c%s "$1" 2>/dev/null || stat -f%z "$1"; }

# `--identified` stamps names + ID numbers on a SECOND set of copies, written to
# a gitignored directory. The committed reports are never touched by it: this
# repository is public, and an ID committed once stays in history. The identity
# text is read from report/identity.local.txt, which .gitignore excludes.
IDENTIFIED=0
IDFILE="$HERE/identity.local.txt"
OUTDIR="$ROOT"
IDARGS=()

build_one() {
    local base="${1%.typ}"
    local src="$HERE/$base.typ"
    [ -f "$src" ] || { echo "no such source: $src" >&2; return 1; }
    "$TYPST" compile --root "$ROOT" ${IDARGS[@]+"${IDARGS[@]}"} "$src" "$OUTDIR/$base.pdf"
    # The .txt companion comes from a second compilation with txtmode set, in
    # which the flame graphs become a one-line pointer (see style.typ). Prose,
    # tables and diagrams are identical in both.
    local tmpdir
    tmpdir="$(mktemp -d)"
    "$TYPST" compile --root "$ROOT" --input txtmode=1 ${IDARGS[@]+"${IDARGS[@]}"} \
        "$src" "$tmpdir/$base.pdf"
    pdftotext "$TXTMODE" -enc UTF-8 "$tmpdir/$base.pdf" "$OUTDIR/$base.txt"
    rm -rf "$tmpdir"
    echo "wrote $OUTDIR/$base.pdf ($(_filesize "$OUTDIR/$base.pdf") bytes)"
}

# The .txt companions depend on which pdftotext is installed. xpdf's has -table,
# which keeps a table row's cells together where its -layout shifted values by a
# row; poppler's has no -table, and its -layout output was intact. Whichever runs,
# check_txt_tables.py below gates the result.
# (`pdftotext -h` exits nonzero, which pipefail would turn into "no -table".)
if { pdftotext -h 2>&1 || true; } | grep -q -- '-table'; then TXTMODE=-table; else TXTMODE=-layout; fi
echo "pdftotext mode: $TXTMODE"

# Pull --identified out of the arguments; anything else is a report base name.
ARGS=()
for a in "$@"; do
    case "$a" in
        --identified) IDENTIFIED=1 ;;
        *) ARGS+=("$a") ;;
    esac
done
set -- ${ARGS[@]+"${ARGS[@]}"}

python3 "$HERE/make_figures.py"
python3 "$HERE/check_figures.py"

build_all() {
    if [ $# -gt 0 ]; then
        for f in "$@"; do build_one "$f"; done
    else
        for f in "$HERE"/report_*.typ; do build_one "$(basename "$f")"; done
    fi
}

# 1. The committed, ID-free reports. This pass is the gated one: the table check
#    runs against what actually ships in the repository.
build_all "$@"
python3 "$HERE/check_txt_tables.py" "$@"

# 2. Optional identified copies, into a gitignored directory.
if [ "$IDENTIFIED" = 1 ]; then
    [ -s "$IDFILE" ] || {
        echo "--identified needs $IDFILE" >&2
        echo "one line, e.g.: Matan Cohen 012345678 · Yuval Kogan 087654321" >&2
        echo "The file is gitignored. Create it and re-run." >&2
        exit 1; }
    OUTDIR="$ROOT/submission/identified"
    mkdir -p "$OUTDIR"
    IDARGS=(--input "ids=$(tr -d '\n' < "$IDFILE")")
    echo
    echo "== identified copies -> $OUTDIR"
    build_all "$@"
    echo
    echo "These carry ID numbers and live under submission/, which is gitignored."
    echo "Hand them in; do not commit them."
fi
