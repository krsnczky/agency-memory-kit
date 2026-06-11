#!/usr/bin/env python3
"""
session-logger.py
Purpose: Stop hook - archives the session trace into <world>/system/logs/sessions/.
         Only saves if SESSION_CONTEXT.md has a workflow trace AND was modified in the
         last 10 minutes (= active session). No-ops silently otherwise.
Trigger: Stop
Notes:
  - Pure Python (stdlib only) so it runs cross-platform (macOS / Linux / Windows) with no
    bash / `stat` dependency. Replaces session-logger.sh.
  - World root: AGENCY_WORLD_ROOT / CLAUDE_PROJECT_DIR / cwd (same order as the engine).
Changelog:
  2026-06-11 - Ported from session-logger.sh (drop the bash dependency for Windows).
"""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path


def world_root():
    for var in ("AGENCY_WORLD_ROOT", "CLAUDE_PROJECT_DIR"):
        val = os.environ.get(var)
        if val:
            return Path(val)
    return Path.cwd()


def main():
    world = world_root()
    session_file = world / ".claude" / "SESSION_CONTEXT.md"
    if not session_file.exists():
        return

    try:
        text = session_file.read_text(encoding="utf-8")
    except Exception:
        return

    # Real trace content? (a line starting with "- [")
    if not any(line.startswith("- [") for line in text.splitlines()):
        return

    # Modified in the last 10 minutes (600s)?
    try:
        if (datetime.now().timestamp() - session_file.stat().st_mtime) > 600:
            return
    except Exception:
        return

    log_dir = world / "system" / "logs" / "sessions"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")

    client = "unknown"
    m = re.search(r"Active client:\s*(.+)", text)
    if m:
        slug = m.group(1).strip().lower().replace(" ", "-")
        if slug and slug != "-":
            client = slug

    try:
        shutil.copy(session_file, log_dir / f"{timestamp}-{client}.md")
    except Exception:
        pass


if __name__ == "__main__":
    main()
