#!/usr/bin/env bash
# Build ONE Rust crate's wheel and install THAT wheel -- the exact file this
# invocation just produced -- then prove the interpreter imports it.
#
# Why this script exists.  The old instructions were `maturin build --release`
# followed by `pip install wheels/*.whl`.  Those are two different artifacts:
# maturin writes to `target/wheels/`, while `wheels/` holds the prebuilt wheel
# committed for the course VM.  Both are version 0.1.0, so pip reports the same
# thing either way and a reader following the README from a fresh clone would
# compile the current source and then install a *saved binary* of it.  Every
# measurement downstream would describe the saved binary, not the source in the
# checkout.  So: build into a fresh directory, refuse to proceed unless exactly
# one wheel landed there, install by full path, and then compare the compiled
# extension Python actually imports against the one inside that wheel.
#
#   ./tools/build_wheel.sh nbody|pyflate [--python python3] [--out DIR]
#                                        [--no-install] [--record FILE]
#
# Prints, and optionally records as JSON: the wheel path and SHA-256, the
# imported extension's path and SHA-256, whether that matches the wheel, the
# crate source hashes, and the toolchain versions.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY=python3
OUT=""
RECORD=""
INSTALL=1

CRATE="${1:-}"
shift || true
case "$CRATE" in
    nbody|pyflate) ;;
    *) echo "usage: $0 nbody|pyflate [--python PY] [--out DIR] [--no-install] [--record FILE]" >&2
       exit 2 ;;
esac
MODULE="${CRATE}_rs"

while [ $# -gt 0 ]; do
    case "$1" in
        --python) PY="$2"; shift 2 ;;
        --out) OUT="$2"; shift 2 ;;
        --record) RECORD="$2"; shift 2 ;;
        --no-install) INSTALL=0; shift ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

CRATE_DIR="$ROOT/rust/$CRATE"
[ -d "$CRATE_DIR" ] || { echo "no such crate: $CRATE_DIR" >&2; exit 1; }

# A fresh output directory per build. Reusing one is how a stale wheel gets
# installed when a build silently fails; an empty directory makes that
# impossible rather than merely unlikely.
STAMP="$(date -u +%Y%m%d_%H%M%S)"
OUT="${OUT:-$CRATE_DIR/target/wheels/$STAMP}"
rm -rf "$OUT"
mkdir -p "$OUT"

command -v maturin >/dev/null || {
    echo "maturin is not installed: python3 -m pip install 'maturin>=1.0,<2.0'" >&2
    exit 1
}

# --locked pins the dependency graph to Cargo.lock, so a rebuild months later
# resolves the same crate versions. It requires the lock file to exist and be
# current, so it is applied only where there is one to honour.
LOCKED=()
if [ -f "$CRATE_DIR/Cargo.lock" ]; then
    LOCKED=(--locked)
else
    echo "note: $CRATE has no Cargo.lock; building without --locked" >&2
fi

echo "== building $CRATE for $($PY -V 2>&1) -> $OUT"
( cd "$CRATE_DIR" && maturin build "${LOCKED[@]}" --release -i "$PY" --out "$OUT" )

# Exactly one wheel, or we do not know which one the next line would install.
shopt -s nullglob
WHEELS=("$OUT"/*.whl)
shopt -u nullglob
if [ "${#WHEELS[@]}" -ne 1 ]; then
    echo "expected exactly 1 wheel in $OUT, found ${#WHEELS[@]}" >&2
    printf '  %s\n' "${WHEELS[@]}" >&2
    exit 1
fi
WHEEL="${WHEELS[0]}"
WHEEL_SHA="$("$PY" -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$WHEEL")"
echo "== built  $WHEEL"
echo "   sha256 $WHEEL_SHA"

if [ "$INSTALL" -eq 1 ]; then
    # By full path, never a glob: the point of the whole script is that this
    # installs the file built above. --force-reinstall because the version
    # number does not change between builds, so pip would otherwise consider an
    # older 0.1.0 already satisfied and skip it.
    PIP=("$PY" -m pip install --force-reinstall --no-deps "$WHEEL")
    # Not "try, then sudo on failure": on a system interpreter pip does not
    # fail, it silently falls back to a --user install. That copy shadows the
    # system one for this user but not for root (py-spy runs under sudo), so
    # one import name ends up answering with two different binaries. Decide up
    # front instead, and let the hash check below catch anything that slips by.
    SITE="$("$PY" -c 'import sysconfig; print(sysconfig.get_paths()["platlib"])')"
    if "$PY" -c 'import sys; sys.exit(sys.prefix == sys.base_prefix)' || [ -w "$SITE" ]; then
        echo "== installing: ${PIP[*]}"
        PIP_USER=0 "${PIP[@]}"
    else
        echo "== installing with sudo ($SITE is not writable): ${PIP[*]}"
        sudo env PIP_USER=0 "${PIP[@]}"
    fi
fi

# What actually got imported. This is the number that matters: an install can
# succeed and a *different* copy still win on sys.path.
"$PY" - "$CRATE" "$MODULE" "$WHEEL" "$WHEEL_SHA" "$CRATE_DIR" "$INSTALL" "${RECORD:-}" <<'EOF'
import hashlib, importlib.machinery, json, os, subprocess, sys, zipfile

crate, module, wheel, wheel_sha, crate_dir, install, record = sys.argv[1:8]
SUFFIXES = tuple(importlib.machinery.EXTENSION_SUFFIXES)


def sha256(data_or_path):
    if isinstance(data_or_path, bytes):
        return hashlib.sha256(data_or_path).hexdigest()
    with open(data_or_path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def extension_file(mod):
    # maturin installs the crate as a package whose __init__.py is a generated
    # three-line re-export, identical for every build; the kernel is the
    # compiled submodule beside it. Hash that, not the stub.
    name = mod.__name__
    sub = sys.modules.get(name + "." + name.rpartition(".")[2])
    for candidate in (sub, mod):
        path = getattr(candidate, "__file__", None) or ""
        if path.endswith(SUFFIXES):
            return path
    for entry in getattr(mod, "__path__", None) or ():
        for fn in sorted(os.listdir(entry)):
            if fn.endswith(SUFFIXES):
                return os.path.join(entry, fn)
    return getattr(mod, "__file__", None)


def version(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              check=True).stdout.strip().splitlines()[0]
    except Exception:
        return "unavailable"


with zipfile.ZipFile(wheel) as zf:
    in_wheel = {n: sha256(zf.read(n)) for n in zf.namelist() if n.endswith(SUFFIXES)}

mod = __import__(module)
loaded = extension_file(mod)
loaded_sha = sha256(loaded) if loaded and os.path.exists(loaded) else None
matches = loaded_sha is not None and loaded_sha in in_wheel.values()

info = {
    "crate": crate,
    "module": module,
    "wheel": os.path.abspath(wheel),
    "wheel_sha256": wheel_sha,
    "wheel_extensions": in_wheel,
    "loaded_extension": loaded,
    "loaded_sha256": loaded_sha,
    "loaded_matches_wheel": matches,
    "installed_by_this_run": install == "1",
    "python": sys.version.split()[0],
    "python_executable": sys.executable,
    "sources": {os.path.basename(p): sha256(os.path.join(crate_dir, "src", p))
                for p in sorted(os.listdir(os.path.join(crate_dir, "src")))
                if p.endswith(".rs")},
    "rustc": version("rustc", "--version"),
    "cargo": version("cargo", "--version"),
    "maturin": version("maturin", "--version"),
}
print("== imported %s extension from %s" % (module, loaded))
print("   sha256 %s (%s the wheel just built)"
      % (loaded_sha, "matches" if matches else "DOES NOT MATCH"))
print("   rustc  %s" % info["rustc"])
if record:
    os.makedirs(os.path.dirname(os.path.abspath(record)) or ".", exist_ok=True)
    with open(record, "w") as fh:
        json.dump(info, fh, indent=2, sort_keys=True)
    print("== provenance written to %s" % record)
if install == "1" and not matches:
    sys.exit("*** %s imports %s, which is not the extension inside %s.\n"
             "    Another copy is winning on sys.path (a --user install is the "
             "usual culprit);\n    anything measured now would describe that "
             "copy, not this build." % (sys.executable, loaded, wheel))
EOF
