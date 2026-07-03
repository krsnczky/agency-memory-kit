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
  2026-07-03 - FIX: plain-stdout output is INVISIBLE to the model on PreToolUse
               exit 0 - the hook was a silent no-op. Warnings now go through
               hookSpecificOutput.additionalContext (same pattern as
               tool_craft_guard.py).
  2026-07-03 - No-mixing guard on the AGENT write path: writing under
               clients/<X>/ with content that mentions ANOTHER known client
               triggers a WARN. The machine gate existed only on the
               transcript-mining path (dream_extractor leak check); the primary
               path - the agent writing a client's memory at session end - was
               convention-only. Automatic when <world>/clients/ exists; no
               config needed.
"""

import json
import os
import re
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


def no_mixing_warning(world, file_path, tool_input):
    """WARN when a write under clients/<X>/ mentions another known client by name.
    file_path arrives lowercased. WARN-only: legit cross-client references exist
    (e.g. a comparison note), but they must be a conscious choice, never an accident."""
    clients_dir = world / "clients"
    if not clients_dir.is_dir():
        return None
    m = re.search(r"/clients/([^/]+)/", file_path)
    if not m:
        return None
    target = m.group(1)
    try:
        known = {d.name.lower() for d in clients_dir.iterdir()
                 if d.is_dir() and not d.name.startswith((".", "_"))}
    except Exception:
        return None
    if target not in known:
        return None
    content = " ".join(
        str(tool_input.get(k, "")) for k in ("content", "new_string")
    ).lower()
    if not content:
        return None
    hits = sorted(c for c in known - {target}
                  if c in content or c.replace("-", " ") in content)
    if not hits:
        return None
    return (f"⚠️ NO-MIXING GUARD: you are writing under clients/{target}/ but the "
            f"content mentions other known client(s): {', '.join(hits)}. Client info "
            f"must NEVER land in another client's folder - verify this reference is "
            f"intentional before proceeding.")


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

    warnings = []

    # No-mixing check: config-free, runs whenever the world has a clients/ dir
    mix = no_mixing_warning(world, file_path, tool_input)
    if mix:
        warnings.append(mix)

    if guards:
        configured_path = mg.get("project_memory_path")
        if configured_path:
            memory_dir = Path(os.path.expanduser(configured_path))
        else:
            memory_dir = default_project_memory_path(world)

        for guard in guards:
            patterns = guard.get("patterns", [])
            if not any(pat.lower() in file_path for pat in patterns):
                continue
            for mem_file in guard.get("memories", []):
                content = load_memory(memory_dir, mem_file)
                if content:
                    label = guard.get("label", "")
                    warnings.append(
                        f"🧠 MEMORY GUARD [{label}] - {mem_file}\n{content}"
                    )

    if warnings:
        # PreToolUse: exit-0 stdout is NOT surfaced to the model - the warning
        # MUST go through the hookSpecificOutput JSON (see tool_craft_guard.py).
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "additionalContext": "\n\n".join(warnings),
            }
        }))

    sys.exit(0)


if __name__ == "__main__":
    main()
