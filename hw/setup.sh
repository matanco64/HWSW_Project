#!/usr/bin/env bash
# One-shot toolchain install for the hardware flow. Idempotent; re-run to repair.
#   ./hw/setup.sh                 # OSS CAD Suite (verilator, yosys, iverilog, sby, gtkwave, surfer) + venv + sky130 liberty
#   ./hw/setup.sh --with-openlane # additionally: single-user Nix + OpenLane 2 (RTL->GDS on sky130)
# Everything is placed under hw/tools and hw/.venv (both gitignored). Requires: curl, tar, python3 >= 3.10, make, g++.
set -euo pipefail
HW_ROOT="$(cd "$(dirname "$0")" && pwd)"
TOOLS="$HW_ROOT/tools"
mkdir -p "$TOOLS"

# Pinned nightly of https://github.com/YosysHQ/oss-cad-suite-build (bump deliberately; record in hw/FLOW.md).
OSS_TAG="2026-08-26"
OSS_TGZ="oss-cad-suite-linux-x64-${OSS_TAG//-/}.tgz"
OSS_URL="https://github.com/YosysHQ/oss-cad-suite-build/releases/download/$OSS_TAG/$OSS_TGZ"
# sky130 HD standard-cell Liberty (typical corner), used by Yosys for area/gate counts.
# Mirrored in OpenROAD-flow-scripts (the google/skywater-pdk-libs-* raw path 404s).
LIB_URL="https://raw.githubusercontent.com/The-OpenROAD-Project/OpenROAD-flow-scripts/master/flow/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
VERILATOR_MIN="5.036"   # cocotb 2.0 minimum

WITH_OPENLANE=0
[ "${1:-}" = "--with-openlane" ] && WITH_OPENLANE=1

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

step "OSS CAD Suite ($OSS_TAG) -> $TOOLS/oss-cad-suite"
if [ -x "$TOOLS/oss-cad-suite/bin/verilator" ]; then
    echo "already present"
else
    curl -L --progress-bar -o "$TOOLS/$OSS_TGZ" "$OSS_URL"
    tar xzf "$TOOLS/$OSS_TGZ" -C "$TOOLS"
    rm -f "$TOOLS/$OSS_TGZ"
fi
VER="$("$TOOLS/oss-cad-suite/bin/verilator" --version | awk '{print $2}')"
if [ "$(printf '%s\n%s\n' "$VERILATOR_MIN" "$VER" | sort -V | head -1)" != "$VERILATOR_MIN" ]; then
    echo "ERROR: verilator $VER < $VERILATOR_MIN required by cocotb 2.0" >&2; exit 1
fi
echo "verilator $VER  |  $("$TOOLS/oss-cad-suite/bin/yosys" -V)  |  $("$TOOLS/oss-cad-suite/bin/iverilog" -V | head -1)"

step "Python venv -> $HW_ROOT/.venv (cocotb 2.0, pyuvm, pytest, cocotbext-axi, pyvcd)"
if [ ! -x "$HW_ROOT/.venv/bin/python" ]; then
    python3 -m venv --without-pip "$HW_ROOT/.venv"
fi
if [ ! -x "$HW_ROOT/.venv/bin/pip" ]; then
    # Debian/Ubuntu without python3-venv ship no ensurepip; bootstrap pip from PyPA instead.
    curl -sSL -o "$TOOLS/get-pip.py" https://bootstrap.pypa.io/get-pip.py
    "$HW_ROOT/.venv/bin/python" "$TOOLS/get-pip.py" -q
fi
"$HW_ROOT/.venv/bin/pip" install -q --upgrade pip
"$HW_ROOT/.venv/bin/pip" install -q -r "$HW_ROOT/requirements.txt"
"$HW_ROOT/.venv/bin/python" -c 'import cocotb, pyuvm; print("cocotb", cocotb.__version__, "| pyuvm", pyuvm.__version__ if hasattr(pyuvm, "__version__") else "ok")'

step "sky130_fd_sc_hd Liberty -> $TOOLS/pdk"
mkdir -p "$TOOLS/pdk"
if grep -q '^library' "$TOOLS/pdk/sky130_fd_sc_hd__tt_025C_1v80.lib" 2>/dev/null; then
    echo "already present"
else
    curl -fL --progress-bar -o "$TOOLS/pdk/sky130_fd_sc_hd__tt_025C_1v80.lib" "$LIB_URL"
    grep -q '^library' "$TOOLS/pdk/sky130_fd_sc_hd__tt_025C_1v80.lib" || { echo "ERROR: liberty download is not a liberty file" >&2; exit 1; }
fi

if [ "$WITH_OPENLANE" = 1 ]; then
    step "Nix (single-user) + OpenLane 2"
    if ! command -v nix >/dev/null 2>&1 && [ ! -f "$HOME/.nix-profile/etc/profile.d/nix.sh" ]; then
        # Official single-user installer; see https://nixos.org/download/ . Review before trusting.
        sh <(curl -L https://nixos.org/nix/install) --no-daemon
    fi
    . "$HOME/.nix-profile/etc/profile.d/nix.sh"
    mkdir -p "$HOME/.config/nix"
    grep -q 'experimental-features' "$HOME/.config/nix/nix.conf" 2>/dev/null || \
        echo 'experimental-features = nix-command flakes' >> "$HOME/.config/nix/nix.conf"
    grep -q 'openlane.cachix.org' "$HOME/.config/nix/nix.conf" 2>/dev/null || cat >> "$HOME/.config/nix/nix.conf" <<'EOF'
extra-substituters = https://openlane.cachix.org
extra-trusted-public-keys = openlane.cachix.org-1:qqdwh+QMNGmZAuyeQJTH9ErW57OWSvdtuwfBKdS254E=
EOF
    # OpenLane 2 via its flake (see https://openlane2.readthedocs.io/en/latest/getting_started/common/nix_installation/)
    nix profile install github:efabless/openlane2 || nix profile upgrade --all
    openlane --version
fi

step "Done. Activate with:  source hw/env.sh"
