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

IDFILE="$ROOT/report/ids.local"
IDPDF="$ROOT/report/ids.pdf"

# --- 0. the built reports must not be older than their sources --------------
# Asked from git history rather than by rebuilding and diffing. A rebuild only
# reproduces the committed bytes on the machine that made them: Typst and
# pdftotext differ between our laptops, and build.sh even picks xpdf's `-table`
# over poppler's `-layout` when it finds it, so a rebuild elsewhere reports
# every report as stale when nothing is wrong. History is the same everywhere.
REPORT_OUT="report_nbody.pdf report_pyflate.pdf report_appendix.pdf
            report_nbody.txt report_pyflate.txt report_appendix.txt"
# shellcheck disable=SC2086
out_commit="$(git log -1 --format=%H -- $REPORT_OUT)"
if [ -n "$out_commit" ]; then
    stale="$(git log --oneline "$out_commit"..HEAD -- 'report/*.typ' report/fig)"
    if [ -n "$stale" ]; then
        echo "Report sources changed after the reports were last built:" >&2
        echo "$stale" >&2
        fail "run ./report/build.sh and commit the result"
    fi
fi
echo "  ok       reports are newer than their sources"

# --- 1. the bundle must correspond to a commit ------------------------------
command -v git >/dev/null || fail "git not found"
git rev-parse --git-dir >/dev/null 2>&1 || fail "not a git repository"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "Uncommitted changes to tracked files:" >&2
    git status --short --untracked-files=no >&2
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

# Names and ID numbers go on their own page, as they did in HW1 and HW2, built
# here and added to the archive. The repository never holds them: it is public,
# and git history keeps whatever it is once given.
[ -s "$IDFILE" ] || fail \
    "no $IDFILE, so the submission would go out without ID numbers.
                   printf 'MATAN_ID=012345678\\nYUVAL_ID=087654321\\n' > report/ids.local
                   The file is gitignored."
# shellcheck source=/dev/null
. "$IDFILE"
[ -n "${MATAN_ID:-}" ] && [ -n "${YUVAL_ID:-}" ] || \
    fail "$IDFILE must set MATAN_ID and YUVAL_ID"
# Same pinned creation date the reports use, or this page alone would make the
# archive differ on every run.
EPOCH="$(git log -1 --format=%ct -- 'report/*.typ')"
SOURCE_DATE_EPOCH="$EPOCH" "${TYPST:-typst}" compile --root "$ROOT" \
    --input "matan-id=$MATAN_ID" --input "yuval-id=$YUVAL_ID" \
    "$ROOT/report/ids.typ" "$IDPDF" || fail "could not build the names/IDs page"
printf '  ok       %-22s %s bytes\n' "report/ids.pdf" "$(wc -c <"$IDPDF" | tr -d ' ')"

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

# Add the names/IDs page. It is the only file in the archive that is not in the
# commit, and the only one carrying ID numbers.
stage="$(mktemp -d)"
mkdir -p "$stage/hwsw-project"
cp "$IDPDF" "$stage/hwsw-project/ids.pdf"
# zip records mtimes, which would make the archive differ on every run; pin it
# so a given revision still produces the same digest.
"$PY" -c "import os,sys; os.utime(sys.argv[1], (int(sys.argv[2]),)*2)" \
    "$stage/hwsw-project/ids.pdf" "$EPOCH"
( cd "$stage" && zip -qX "$ARCHIVE" hwsw-project/ids.pdf )
rm -rf "$stage"

# Prove it: the archive carries the IDs, and nothing in the repository does.
ids_re="$MATAN_ID|$YUVAL_ID"
unzip -p "$ARCHIVE" hwsw-project/ids.pdf > "$OUT/.ids_check.pdf"
if command -v pdftotext >/dev/null 2>&1; then
    pdftotext "$OUT/.ids_check.pdf" - 2>/dev/null | grep -qE "$ids_re" || \
        fail "ids.pdf in the archive carries no ID number"
fi
rm -f "$OUT/.ids_check.pdf"
if git ls-files -z | xargs -0 grep -lE "$ids_re" 2>/dev/null | grep -q .; then
    fail "a tracked file contains an ID number; it must not"
fi
echo "  ok       archive carries ids.pdf; no tracked file contains an ID"

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
