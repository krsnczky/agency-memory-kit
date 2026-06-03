#!/usr/bin/env python3
"""
system-briefing.py
Purpose: SessionStart hook - injects the system-level "Next session briefing"
         section from <world>/system/memory/learnings.md. Deterministic
         cross-session continuity for system/dev work, with no global vault.
         Then runs the candidate nudge (open promotion/sweep heads-up).
Trigger: SessionStart
Notes:
  - Heading is config-driven (next_briefing_heading) so a non-English world works.
  - World root comes from agency_common (CLAUDE_PROJECT_DIR for hooks).
Changelog:
  2026-06-03 - Ported from system-briefing.sh; config-driven heading + world-root.
"""

import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
from agency_common import resolve_world_root, load_world_config  # noqa: E402


def extract_section(text, heading):
    """Return the named '## <heading>' section verbatim (heading line included),
    stopping at the next '## ' heading. Empty string if not found."""
    lines = text.splitlines()
    out = []
    grab = False
    for line in lines:
        if line.startswith("## ") and line[3:].strip() == heading:
            grab = True
            out.append(line)
            continue
        if grab and line.startswith("## "):
            break
        if grab:
            out.append(line)
    return "\n".join(out).strip()


def main():
    world = resolve_world_root()
    config = load_world_config(world)
    heading = config.get("next_briefing_heading", "Next session briefing")

    learnings = world / "system" / "memory" / "learnings.md"
    if learnings.exists():
        try:
            text = learnings.read_text(encoding="utf-8")
            section = extract_section(text, heading)
            if section:
                print(section)
        except Exception:
            pass

    # Candidate nudge (inherits CLAUDE_PROJECT_DIR -> same world)
    nudge = PLUGIN_ROOT / "scripts" / "candidates_nudge.py"
    try:
        subprocess.run(["python3", str(nudge)], check=False)
    except Exception:
        pass


if __name__ == "__main__":
    main()
