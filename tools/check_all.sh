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
native nbody_rs   nbody-native-exact    env NBODY_ROUNDS=3 "$PY" dev/nbody/rs_check.py
native pyflate_rs pyflate-native-exact  "$PY" dev/pyflate/rs_check.py

if ls report_*.txt >/dev/null 2>&1; then
    check report-text-export "$PY" report/check_txt_tables.py
else
    skip report-text-export "no report_*.txt in this checkout"
fi

echo
echo "================ summary ================"
for x in "${PASSED[@]}";  do echo "PASS  $x"; done
for x in "${SKIPPED[@]}"; do echo "SKIP  $x"; done
for x in "${FAILED[@]}";  do echo "FAIL  $x"; done
if [ "${#FAILED[@]}" -ne 0 ]; then
    echo "${#FAILED[@]} check(s) failed"
    exit 1
fi
echo "all ${#PASSED[@]} checks passed, ${#SKIPPED[@]} skipped"
