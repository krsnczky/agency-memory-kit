#!/bin/bash
# run-weekly.sh
# Generic wrapper for the weekly consolidation. Used by the launchd plist, by cron, or
# standalone. Sources the API key (cron/launchd do NOT load your shell rc) and runs
# consolidate.py against the world root.
#
# Required: AGENCY_WORLD_ROOT must point at your world (the data root: clients/, system/).
# Optional: ~/.anthropic.env may export ANTHROPIC_API_KEY (sourced if present).
#
# Usage:
#   AGENCY_WORLD_ROOT=/path/to/world bash run-weekly.sh
set -euo pipefail

# 1) API key (cron/launchd run with a bare environment)
if [ -f "$HOME/.anthropic.env" ]; then
  # shellcheck disable=SC1090
  source "$HOME/.anthropic.env"
fi

# 2) Locate the plugin (this script lives in <plugin>/runners/)
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 3) World root
WORLD="${AGENCY_WORLD_ROOT:?Set AGENCY_WORLD_ROOT to your world root (clients/ + system/)}"

exec python3 "$PLUGIN_DIR/scripts/consolidate.py" --world "$WORLD"
