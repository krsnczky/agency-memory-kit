#!/bin/bash
# install.sh - one-time setup helper for agency-memory-kit (macOS / Linux).
# Safe to re-run (idempotent). Run from the repo root: bash install.sh
#
# What this does:
#   1. Finds (or offers to install) Python 3.
#   2. Tells you the EXACT command to type into the Claude Code plugin config
#      prompt ("Python command") when you install the plugin.
#   3. Checks the optional anthropic package (only the weekly consolidate.py needs it).
#   4. Prints the remaining setup steps.
#
# The hooks are NOT wired here - they ship inside the plugin
# (plugins/agency-memory/hooks/hooks.json) and activate when you install the
# plugin in Claude Code.
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "agency-memory-kit setup (macOS / Linux)"
echo "---------------------------------------"

# --- 1. Find a working Python 3 -------------------------------------------------
# Returns the command name (python3 / python) that runs Python 3.x, or empty.
find_python() {
  for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
      if "$cmd" -c 'import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)' >/dev/null 2>&1; then
        echo "$cmd"
        return 0
      fi
    fi
  done
  return 1
}

PYCMD="$(find_python || true)"

if [ -z "$PYCMD" ]; then
  echo "[!!] No Python 3 found on this machine."
  # Detect a package manager and offer to install.
  INSTALL_CMD=""
  if [ "$(uname)" = "Darwin" ]; then
    if command -v brew >/dev/null 2>&1; then
      INSTALL_CMD="brew install python"
    else
      echo ""
      echo "Homebrew is not installed. Install it first from https://brew.sh, then re-run this script."
      echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
      exit 1
    fi
  else
    # Linux: pick the first package manager we recognize.
    if command -v apt-get >/dev/null 2>&1; then
      INSTALL_CMD="sudo apt-get update && sudo apt-get install -y python3 python3-pip"
    elif command -v dnf >/dev/null 2>&1; then
      INSTALL_CMD="sudo dnf install -y python3 python3-pip"
    elif command -v pacman >/dev/null 2>&1; then
      INSTALL_CMD="sudo pacman -S --noconfirm python python-pip"
    elif command -v zypper >/dev/null 2>&1; then
      INSTALL_CMD="sudo zypper install -y python3 python3-pip"
    else
      echo "Could not detect your package manager. Install Python 3 manually, then re-run this script."
      exit 1
    fi
  fi

  echo ""
  echo "I can install Python 3 with:"
  echo "    $INSTALL_CMD"
  printf "Run it now? [y/N] "
  read -r answer
  case "$answer" in
    [yY]|[yY][eE][sS])
      eval "$INSTALL_CMD"
      PYCMD="$(find_python || true)"
      if [ -z "$PYCMD" ]; then
        echo "[!!] Install ran but Python 3 still not found. Open a new terminal and re-run this script."
        exit 1
      fi
      ;;
    *)
      echo "Skipped. Install Python 3 yourself, then re-run this script."
      exit 1
      ;;
  esac
fi

echo "[ok] Python 3 found:  $PYCMD  ($("$PYCMD" --version 2>&1))"

# --- 2. The value to enter in the plugin config --------------------------------
echo ""
echo ">>> When Claude Code asks for the \"Python command\" during plugin install,"
echo ">>> enter exactly:   $PYCMD"
echo ""

# --- 3. anthropic package (only the weekly consolidate.py needs it) ------------
if "$PYCMD" -c "import anthropic" >/dev/null 2>&1; then
  echo "[ok] anthropic package found (consolidate.py ready)"
else
  echo "[--] anthropic package not installed. Only needed for weekly consolidate.py."
  echo "     Install when you want weekly consolidation:  $PYCMD -m pip install anthropic"
fi

# --- 4. Make the runner script executable --------------------------------------
chmod +x plugins/agency-memory/runners/run-weekly.sh 2>/dev/null || true
echo "[ok] weekly runner script is executable"

# --- 5. API key for consolidate.py ---------------------------------------------
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  echo "[ok] ANTHROPIC_API_KEY is set in this shell"
else
  echo "[--] ANTHROPIC_API_KEY not set. consolidate.py (weekly) needs it."
fi

echo ""
echo "Next steps:"
echo "  1) Install the plugin in Claude Code:"
echo "       /plugin marketplace add $ROOT"
echo "       /plugin install agency-memory@agency-memory-kit"
echo "     When asked for the Python command, enter:   $PYCMD"
echo ""
echo "  2) Set up a world (your data root) - or use this repo root as one:"
echo "       cp -r plugins/agency-memory/templates/world/* /path/to/my-world/"
echo "     Then run Claude Code from your world folder."
echo ""
echo "  3) (Optional) Localize: copy system/memory/world.json.example to world.json and edit."
echo ""
echo "  4) Create your first client (run from the kit repo, which carries the template):"
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
echo "  Schedule it with a template in plugins/agency-memory/runners/ (launchd or systemd)."
