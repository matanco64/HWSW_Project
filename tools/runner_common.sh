# Shared stage library for script_<bench>.sh. Sourced, never executed.
#
# The three runners used to be three copies of the same 130 lines and had
# drifted in ways that changed what a reader would measure. One library, three
# thin wrappers, so a fix lands everywhere at once.
#
# A wrapper sets BENCH (and optionally PROFILE_LOOPS / PROFILE_VALUES) and
# then calls `run_stage "$@"`.

set -euo pipefail

# The repo root is the directory of the wrapper that sourced this file; when
# this file is sourced directly (tests, an interactive shell) fall back to its
# own parent so ROOT is still the checkout.
if [ -n "${BASH_SOURCE[1]:-}" ]; then
    ROOT="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
else
    ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
PROFILE_LOOPS="${PROFILE_LOOPS:-2}"
PROFILE_VALUES="${PROFILE_VALUES:-6}"
BM_OPT="$ROOT/benchmarks/bm_$BENCH/run_benchmark.py"
HAS_NATIVE="${HAS_NATIVE:-1}"    # 0 for a benchmark with no rust/<bench> crate

# ---------------------------------------------------------------------------
# Results directory: never the top-level results/, which holds the captures the
# reports quote. Each run gets results/runs/<stamp>_<bench>/ with
# results/runs/latest pointing at it, so stage-at-a-time use still works.
# HWSW_RESULTS=<dir> overrides; HWSW_FRESH=1 forces a new directory.
# ---------------------------------------------------------------------------
RUNS="$ROOT/results/runs"
_new_run_dir() {
    local d="$RUNS/$(date -u +%Y%m%d_%H%M%S)_$BENCH"
    mkdir -p "$d"
    ln -sfn "$(basename "$d")" "$RUNS/latest" 2>/dev/null || true
    echo "$d"
}
_resolve_res() {
    if [ -n "${HWSW_RESULTS:-}" ]; then
        mkdir -p "$HWSW_RESULTS"; echo "$HWSW_RESULTS"; return
    fi
    mkdir -p "$RUNS"
    # A stage that produces the run's first artifact starts a run; a stage that
    # only consumes earlier artifacts joins the newest one.
    case "${1:-all}" in
        compare|native) ;;
        *) _new_run_dir; return ;;
    esac
    if [ "${HWSW_FRESH:-0}" = 1 ] || [ ! -d "$RUNS/latest" ]; then
        _new_run_dir; return
    fi
    ( cd "$RUNS/latest" && pwd -P )
}

# ---------------------------------------------------------------------------
# Prerequisites, recorded rather than assumed
# ---------------------------------------------------------------------------
EXPECT_PY=3.10          # course VM: CPython 3.10.12
EXPECT_PYPERFORMANCE=1.14.0

_warn() { echo "WARNING: $*" >&2; }

check_prereqs() {
    # Hard requirements first: without these no stage can produce anything.
    command -v python3 >/dev/null || { echo "python3 not found" >&2; exit 1; }
    python3 -c "import pyperf" 2>/dev/null || {
        echo "pyperf is not importable by $(command -v python3)." >&2
        echo "  python3 -m pip install 'pyperformance==$EXPECT_PYPERFORMANCE'" >&2
        exit 1; }
    python3 -c "import pyperformance" 2>/dev/null || {
        echo "pyperformance is not importable by $(command -v python3)." >&2
        echo "  python3 -m pip install 'pyperformance==$EXPECT_PYPERFORMANCE'" >&2
        exit 1; }

    local pyver ppver pfver
    pyver="$(python3 -c 'import sys;print("%d.%d.%d"%sys.version_info[:3])')"
    ppver="$(python3 -c 'import pyperformance;print(getattr(pyperformance,"__version__","?"))')"
    pfver="$(python3 -c 'import pyperf;print(getattr(pyperf,"__version__","?"))')"

    # Version mismatches are warnings, not errors: the scripts still run, but a
    # number produced on a different interpreter is not comparable with the
    # reported ones, and silence about that is how mixed evidence gets quoted.
    case "$pyver" in
        $EXPECT_PY.*) ;;
        *) _warn "CPython $pyver, but the reported measurements are $EXPECT_PY.x."
           _warn "Results from this run are NOT comparable with results/." ;;
    esac
    [ "$ppver" = "$EXPECT_PYPERFORMANCE" ] || \
        _warn "pyperformance $ppver, expected $EXPECT_PYPERFORMANCE."

    printf 'bench=%s\npython=%s\npyperformance=%s\npyperf=%s\nstock=%s\nhost=%s\nkernel=%s\ndate=%s\ncpu=%s\n' \
        "$BENCH" "$pyver" "$ppver" "$pfver" "$BM_STOCK" "$(uname -n)" \
        "$(uname -sr)" "$(date -uIseconds)" "${CPU:-not pinned}" > "$RES/environment_$BENCH.txt"
}

require_perf() {
    command -v perf >/dev/null || {
        echo "perf not found: sudo apt-get install linux-tools-generic" >&2
        exit 1; }
}

# ---------------------------------------------------------------------------
# Locate the stock benchmark instead of hard-coding a dist-packages path
# ---------------------------------------------------------------------------
locate_stock() {
    local d
    d="$(python3 - "$BENCH" <<'EOF' 2>/dev/null || true
import os, sys
try:
    import pyperformance
except ImportError:
    raise SystemExit(1)
p = os.path.join(os.path.dirname(pyperformance.__file__),
                 "data-files", "benchmarks", "bm_" + sys.argv[1])
if os.path.isfile(os.path.join(p, "run_benchmark.py")):
    print(p)
EOF
)"
    if [ -z "$d" ]; then
        # A source checkout beside this repo is the documented fallback for
        # development hosts without pyperformance installed.
        d="$ROOT/../pyperformance/pyperformance/data-files/benchmarks/bm_$BENCH"
        [ -f "$d/run_benchmark.py" ] || {
            echo "cannot locate the stock bm_$BENCH." >&2
            echo "Install pyperformance for $(command -v python3), or place a" >&2
            echo "pyperformance checkout beside this repository." >&2
            exit 1; }
    fi
    ( cd "$d" && pwd -P )
}

# ---------------------------------------------------------------------------
# Backend discipline: pyperf scrubs the worker environment, so HWSW_BACKEND has
# to be forwarded with --inherit-environ or the workers measure whatever the
# import happened to find. Every JSON produced is then checked against what was
# requested -- an unchecked request is how a native-vs-native comparison got
# recorded once.
# ---------------------------------------------------------------------------
pinned() {                       # pinned <backend> <cmd...>
    local backend="$1"; shift
    HWSW_BACKEND="$backend" "$@"
}

assert_backend() {               # assert_backend <json> <backend|->
    # <backend> is what hwsw_backend and hwsw_backend_requested must both say;
    # "-" skips that check (the stock benchmark records no backend). When the
    # stage pinned a CPU, the recorded affinity must match it too.
    python3 - "$1" "$2" "${CPU:-}" <<'EOF'
import json, sys
path, want, cpu = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path) as fh:
    suite = json.load(fh)
meta = dict(suite.get("metadata", {}))
for bench in suite.get("benchmarks", []):
    meta.update(bench.get("metadata", {}) or {})
problems = []
if want != "-":
    got, asked = meta.get("hwsw_backend"), meta.get("hwsw_backend_requested")
    if got != want:
        problems.append("BACKEND MISMATCH: requested %r, JSON records %r -- the "
                        "run measured the wrong back end" % (want, got))
    elif asked is not None and asked != want:
        # The workers ran the right path but were never told to -- HWSW_BACKEND
        # did not reach them, and the match is a coincidence of what was installed.
        problems.append("BACKEND NOT PINNED: the workers recorded request %r, "
                        "not %r -- selection was accidental" % (asked, want))
if cpu:
    affinity = meta.get("cpu_affinity")
    if affinity is None:
        print("   WARNING: %s records no cpu_affinity (requested CPU %s)" % (path, cpu))
    elif str(affinity) != cpu:
        problems.append("CPU AFFINITY %r, but CPU %s was requested" % (affinity, cpu))
if problems:
    sys.exit("*** %s:\n    %s\n    Do not quote this run." % (path, "\n    ".join(problems)))
print("   metadata ok: %s backend=%s requested=%s cpu=%s"
      % (path, meta.get("hwsw_backend", "-"), meta.get("hwsw_backend_requested", "-"),
         meta.get("cpu_affinity", "-")))
EOF
}

# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------
# pip refuses --user inside a virtualenv, and the course's own guide sets
# pyperformance up in one; outside a venv --user is what avoids needing root.
# Pick per interpreter rather than assuming either.
_pip_install() {
    if python3 -c 'import sys; raise SystemExit(0 if sys.prefix != sys.base_prefix else 1)'; then
        python3 -m pip install "$@"
    else
        python3 -m pip install --user "$@"
    fi
}

setup() {
    sudo apt-get install -y python3-dbg linux-tools-generic git >/dev/null || true
    # The course VM ships pyperformance; a fresh host does not, and
    # check_prereqs exits without it -- so "setup installs the prerequisites"
    # has to be true rather than merely intended. Pinned, because a different
    # pyperformance supplies a different stock benchmark to measure against.
    python3 -c "import pyperformance" 2>/dev/null || \
        _pip_install "pyperformance==$EXPECT_PYPERFORMANCE" || \
        _warn "could not install pyperformance==$EXPECT_PYPERFORMANCE (see check_prereqs)"
    # py-spy supplies the Python-frame flame graphs in the profile stage; perf
    # covers the C frames whether or not this succeeds.
    command -v py-spy >/dev/null 2>&1 || _pip_install py-spy || true
    [ -d "$HOME/FlameGraph" ] || git clone --depth 1 https://github.com/brendangregg/FlameGraph "$HOME/FlameGraph"
    # KVM guest quirks: allow perf sampling; NOTE not persisted across VM reboots.
    sudo sysctl -w kernel.perf_event_paranoid=-1 kernel.kptr_restrict=0
    sudo python3 -m pyperf system tune || true
}

baseline() {
    # Stock benchmark, release python3, full rigor — the "before" evidence.
    # Pinned to the Python path: the stock file has no native backend, but
    # pinning keeps one rule for every measured invocation instead of a rule
    # with exceptions to remember.
    rm -f "$RES/baseline_$BENCH.json"
    pinned python python3 -m pyperformance run --rigorous "${CPU_ARGS[@]}" -b "$BENCH" \
        -o "$RES/baseline_$BENCH.json"
    assert_backend "$RES/baseline_$BENCH.json" -
    python3 -m pyperf stats "$RES/baseline_$BENCH.json" \
        | tee "$RES/baseline_${BENCH}_stats.txt"
}

_profile_one() {
    # $1 = tag (stock|opt), $2 = run_benchmark.py to profile.
    # Same flags AND the same pinned back end on both sides, so the two flame
    # graphs are directly comparable and neither one silently profiles the Rust
    # kernel because a wheel happens to be installed.
    # --call-graph dwarf, NOT -g: Ubuntu's python3-dbg has no frame pointers, so
    # frame-pointer unwinding walks into freed memory and yields chains of
    # 0xfdfdfd.. (Py_DEBUG fill bytes) -- an unusable flame graph.
    local l="$PROFILE_LOOPS" n="$PROFILE_VALUES"
    pinned python perf record -F 999 --call-graph dwarf,16384 -e cpu-clock \
        -o "$RES/${BENCH}_$1.perf.data" -- \
        python3-dbg "$2" --worker -l"$l" -w0 -n"$n"
    perf report --stdio -i "$RES/${BENCH}_$1.perf.data" > "$RES/perf_report_${BENCH}_$1.txt"
    perf script -i "$RES/${BENCH}_$1.perf.data" \
        | "$HOME/FlameGraph/stackcollapse-perf.pl" \
        | "$HOME/FlameGraph/flamegraph.pl" --title "$BENCH ($1, python3-dbg)" \
        > "$RES/flame_${BENCH}_$1.svg"
    # Python-level flame graph. CPython 3.10 has no -X perf trampoline, so perf
    # can only ever show C frames; py-spy samples the interpreter frame stack
    # and names the actual Python functions.
    PYSPY="$(command -v py-spy || echo "$HOME/.local/bin/py-spy")"
    if [ -x "$PYSPY" ]; then
        # sudo resets the environment, so the pin has to be re-applied inside it.
        sudo env HWSW_BACKEND=python "$PYSPY" record -f flamegraph \
            -o "$RES/pyspy_${BENCH}_$1.svg" -- \
            python3 "$2" --worker -l"$l" -w0 -n"$n" \
            || echo "py-spy failed ($1), non-fatal"
    fi
    # Hardware counters on release python3 (guest PMU counts <=4 events per pass).
    # --fast spawns workers, so the pin needs --inherit-environ to reach them.
    { pinned python perf stat -e cycles:u,instructions:u -- \
        python3 "$2" --fast --inherit-environ HWSW_BACKEND 2>&1 | tail -20
      pinned python perf stat -e cache-references,cache-misses,branches,branch-misses -- \
        python3 "$2" --fast --inherit-environ HWSW_BACKEND 2>&1 | tail -20
    } > "$RES/perf_stat_${BENCH}_$1.txt"
}

profile() {
    require_perf
    # Profile shape with python3-dbg (symbols); timings here are NOT quotable.
    # cpu-clock samples in proportion to elapsed CPU time, which is what a
    # "where does the time go" flame graph wants. On this guest PMU
    # `perf record -e cycles -F <n>` gave zero samples at every frequency tried
    # while `-c 2000000` worked -- use that for cycle-accurate work.
    # NOTE: `pyperf system tune` sets perf_event_max_sample_rate=1, throttling
    # perf record to 1 Hz -- restore a usable rate before recording.
    sudo sysctl -w kernel.perf_event_max_sample_rate=100000 \
                  kernel.perf_event_paranoid=-1 kernel.kptr_restrict=0
    # Both sides: 'stock' is the Initial Analysis evidence, 'opt' shows the
    # hotspot actually moving after the optimizations.
    _profile_one stock "$BM_STOCK/run_benchmark.py"
    _profile_one opt   "$BM_OPT"
}

optimized() {
    # Our modified benchmark from benchmarks/ via custom manifest (same benchmark name).
    rm -f "$RES/optimized_$BENCH.json"
    pinned python python3 -m pyperformance run --rigorous "${CPU_ARGS[@]}" \
        --manifest "$ROOT/benchmarks/MANIFEST" -b "$BENCH" \
        -o "$RES/optimized_$BENCH.json"
    # Benchmarks with a native tier must record the selected backend.
    if [ "$HAS_NATIVE" = 1 ]; then
        assert_backend "$RES/optimized_$BENCH.json" python
    else
        assert_backend "$RES/optimized_$BENCH.json" -
    fi
}

compare() {
    python3 -m pyperf compare_to "$RES/baseline_$BENCH.json" \
        "$RES/optimized_$BENCH.json" --table | tee "$RES/compare_$BENCH.txt"
}

wheel() {
    # Build the crate and install THAT wheel. See tools/build_wheel.sh for why
    # this is a stage rather than two lines in the README.
    "$ROOT/tools/build_wheel.sh" "$BENCH" --python python3 \
        --record "$RES/wheel_$BENCH.json"
}

# Make ${BENCH}_rs importable before the native stage runs. A fresh clone has
# no extension installed, so `all` used to run the entire suite and only then
# fail in native -- reporting an incomplete run for a repository that ships a
# prebuilt wheel. Build from this checkout where the Rust toolchain exists
# (the honest route: it measures the source in front of you), otherwise install
# the committed wheel the canonical run measured. Say which one happened.
ensure_native_module() {
    python3 -c "import ${BENCH}_rs" 2>/dev/null && return 0
    if command -v maturin >/dev/null 2>&1 && command -v cargo >/dev/null 2>&1; then
        echo "== $BENCH / wheel (building ${BENCH}_rs from this checkout)"
        if wheel; then
            return 0
        fi
        _warn "building ${BENCH}_rs failed; falling back to the committed wheel"
    fi
    local prebuilt
    prebuilt="$(ls "$ROOT/rust/$BENCH"/wheels/*.whl 2>/dev/null | head -n 1)"
    [ -n "$prebuilt" ] || { _warn "no committed wheel under rust/$BENCH/wheels/"; return 1; }
    echo "== $BENCH / wheel (installing committed $(basename "$prebuilt"))"
    echo "   NOTE: the binary the canonical run measured, not a build of this checkout."
    _pip_install --force-reinstall "$prebuilt" >/dev/null || return 1
    python3 -c "import ${BENCH}_rs" 2>/dev/null
}

native() {
    # The native back end against the pure-Python fallback of the SAME file,
    # same interpreter, harness and rigor, so HWSW_BACKEND is the only
    # difference. Deliberately not run through pyperformance, which builds its
    # own venv with no extension wheel in it. baseline vs optimized above stays
    # the course A/B; this is the accelerator tier on top of it.
    if ! python3 -c "import ${BENCH}_rs" 2>/dev/null; then
        echo "native stage: ${BENCH}_rs is not installed. Build and install it:" >&2
        echo "  ./script_$BENCH.sh wheel        # or: ./tools/build_wheel.sh $BENCH" >&2
        return 1
    fi
    # Record what is actually loaded, so this run's numbers can be tied to a
    # specific binary rather than to a version string that never changes.
    python3 - "$BENCH" > "$RES/native_module_$BENCH.txt" <<'EOF'
import hashlib, importlib.machinery, os, sys
# The package's __init__.py is a generated stub identical across builds; the
# kernel is the compiled extension beside it, so that is what gets hashed.
mod = __import__(sys.argv[1] + "_rs")
sfx = tuple(importlib.machinery.EXTENSION_SUFFIXES)
d = os.path.dirname(mod.__file__)
path = next((os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith(sfx)),
            mod.__file__)
print("module: %s" % path)
print("sha256: %s" % hashlib.sha256(open(path, "rb").read()).hexdigest())
EOF
    cat "$RES/native_module_$BENCH.txt"

    rm -f "$RES/native_$BENCH.json" "$RES/fallback_$BENCH.json"
    # --inherit-environ is not optional here. pyperf re-executes each worker
    # with a scrubbed environment, so without it HWSW_BACKEND never reaches the
    # processes that do the timing and BOTH runs silently measure whatever the
    # import found -- which is what happened the first time, and the recorded
    # hwsw_backend metadata is what caught it.
    pinned python python3 "$BM_OPT" --rigorous "${CPU_ARGS[@]}" \
        --inherit-environ HWSW_BACKEND -o "$RES/fallback_$BENCH.json"
    pinned native python3 "$BM_OPT" --rigorous "${CPU_ARGS[@]}" \
        --inherit-environ HWSW_BACKEND -o "$RES/native_$BENCH.json"
    # The pin is a request; the metadata is the evidence it was honoured.
    assert_backend "$RES/fallback_$BENCH.json" python
    assert_backend "$RES/native_$BENCH.json" native
    python3 -m pyperf compare_to "$RES/fallback_$BENCH.json" \
        "$RES/native_$BENCH.json" --table | tee "$RES/compare_${BENCH}_native.txt"
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
run_stage() {
    local stage="${1:-all}"
    case "$stage" in
        setup|baseline|profile|optimized|compare|wheel|native|all) ;;
        *) echo "usage: script_$BENCH.sh setup|baseline|profile|optimized|compare|wheel|native|all" >&2
           exit 2 ;;
    esac
    # A `;;&` fallthrough would fold this into the case above, but that is a
    # bash 4 feature and the test suite runs this file under macOS's bash 3.2.
    case "$stage" in
        wheel|native)
            [ "$HAS_NATIVE" = 1 ] || {
                echo "$BENCH has no rust/ crate, so there is no '$stage' stage." >&2
                exit 2; } ;;
    esac

    # setup installs the prerequisites, so it cannot require them first.
    if [ "$stage" = setup ]; then
        setup
        return
    fi

    # `all` begins by installing the prerequisites, so everything that needs
    # them -- locating the stock benchmark through the installed pyperformance,
    # and check_prereqs itself -- has to follow it rather than precede it.
    if [ "$stage" = all ]; then
        setup
    fi

    RES="$(_resolve_res "$stage")"
    BM_STOCK="$(locate_stock)"

    # Timed stages (baseline, optimized, native) run on one guest CPU via
    # --affinity, the protocol the preserved pyflate headline was measured
    # with. HWSW_CPU=<n> picks the CPU, HWSW_CPU=none disables pinning.
    # Profiling is unpinned: its timings are never quoted.
    CPU=""
    CPU_ARGS=()
    if [ "${HWSW_CPU:-auto}" != none ]; then
        CPU="${HWSW_CPU:-auto}"
        if [ "$CPU" = auto ]; then
            CPU="$(python3 -c 'import os; print(min(os.sched_getaffinity(0)))' 2>/dev/null || true)"
        fi
        if [ -n "$CPU" ]; then
            CPU_ARGS=(--affinity "$CPU")
        fi
    fi
    check_prereqs
    echo "== $BENCH / $stage"
    echo "   results -> $RES"
    echo "   stock   -> $BM_STOCK"
    echo "   cpu     -> ${CPU:-not pinned}"

    if [ "$stage" != all ]; then
        "$stage"
        return
    fi

    baseline; profile; optimized; compare
    if [ "$HAS_NATIVE" != 1 ]; then
        echo "== done: $RES (no native tier for $BENCH)"
        return 0
    fi
    # The native tier is optional -- a host without the wheel still produces the
    # full course A/B -- but "optional" must not mean "silent". The old
    # `native || true` swallowed a real failure and left an incomplete results
    # directory looking complete.
    # native() prints its own instructions when the module is missing, so a
    # failure here still explains itself.
    ensure_native_module || true
    local native_rc=0
    native || native_rc=$?
    if [ "$native_rc" -ne 0 ]; then
        echo "NATIVE TIER NOT MEASURED (exit $native_rc): the stock/optimized" >&2
        echo "comparison in $RES is complete; the native comparison is absent." >&2
        echo "SKIPPED: native" >> "$RES/stages_incomplete.txt"
    fi
    echo "== done: $RES"
    return "$native_rc"
}
