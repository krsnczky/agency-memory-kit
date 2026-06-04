#!/usr/bin/env python3
"""
agency_common.py
Purpose: Shared resolution layer for the agency-memory plugin. Two jobs:
  1. Find the WORLD root - the user's data (clients/, system/memory/).
  2. Load the world CONFIG (section names, protected/evergreen sets, memory-guard
     rules) so the engine is not hardcoded to one language or one agency.

Engine/data split (the core of the plugin):
  - The plugin (engine) locates ITSELF via __file__ (== ${CLAUDE_PLUGIN_ROOT}).
  - The user's DATA (world) is resolved SEPARATELY, because one engine serves
    many worlds and runs both inside Claude Code (hooks, has CLAUDE_PROJECT_DIR)
    and from cron/launchd (no Claude env at all).

World root resolution order (every script uses this, identically):
  1. explicit --world arg / AGENCY_WORLD_ROOT env
  2. CLAUDE_PROJECT_DIR env (Claude Code sets this for hook processes)
  3. cwd fallback

World config (the "instance" layer of the 3-layer vision):
  Loaded from <world>/system/memory/world.json, merged over the plugin's bundled
  world.default.json (English). A non-English world ships its own world.json that
  overrides section names etc. - the engine never hardcodes them.
Changelog:
  2026-06-03 - Initial version (plugin conversion: engine/data split + config layer).
"""

import json
import os
import re
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "world.default.json"


def resolve_world_root(explicit=None):
    """Return the world root (user data) as an absolute Path. See order above."""
    if explicit:
        return Path(explicit).expanduser().resolve()
    env_world = os.environ.get("AGENCY_WORLD_ROOT")
    if env_world:
        return Path(env_world).expanduser().resolve()
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir:
        return Path(project_dir).expanduser().resolve()
    return Path.cwd().resolve()


def _merge(base, override):
    """Shallow merge; nested dicts (e.g. memory_guard) merged one level deep."""
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            merged = dict(out[k])
            merged.update(v)
            out[k] = merged
        else:
            out[k] = v
    return out


def load_world_config(world_root):
    """Bundled English defaults, with <world>/system/memory/world.json layered on top."""
    config = {}
    try:
        with open(DEFAULT_CONFIG_PATH, encoding="utf-8") as f:
            config = json.load(f)
    except Exception:
        config = {}

    override_path = Path(world_root) / "system" / "memory" / "world.json"
    if override_path.exists():
        try:
            with open(override_path, encoding="utf-8") as f:
                override = json.load(f)
            config = _merge(config, override)
        except Exception:
            pass  # malformed override -> fall back to defaults, never crash a hook
    return config


def default_project_memory_path(world_root):
    """Derive the Claude Code project auto-memory dir from the world root,
    matching Claude Code's own slug scheme: ~/.claude/projects/<slug>/memory
    where <slug> is the absolute world path with every character outside
    [A-Za-z0-9_-] replaced by '-'. NB: this includes spaces (e.g. a path like
    '.../Axon Digital' -> '...-Axon-Digital'), dots, etc. - not just '/'. Verified
    against real slugs (incl. a 'First project' -> 'First-project' case)."""
    slug = re.sub(r"[^A-Za-z0-9_-]", "-", str(Path(world_root).resolve()))
    return Path("~/.claude/projects").expanduser() / slug / "memory"
