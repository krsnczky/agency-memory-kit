#!/bin/bash
# install.sh - one-time setup helper for agency-memory-kit (plugin model).
# Safe to re-run (idempotent). Run from the repo root: bash install.sh
#
# The hooks themselves are NOT wired here anymore - they ship inside the plugin
# (plugins/agency-memory/hooks/hooks.json) and activate when you install the plugin in
# Claude Code. This script just checks your environment and prints the next steps.
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "agency-memory-kit setup (plugin model)"
echo "--------------------------------------"

# 1. python3 present?
if command -v python3 >/dev/null 2>&1; then
  echo "[ok] python3 found ($(python3 --version 2>&1))"
else
  echo "[!!] python3 not found - the hooks and scripts need it. Install python3."
fi

# 2. anthropic package (only needed for the weekly consolidate.py)
if python3 -c "import anthropic" >/dev/null 2>&1; then
  echo "[ok] anthropic package found (consolidate.py ready)"
else
  echo "[--] anthropic package not installed. Only needed for consolidate.py."
  echo "     Install when you want weekly consolidation:  pip install anthropic"
fi

# 3. Make the runner scripts executable
chmod +x plugins/agency-memory/runners/run-weekly.sh 2>/dev/null || true
chmod +x plugins/agency-memory/hooks/scripts/session-logger.sh 2>/dev/null || true
echo "[ok] runner / hook shell scripts are executable"

# 4. API key for consolidate.py
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  echo "[ok] ANTHROPIC_API_KEY is set in this shell"
else
  echo "[--] ANTHROPIC_API_KEY not set. consolidate.py (weekly) needs it."
fi

echo ""
echo "Next:"
echo "  1) Install the plugin in Claude Code:"
echo "       /plugin marketplace add $ROOT"
echo "       /plugin install agency-memory@agency-memory-kit"
echo ""
echo "  2) Set up a world (your data root) - or use this repo root as one:"
echo "       cp -r plugins/agency-memory/templates/world/* /path/to/my-world/"
echo "     Then run Claude Code from your world folder."
echo ""
echo "  3) (Optional) Localize: copy system/memory/world.json.example to world.json and edit."
echo ""
echo "  4) Create your first client (run from the kit repo, which carries _template):"
echo "       bash new-client.sh <client-slug>"
echo ""
echo "Weekly consolidation (optional but recommended):"
echo "  consolidate.py calls the Claude API, so it needs ANTHROPIC_API_KEY."
echo "  Put the key in a dedicated env file (cron/launchd do NOT load your shell rc):"
echo "    echo 'export ANTHROPIC_API_KEY=sk-ant-...' > ~/.anthropic.env && chmod 600 ~/.anthropic.env"
echo ""
echo "  Run it once against your world:"
echo "    AGENCY_WORLD_ROOT=/path/to/my-world bash plugins/agency-memory/runners/run-weekly.sh"
echo ""
echo "  Schedule it with a template in plugins/agency-memory/runners/ (launchd or GitHub Actions)."
