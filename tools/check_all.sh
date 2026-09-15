#!/usr/bin/env bash
# Every software correctness check in one command, with one exit status.
#
#   ./tools/check_all.sh                   # native checks run if the wheels import
#   ./tools/check_all.sh --require-native  # ...and fail if they do not (CI, VM)
#
# PYTHON=<interpreter> selects the interpreter (default: python3). A check that
# cannot run is reported as SKIPPED by name, never folded into a pass.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-python3}"
REQUIRE_NATIVE=0
[ "${1:-}" = --require-native ] && REQUIRE_NATIVE=1

PASSED=()
FAILED=()
SKIPPED=()

check() {
    local name="$1"; shift
    echo
    echo "== $name: $*"
    local rc=0
    "$@" || rc=$?
    if [ "$rc" -eq 0 ]; then
        PASSED+=("$name")
    else
        FAILED+=("$name (exit $rc)")
    fi
}

skip() {
    echo
    echo "== $1: SKIPPED ($2)"
    SKIPPED+=("$1: $2")
}

native() {                      # native <module> <name> <cmd...>
    local module="$1" name="$2"; shift 2
    if "$PY" -c "import $module" 2>/dev/null; then
        check "$name" "$@"
    elif [ "$REQUIRE_NATIVE" -eq 1 ]; then
        echo
        echo "== $name: FAILED ($module is not importable and --require-native was given)"
        FAILED+=("$name ($module not importable)")
    else
        skip "$name" "$module not importable"
    fi
}

echo "python: $("$PY" -VV 2>&1 | head -1)"

check unit-tests            "$PY" -m unittest discover -s tests -v
check nbody-python-exact    "$PY" dev/nbody/verify.py --steps 20000
check nbody-python-exact-N  "$PY" dev/nbody/verify.py --steps 2000 --bodies 5,10,20
# The rolled fallback above _MAX_UNROLL_PAIRS had no oracle: verify.py topped out
# at N = 200 (19,900 pairs), just under the 20,000 limit, so the generated kernel
# was the only thing ever checked. Lowering the limit reaches the same code at
# N = 6, for a fraction of the work.
check nbody-python-exact-rolled \
    env NBODY_MAX_UNROLL_PAIRS=0 "$PY" dev/nbody/verify.py --steps 2000 --bodies 6,10
# --bodies: the native path is what --bodies N and the big-N sweep drive, and
# pair order above five bodies is generated code that N = 5 never exercises.
native nbody_rs   nbody-native-exact    env NBODY_ROUNDS=3 "$PY" dev/nbody/rs_check.py --bodies 5,10,31
native pyflate_rs pyflate-native-exact  "$PY" dev/pyflate/rs_check.py

if ls report_*.txt >/dev/null 2>&1; then
    check report-text-export "$PY" report/check_txt_tables.py
else
    skip report-text-export "no report_*.txt in this checkout"
fi

# The reports teach with worked examples -- a Huffman lookup, a counting-sort BWT,
# a move-to-front update, an RLE4 expansion, and an nbody pair update. This runs
# them against the shipped functions, so an example cannot quietly drift away from
# the code it claims to describe. Standard library only: it loads the functions
# from their AST rather than importing the benchmarks.
check report-examples "$PY" report/verify_examples.py

echo
echo "================ summary ================"
# bash 3.2 treats an empty declared array as unset under `set -u`, so a run in
# which nothing failed died here instead of printing the summary. The ${a[@]+..}
# form expands to nothing when the array is empty and is safe on every bash.
for x in ${PASSED[@]+"${PASSED[@]}"};  do echo "PASS  $x"; done
for x in ${SKIPPED[@]+"${SKIPPED[@]}"}; do echo "SKIP  $x"; done
for x in ${FAILED[@]+"${FAILED[@]}"};  do echo "FAIL  $x"; done
nfail=0
for x in ${FAILED[@]+"${FAILED[@]}"}; do nfail=$((nfail + 1)); done
if [ "$nfail" -ne 0 ]; then
    echo "$nfail check(s) failed"
    exit 1
fi
echo "all checks passed"
