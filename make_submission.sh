#!/usr/bin/env bash
# Package the course submission, after checking it is one.
#
#   ./make_submission.sh              # verify, then write submission/<rev>.zip
#   ./make_submission.sh --check      # verify only, write nothing
#   ./make_submission.sh --out DIR    # somewhere other than submission/
#
# The archive comes from `git archive HEAD`, so it is exactly the committed
# tree: no results/runs/, no output/, no build artifacts, nothing a .gitignore
# already excludes, and nothing uncommitted. That is also why a dirty tree is
# refused -- a bundle that does not correspond to a commit cannot be checked
# against anything later.
#
# Staleness is gated by tools/check_all.sh rather than by comparing timestamps.
# mtimes are meaningless in a fresh clone; check_txt_tables.py instead reads the
# table rows out of report/*.typ and requires them to appear in the shipped
# report_*.txt, and verify_examples.py runs the reports' worked examples against
# the shipped functions. Both fail if a report no longer matches its source.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

OUT="$ROOT/submission"
CHECK_ONLY=0
while [ $# -gt 0 ]; do
    case "$1" in
        --check) CHECK_ONLY=1; shift ;;
        --out)   OUT="${2:?--out needs a directory}"; shift 2 ;;
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

fail() { echo "SUBMISSION NOT READY: $*" >&2; exit 1; }

IDENT_DIR="$ROOT/submission/identified"
IDFILE="$ROOT/report/identity.local.txt"

# --- 0. rebuild the reports, so what ships is what the sources say ----------
# This runs FIRST, and the dirty-tree check below is what makes it meaningful:
# report/build.sh pins the PDF creation date to the last commit touching
# report/, so an unchanged document rebuilds byte-identically. A report that
# comes back modified is therefore genuinely stale, not just re-run.
echo "== rebuilding the reports"
./report/build.sh >/dev/null || fail "report build failed; run ./report/build.sh to see why"

# --- 1. the bundle must correspond to a commit ------------------------------
command -v git >/dev/null || fail "git not found"
git rev-parse --git-dir >/dev/null 2>&1 || fail "not a git repository"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "Uncommitted changes to tracked files:" >&2
    git status --short --untracked-files=no >&2
    echo "(the reports were just rebuilt; if they are listed above they were stale)" >&2
    fail "commit or stash them first; the archive is built from HEAD"
fi
REV="$(git rev-parse --short HEAD)"
STAMP="$(date -u +%Y%m%d)"

# --- 2. the named deliverables must exist ------------------------------------
# project_instructions.md "What You Need to Submit": a report and a run script
# per selected benchmark, a README, and the AI prompt log. pyflate and nbody are
# the two submitted benchmarks.
missing=0
for f in report_pyflate.txt report_nbody.txt \
         script_pyflate.sh script_nbody.sh \
         README.md prompt.txt; do
    if [ -s "$f" ]; then
        printf '  ok       %-22s %s\n' "$f" "$(wc -c <"$f" | tr -d ' ') bytes"
    else
        printf '  MISSING  %s\n' "$f"; missing=1
    fi
done
[ "$missing" -eq 0 ] || fail "a required deliverable is absent or empty"

for s in script_pyflate.sh script_nbody.sh; do
    [ -x "$s" ] || fail "$s is not executable"
    bash -n "$s" || fail "$s does not parse"
done

# --- 3. hardware: the course wants an implementation, not only a proposal ----
rtl_count=$(git ls-files 'hw/*/rtl/*.sv' | wc -l | tr -d ' ')
[ "$rtl_count" -gt 0 ] || fail "no SystemVerilog under hw/*/rtl/ is committed"
printf '  ok       %-22s %s committed\n' "hw RTL" "$rtl_count .sv files"

# --- 4. correctness ----------------------------------------------------------
# check_all.sh skips the nbody oracles when pyperf is missing, which is the right
# thing for a bare checkout but the wrong thing here: packaging a submission
# whose central correctness claim was never exercised is worse than not
# packaging one. Require the prerequisite up front, with the fix in the message.
PY="${PYTHON:-python3}"
"$PY" -c "import pyperf" 2>/dev/null || fail \
    "pyperf is not importable by $PY, so the bit-exactness oracles would be skipped.
                     $PY -m pip install 'pyperformance==1.14.0'
                   or run ./script_nbody.sh setup, which installs it."

# The archive must carry names and ID numbers even though the repository does
# not: this repository is public, so the stamped reports exist only under
# submission/identified/ and are overlaid into the zip below.
[ -s "$IDFILE" ] || fail \
    "no $IDFILE, so the reports would go out without ID numbers.
                   printf 'Name 012345678 · Name 087654321\\n' > report/identity.local.txt
                   The file is gitignored."
for f in report_pyflate report_nbody; do
    [ -s "$IDENT_DIR/$f.pdf" ] && [ -s "$IDENT_DIR/$f.txt" ] || \
        fail "$IDENT_DIR/$f is missing; ./report/build.sh should have written it"
done

echo
echo "== running tools/check_all.sh"
./tools/check_all.sh || fail "correctness checks failed"

if [ "$CHECK_ONLY" -eq 1 ]; then
    echo
    echo "submission checks passed for $REV (nothing written, --check)"
    exit 0
fi

# --- 5. package --------------------------------------------------------------
mkdir -p "$OUT"
ARCHIVE="$OUT/hwsw_submission_${STAMP}_${REV}.zip"
rm -f "$ARCHIVE"
git archive --format=zip --prefix="hwsw-project/" -o "$ARCHIVE" HEAD

# Replace the repository's ID-free reports with the stamped ones. zip overwrites
# entries of the same name, so the archive ends up with exactly one copy of each.
stage="$(mktemp -d)"
mkdir -p "$stage/hwsw-project"
cp "$IDENT_DIR"/report_*.pdf "$IDENT_DIR"/report_*.txt "$stage/hwsw-project/"
( cd "$stage" && zip -q "$ARCHIVE" hwsw-project/report_* )
rm -rf "$stage"

# Prove it: every report inside the archive must carry an ID number, and the
# repository's own copies must still not.
ids_re="$(grep -oE '[0-9]{6,}' "$IDFILE" | paste -sd'|' -)"
[ -n "$ids_re" ] || fail "no ID numbers found in $IDFILE"
for f in report_pyflate report_nbody; do
    unzip -p "$ARCHIVE" "hwsw-project/$f.txt" | grep -qE "$ids_re" || \
        fail "$f.txt in the archive carries no ID number"
done
if grep -rqE "$ids_re" "$ROOT/report_pyflate.txt" "$ROOT/report_nbody.txt" 2>/dev/null; then
    fail "the repository's own reports contain ID numbers; they must not"
fi
echo "  ok       archive reports carry IDs; repository copies do not"

echo
echo "wrote $ARCHIVE"
echo "  size     $(du -h "$ARCHIVE" | cut -f1)"
echo "  revision $REV on $(git rev-parse --abbrev-ref HEAD)"
echo "  files    $(git ls-files | wc -l | tr -d ' ') tracked"
if command -v shasum >/dev/null 2>&1; then
    echo "  sha256   $(shasum -a 256 "$ARCHIVE" | cut -d' ' -f1)"
elif command -v sha256sum >/dev/null 2>&1; then
    echo "  sha256   $(sha256sum "$ARCHIVE" | cut -d' ' -f1)"
fi
echo
echo "The repository itself is the primary deliverable; this archive is for"
echo "wherever a git URL is not accepted. git archive is deterministic, so"
echo "rebuilding $REV gives this same digest."
