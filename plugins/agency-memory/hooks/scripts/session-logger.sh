#!/bin/bash
# session-logger.sh
# Claude Code Stop hook - archives the session trace into <world>/system/logs/sessions/
# Only saves if SESSION_CONTEXT.md contains a workflow trace
# and was modified in the last 10 minutes (= active session).
# No-ops silently if .claude/SESSION_CONTEXT.md does not exist.
# Changelog:
#   2026-05-27 - Portability: hardcoded paths -> $(pwd) based dynamic paths
#   2026-05-31 - Extracted to agency-memory-kit; English client label
#   2026-06-03 - Plugin conversion: world root via AGENCY_WORLD_ROOT / CLAUDE_PROJECT_DIR / pwd

WORLD="${AGENCY_WORLD_ROOT:-${CLAUDE_PROJECT_DIR:-$(pwd)}}"
SESSION_FILE="$WORLD/.claude/SESSION_CONTEXT.md"
LOG_DIR="$WORLD/system/logs/sessions"

# Does the file exist?
if [ ! -f "$SESSION_FILE" ]; then
  exit 0
fi

# Does it contain real trace content?
if ! grep -q "^\- \[" "$SESSION_FILE" 2>/dev/null; then
  exit 0
fi

# Modified in the last 10 minutes? (600 seconds)
LAST_MODIFIED=$(stat -f "%m" "$SESSION_FILE" 2>/dev/null || stat -c "%Y" "$SESSION_FILE" 2>/dev/null)
NOW=$(date +%s)
DIFF=$((NOW - LAST_MODIFIED))

if [ "$DIFF" -gt 600 ]; then
  exit 0
fi

# All conditions met - save
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +"%Y-%m-%d-%H%M")

# Client name from the file (if present)
CLIENT=$(grep "Active client:" "$SESSION_FILE" | sed 's/.*Active client: //' | tr ' ' '-' | tr '[:upper:]' '[:lower:]' | head -1)
if [ -z "$CLIENT" ] || [ "$CLIENT" = "-" ]; then
  CLIENT="unknown"
fi

LOG_FILE="$LOG_DIR/${TIMESTAMP}-${CLIENT}.md"
cp "$SESSION_FILE" "$LOG_FILE"

exit 0
