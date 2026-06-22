#!/usr/bin/env python3
"""
memory-guard.py
Purpose: PreToolUse hook - before a Write/Edit, surface the relevant project
         memory constraints so the agent must take them into account.
Trigger: PreToolUse (matcher: Write|Edit)
Engine/data split:
  - Mechanism (match file path -> print matching memory files) lives here (plugin).
  - The GUARDS list and the project-memory path live in the WORLD config
    (memory_guard.guards / memory_guard.project_memory_path). A world with no
    guards configured -> this hook is a silent no-op.
Changelog:
  2026-05-26 - Initial version
  2026-05-27 - Portability: hardcoded paths -> dynamic paths
  2026-06-03 - Plugin conversion: GUARDS + project path moved to world config;
               mechanism stays generic.
"""

import json
import os
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
from agency_common import (  # noqa: E402
    resolve_world_root,
    load_world_config,
    default_project_memory_path,
)


def load_memory(memory_dir, filename):
    path = Path(memory_dir) / filename
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8")
        # Strip frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return parts[2].strip()
        return content.strip()
    except Exception:
        return None


def main():
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    file_path = tool_input.get("file_path", "").lower()
    if not file_path:
        sys.exit(0)

    world = resolve_world_root()
    config = load_world_config(world)
    mg = config.get("memory_guard", {}) or {}
    guards = mg.get("guards", []) or []
    if not guards:
        sys.exit(0)  # no guards configured for this world -> no-op

    configured_path = mg.get("project_memory_path")
    if configured_path:
        memory_dir = Path(os.path.expanduser(configured_path))
    else:
        memory_dir = default_project_memory_path(world)

    warnings = []
    for guard in guards:
        patterns = guard.get("patterns", [])
        if not any(pat.lower() in file_path for pat in patterns):
            continue
        for mem_file in guard.get("memories", []):
            content = load_memory(memory_dir, mem_file)
            if content:
                label = guard.get("label", "")
                warnings.append(
                    f"🧠 MEMORY GUARD [{label}] — {mem_file}\n{content}"
                )

    if warnings:
        print("\n" + "\n\n".join(warnings) + "\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
