#!/usr/bin/env bash
# Render report.html -> report.pdf with headless Chrome.
#
# Chrome cannot write into the OneDrive-synced project folder (Access denied),
# so it renders to a temp file which we then copy into place.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
CHROME="${CHROME:-/c/Program Files/Google/Chrome/Application/chrome.exe}"
TMP="${TMP:-/c/Users/$USER/AppData/Local/Temp}/report_build.pdf"
TMP_WIN=$(cygpath -w "$TMP" 2>/dev/null || echo "$TMP")
URL="file:///$(cygpath -m "$HERE/report.html" 2>/dev/null || echo "$HERE/report.html")"

# --user-data-dir is required: without it headless Chrome aborts with
# "Missing headless user data directory".
PROFILE_DIR="$(mktemp -d)"
"$CHROME" --headless --disable-gpu --no-pdf-header-footer \
    --user-data-dir="$(cygpath -w "$PROFILE_DIR" 2>/dev/null || echo "$PROFILE_DIR")" \
    --print-to-pdf="$TMP_WIN" "$URL"
rm -rf "$PROFILE_DIR"
cp -f "$TMP" "$HERE/report.pdf"
echo "wrote $HERE/report.pdf ($(stat -c%s "$HERE/report.pdf") bytes)"
