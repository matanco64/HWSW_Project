#!/usr/bin/env bash
# Mirror the presentation folder to a plain Windows folder the desktop agent can attach, and
# pull its outputs back. The agent cannot open \\wsl.localhost paths, so this is the bridge.
#
#   tools/presentation/sync_win.sh push   # assets/, prompts/ -> C:\Users\Kogan\HWSW_presentation\
#   tools/presentation/sync_win.sh pull   # screenshots/status from the mirror's verify\ and the
#                                         # newest deck_export.* from Downloads -> presentation/verify/
#   tools/presentation/sync_win.sh        # both
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WIN_USER=/mnt/c/Users/Kogan
MIRROR="$WIN_USER/HWSW_presentation"
DL="$WIN_USER/Downloads"
VERIFY="$ROOT/presentation/verify"

push() {
  mkdir -p "$MIRROR/verify"
  rsync -a --delete "$ROOT/presentation/assets/"  "$MIRROR/assets/"  --exclude 'chain_cosim.log'
  rsync -a --delete "$ROOT/presentation/prompts/" "$MIRROR/prompts/"
  cp "$ROOT/presentation/SLIDES_URL.txt" "$MIRROR/" 2>/dev/null || true
  echo "pushed assets ($(ls "$MIRROR/assets" | wc -l) files) and prompts ($(ls "$MIRROR/prompts" | wc -l) files) to $MIRROR"
}

pull() {
  mkdir -p "$VERIFY"
  # anything the agent or the human dropped into the mirror's verify folder
  if [ -d "$MIRROR/verify" ]; then
    rsync -a --exclude '*:Zone.Identifier' "$MIRROR/verify/" "$VERIFY/"
  fi
  # newest deck export in Downloads, whatever Google named it (deck_export.* or the deck title)
  for ext in pptx txt; do
    newest="$(ls -t "$DL"/deck_export.$ext "$DL"/HWSW*.$ext "$MIRROR"/verify/deck_export.$ext "$MIRROR"/verify/HWSW*.$ext 2>/dev/null | head -1 || true)"
    if [ -n "$newest" ]; then
      cp "$newest" "$VERIFY/deck_export.$ext"
      echo "pulled $(basename "$newest") ($(date -r "$newest" '+%H:%M:%S')) -> verify/deck_export.$ext"
    fi
  done
  echo "verify/ now has $(ls "$VERIFY" | grep -vc Zone.Identifier) entries"
}

case "${1:-both}" in
  push) push ;;
  pull) pull ;;
  both) push; pull ;;
  *) echo "usage: $0 [push|pull]"; exit 2 ;;
esac
