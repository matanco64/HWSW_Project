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

# Typst stamps a creation date into every PDF, so an unpinned rebuild changed the
# bytes of an unchanged document and `git status` could never tell a stale report
# from a re-run. Pinning it to the commit's own date makes a given revision build
# byte-identical PDFs, which is what lets make_submission.sh treat a dirty tree
# after a rebuild as real staleness.
# Dated from the last commit touching the Typst sources, not from HEAD and not
# from report/ as a whole. The PDFs live at the repository root, so committing
# them cannot move this date, and neither can editing a build script -- either
# would change the timestamp, hence the bytes, hence the next build, and
# make_submission could never reach a clean tree.
if [ -z "${SOURCE_DATE_EPOCH:-}" ]; then
    SOURCE_DATE_EPOCH="$(git -C "$ROOT" log -1 --format=%ct -- 'report/*.typ' 2>/dev/null || true)"
    [ -n "$SOURCE_DATE_EPOCH" ] && export SOURCE_DATE_EPOCH
fi

# stat(1) takes different flags on GNU and BSD userlands, and this builds on
# both (WSL/Linux for the release build, macOS for a local check).
_filesize() { stat -c%s "$1" 2>/dev/null || stat -f%z "$1"; }

# Stamped copies carrying names + ID numbers are built BY DEFAULT, into a
# gitignored directory. The committed reports are never touched by them: this
# repository is public, and an ID committed once stays in history for good. The
# identity text comes from report/identity.local.txt, which .gitignore excludes;
# without that file the stamped pass is skipped, so CI and fresh clones are fine.
# `--no-identity` skips it explicitly.
IDENTIFIED=1
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
        --identified) IDENTIFIED=1 ;;          # accepted; it is now the default
        --no-identity) IDENTIFIED=0 ;;
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
if [ "$IDENTIFIED" = 1 ] && [ ! -s "$IDFILE" ]; then
    echo
    echo "no $IDFILE, so no stamped copies were built."
    echo "To make them: printf 'Name 012345678 · Name 087654321\\n' > $IDFILE"
    IDENTIFIED=0
fi
if [ "$IDENTIFIED" = 1 ]; then
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
