#!/usr/bin/env python3
"""
candidates_nudge.py
Purpose: SessionStart nudge - a GLOBAL heads-up (not a dump): how many candidates are
         waiting, split client vs global. CLIENT candidates (wiki-promotion + client
         sweep) are NOT surfaced in detail here - they come up when you load that client,
         scoped to that client only (client_candidates.py, point-of-use). Here it is just
         the count + a pointer to the global rule candidates (promotion + system sweep).
         Pure stdlib, read-only.
Usage:
  python3 candidates_nudge.py        # world via AGENCY_WORLD_ROOT / CLAUDE_PROJECT_DIR / cwd
Changelog:
  2026-06-03 - Plugin conversion: STATE_PATH via agency_common world-root.
"""

import json
from datetime import datetime

from agency_common import resolve_world_root

STATE_PATH = resolve_world_root() / "system" / "memory" / "candidates-state.json"


def _weeks_since(date_str):
    try:
        return (datetime.now() - datetime.strptime(date_str, "%Y-%m-%d")).days // 7
    except Exception:
        return 0


def main():
    if not STATE_PATH.exists():
        return
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return

    opens = [c for c in state.get("candidates", []) if c.get("status") == "open"]
    if not opens:
        return

    # Client-scoped (surfaced when that client loads, only for that one) vs global (shown here)
    GLOBAL_SCOPES = {"global", "system"}
    client_cands = [c for c in opens if c.get("scope") not in GLOBAL_SCOPES and c["type"] in ("wiki-promotion", "sweep")]
    global_cands = [c for c in opens if c not in client_cands]
    clients = sorted({c["scope"] for c in client_cands})
    oldest = max(_weeks_since(c.get("first_seen", "")) for c in opens)
    age = "this week" if oldest == 0 else f"oldest {oldest}w waiting"

    parts = []
    if client_cands:
        parts.append(f"{len(client_cands)} client candidate(s) across {len(clients)} client(s)")
    if global_cands:
        parts.append(f"{len(global_cands)} global rule candidate(s)")
    print(f"🔔 Memory candidate review: {' + '.join(parts)} waiting ({age}). "
          f"Client candidates surface when you load that client (scoped to it only). "
          f"Global: promotion-candidates.md / sweep-candidates.md.")


if __name__ == "__main__":
    main()
