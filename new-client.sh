#!/bin/bash
# new-client.sh - scaffold a new client folder from clients/_template
# Usage: bash new-client.sh <client-slug>
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

SLUG="$1"
if [ -z "$SLUG" ]; then
  echo "Usage: bash new-client.sh <client-slug>   (e.g. acme-corp)"
  exit 1
fi

TARGET="clients/$SLUG"
if [ -e "$TARGET" ]; then
  echo "[!!] $TARGET already exists. Aborting (will not overwrite)."
  exit 1
fi

cp -r clients/_template "$TARGET"
mkdir -p "$TARGET/raw"
touch "$TARGET/raw/.gitkeep"

echo "[ok] created $TARGET from template"
echo ""
echo "Next: fill in the placeholders ([CLIENT NAME], [DATE], etc.) in:"
echo "  $TARGET/.claude/CLAUDE.md"
echo "  $TARGET/wiki/index.md"
echo "  $TARGET/wiki/profil.md"
echo "  $TARGET/wiki/hot.md"
