#!/usr/bin/env bash
# Source this to put the hardware toolchain on PATH:  source hw/env.sh
# Everything lives under hw/tools (gitignored) and hw/.venv; nothing is installed system-wide.
HW_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export HW_ROOT
export PROJ_ROOT="$(cd "$HW_ROOT/.." && pwd)"
export OSS_CAD_SUITE="$HW_ROOT/tools/oss-cad-suite"
export PDK_LIB="$HW_ROOT/tools/pdk/sky130_fd_sc_hd__tt_025C_1v80.lib"

# Project venv first (cocotb, pyuvm, pytest), then the suite's binaries (verilator, yosys, iverilog, sby, gtkwave, surfer).
# The suite is NOT sourced via its own environment script on purpose: that would shadow python3 with its bundled interpreter.
[ -d "$HW_ROOT/.venv" ] && export PATH="$HW_ROOT/.venv/bin:$PATH" && export VIRTUAL_ENV="$HW_ROOT/.venv"
[ -d "$OSS_CAD_SUITE/bin" ] && export PATH="$OSS_CAD_SUITE/bin:$PATH"

# Nix (OpenLane 2), only if installed by setup.sh --with-openlane
[ -f "$HOME/.nix-profile/etc/profile.d/nix.sh" ] && . "$HOME/.nix-profile/etc/profile.d/nix.sh"

export PYTHONDONTWRITEBYTECODE=1
