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

OUTDIR="$ROOT"

build_one() {
    local base="${1%.typ}"
    local src="$HERE/$base.typ"
    [ -f "$src" ] || { echo "no such source: $src" >&2; return 1; }
    "$TYPST" compile --root "$ROOT" "$src" "$OUTDIR/$base.pdf"
    # The .txt companion comes from a second compilation with txtmode set, in
    # which the flame graphs become a one-line pointer (see style.typ). Prose,
    # tables and diagrams are identical in both.
    local tmpdir
    tmpdir="$(mktemp -d)"
    "$TYPST" compile --root "$ROOT" --input txtmode=1 "$src" "$tmpdir/$base.pdf"
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

python3 "$HERE/make_figures.py"
python3 "$HERE/check_figures.py"

build_all() {
    if [ $# -gt 0 ]; then
        for f in "$@"; do build_one "$f"; done
    else
        for f in "$HERE"/report_*.typ; do build_one "$(basename "$f")"; done
    fi
}

build_all "$@"

# Consolidated hardware report: hw/docs/hardware_report.md is the source that
# gets edited; the Typst file is generated from it and committed alongside so
# the shipped PDF has a reproducible origin. Built with every full build (no
# argument), skipped when a single report was named.
if [ $# -eq 0 ]; then
    python3 "$ROOT/tools/md2typ.py" "$ROOT/hw/docs/hardware_report.md" \
        "$ROOT/hw/docs/hardware_report.typ"
    "$TYPST" compile --root "$ROOT" "$ROOT/hw/docs/hardware_report.typ" \
        "$ROOT/hw/docs/hardware_report.pdf"
    echo "built hw/docs/hardware_report.pdf"
fi

python3 "$HERE/check_txt_tables.py" "$@"
