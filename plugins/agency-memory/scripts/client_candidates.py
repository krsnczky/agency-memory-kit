#!/usr/bin/env python3
"""
client_candidates.py
Purpose: Print one client's OPEN memory candidates (client-learning + wiki-promotion + sweep)
         from candidates-state.json. Point-of-use surfacing: when you work on that client,
         only THAT client's candidates come up (no-mixing, clarity). Promotion (scope=global)
         and tool-craft (scope=system) are NOT client-scoped - they stay in the global nudge /
         review files. Pure stdlib (no anthropic), read-only.
Usage:
  python3 client_candidates.py acme-corp   # world via AGENCY_WORLD_ROOT / CLAUDE_PROJECT_DIR / cwd
Changelog:
  2026-06-03 - Plugin conversion: STATE_PATH via agency_common world-root.
  2026-06-08 - Added the client-learning type to CLIENT_TYPES (the dream_extractor v2 stream
               was missing from point-of-use surfacing - found during beta review).
"""

import json
import sys
from datetime import datetime

from agency_common import resolve_world_root

STATE_PATH = resolve_world_root() / "system" / "memory" / "candidates-state.json"
CLIENT_TYPES = ("client-learning", "wiki-promotion", "sweep")


def _weeks_since(date_str):
    try:
        return (datetime.now() - datetime.strptime(date_str, "%Y-%m-%d")).days // 7
    except Exception:
        return 0


def _age(c):
    w = _weeks_since(c.get("first_seen", ""))
    return "this week" if w == 0 else f"{w}w waiting"


def candidates_for(client, state):
    return [c for c in state.get("candidates", [])
            if c.get("status") == "open" and c.get("scope") == client and c.get("type") in CLIENT_TYPES]


def main():
    if len(sys.argv) < 2:
        print("Usage: client_candidates.py <client-folder-name>", file=sys.stderr)
        sys.exit(1)
    client = sys.argv[1]
    if not STATE_PATH.exists():
        return
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return

    rows = candidates_for(client, state)
    if not rows:
        return

    learn = [c for c in rows if c["type"] == "client-learning"]
    wiki = [c for c in rows if c["type"] == "wiki-promotion"]
    sweep = [c for c in rows if c["type"] == "sweep"]

    print(f"🔔 [{client}] memory candidate review waiting (from weekly consolidation):")
    if learn:
        print("  CLIENT-LEARNING (durable learning from the transcript -> memory/learnings.md):")
        for c in learn:
            print(f"    #{c['id']} ({_age(c)}) {c['text']}")
    if wiki:
        print("  WIKI-PROMOTION (durable account fact -> campaigns-<area>.md):")
        for c in wiki:
            print(f"    #{c['id']} ({_age(c)}) {c['text']}")
    if sweep:
        print("  SWEEP (proposed for archiving):")
        for c in sweep:
            print(f"    #{c['id']} ({_age(c)}) {c['text']}")
    print("  -> Tell me which #id to accept / reject.")


if __name__ == "__main__":
    main()
