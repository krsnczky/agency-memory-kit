#!/usr/bin/env python3
"""
system-briefing.py
Purpose: SessionStart hook - injects the system-level "Next session briefing"
         section from <world>/system/memory/learnings.md. Deterministic
         cross-session continuity for system/dev work, with no global vault.
         Also injects: the FULL context-load-order table (once per session start,
         incl. after compaction - the per-prompt injector only carries the short
         reminder block), and the approved Advisory section of tool-craft.md.
         Then runs the candidate nudge (open promotion/sweep heads-up).
Trigger: SessionStart (fires on startup/resume/clear/compact - so the full
         load-order survives compaction)
Notes:
  - Heading is config-driven (next_briefing_heading) so a non-English world works.
  - World root comes from agency_common (CLAUDE_PROJECT_DIR for hooks).
Changelog:
  2026-06-03 - Ported from system-briefing.sh; config-driven heading + world-root.
  2026-07-03 - Full context-load-order moved here from the per-prompt injector
               (progressive disclosure); tool-craft Advisory section injected
               (the approved advisory lessons never reached the model before);
               nudge runs via sys.executable and its failure is surfaced instead
               of vanishing.
"""

import subprocess
import sys

# Windows / non-UTF-8 locales: emoji in stdout would crash (e.g. cp1250). Force UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

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


def extract_advisory(text):
    """The '## ...Advisory...' section body of tool-craft.md (substring match, so
    an emoji-prefixed heading works). Empty string if missing or placeholder-only."""
    lines = text.splitlines()
    out = []
    grab = False
    for line in lines:
        if line.startswith("## "):
            grab = "Advisory" in line
            continue
        if grab:
            out.append(line)
    body = "\n".join(out).strip()
    # Placeholder-only section ("_None yet._" etc.) -> nothing to inject
    if not any(l.strip().startswith("- ") for l in body.splitlines()):
        return ""
    return body


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

    # Full context-load-order (per prompt only the short reminder block goes in;
    # SessionStart fires on compact too, so this survives compaction)
    load_order = world / "system" / "memory" / "context-load-order.md"
    if load_order.exists():
        try:
            content = load_order.read_text(encoding="utf-8").strip()
            if content:
                print(f"\n📋 CONTEXT LOAD ORDER - FULL TABLE (system/memory/context-load-order.md)\n{content}\n")
        except Exception:
            pass

    # Approved tool-craft Advisory lessons (the enforceable table is machine-read
    # by the guard; the advisory list is context - this is its delivery point)
    tool_craft = world / "system" / "memory" / "tool-craft.md"
    if tool_craft.exists():
        try:
            advisory = extract_advisory(tool_craft.read_text(encoding="utf-8"))
            if advisory:
                print(f"\n🧭 TOOL-CRAFT ADVISORY (approved lessons, system/memory/tool-craft.md)\n{advisory}\n")
        except Exception:
            pass

    # Candidate nudge (inherits CLAUDE_PROJECT_DIR -> same world). Runs with the
    # same interpreter as this hook (user_config python); a failure is surfaced
    # as one line instead of vanishing.
    nudge = PLUGIN_ROOT / "scripts" / "candidates_nudge.py"
    try:
        res = subprocess.run([sys.executable, str(nudge)], check=False,
                             capture_output=True, text=True)
        if res.stdout:
            print(res.stdout, end="")
        if res.returncode != 0:
            err_lines = (res.stderr or "").strip().splitlines()
            tail = err_lines[-1] if err_lines else "no stderr"
            print(f"⚠️ candidates_nudge failed (exit {res.returncode}): {tail}")
    except Exception as e:
        print(f"⚠️ candidates_nudge could not run: {e}")


if __name__ == "__main__":
    main()
