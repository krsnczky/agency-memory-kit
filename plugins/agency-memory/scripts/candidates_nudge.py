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
  2026-07-03 - Robustness: missing type/scope keys no longer crash the nudge, and an
               unexpected error prints one line instead of a swallowed traceback.
               New consumers: tool-craft violation escalation (a WARN rule hit >=5x
               is surfaced as DENY-ripe) + a warning when the last weekly run's
               transcript-mining (Dreaming) branch failed.
"""

import json
import sys
from datetime import datetime

# Windows / non-UTF-8 locales: emoji in stdout would crash (e.g. cp1250). Force UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


from agency_common import resolve_world_root

WORLD = resolve_world_root()
STATE_PATH = WORLD / "system" / "memory" / "candidates-state.json"
VIOLATIONS_PATH = WORLD / "system" / "memory" / "tool-craft-violations.json"
ESCALATION_THRESHOLD = 5  # a WARN rule hit this many times is DENY-ripe


def _weeks_since(date_str):
    try:
        return (datetime.now() - datetime.strptime(date_str, "%Y-%m-%d")).days // 7
    except Exception:
        return 0


def candidates_nudge(state):
    opens = [c for c in state.get("candidates", []) if c.get("status") == "open"]
    if not opens:
        return

    # Client-scoped (surfaced when that client loads, only for that one) vs global (shown here)
    GLOBAL_SCOPES = {"global", "system"}
    client_cands = [c for c in opens if c.get("scope") not in GLOBAL_SCOPES
                    and c.get("type") in ("wiki-promotion", "sweep", "client-learning")]
    global_cands = [c for c in opens if c not in client_cands]
    clients = sorted({c.get("scope", "?") for c in client_cands})
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

    # #11: global/system candidates have NO point-of-use venue (no client load ever
    # surfaces them), so a count alone lets them rot. Show the oldest few in full.
    GLOBAL_DETAIL_CAP = 5
    details = sorted((c for c in global_cands if c.get("scope") in GLOBAL_SCOPES),
                     key=lambda c: c.get("first_seen", ""))
    if details:
        print("   Oldest global/system candidates (accept/reject by #id):")
        for c in details[:GLOBAL_DETAIL_CAP]:
            w = _weeks_since(c.get("first_seen", ""))
            age_s = "this week" if w == 0 else f"{w}w"
            text = c.get("text", "")
            if len(text) > 220:
                text = text[:220] + "..."
            print(f"    #{c.get('id', '?')} [{c.get('type', '?')}] ({age_s}) {text}")
        if len(details) > GLOBAL_DETAIL_CAP:
            print(f"    ... +{len(details) - GLOBAL_DETAIL_CAP} more in the review files")


def last_run_nudge(state):
    """Warn when the last weekly run's transcript-mining (Dreaming) branch failed -
    without this the failure is silent and that week's learnings quietly age out."""
    lr = state.get("last_run") or {}
    if lr and not lr.get("new_extractors_ok", True):
        err = lr.get("error") or "unknown error"
        print(f"⚠️ Last weekly consolidation ({lr.get('date', '?')}): the transcript-mining "
              f"(Dreaming) branch FAILED: {err}. The 10-day overlap window covers the gap "
              f"if the next run succeeds; otherwise mine manually (dream_extractor.py --days N).")


def violations_nudge():
    """Close the WARN->DENY escalation loop: surface rules that keep getting hit."""
    if not VIOLATIONS_PATH.exists():
        return
    try:
        counts = json.loads(VIOLATIONS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return
    ripe = sorted(((k, v) for k, v in counts.items()
                   if isinstance(v, int) and v >= ESCALATION_THRESHOLD),
                  key=lambda kv: -kv[1])
    if ripe:
        listing = ", ".join(f"rule #{k}: {v}x" for k, v in ripe)
        print(f"🔔 Tool-craft WARN escalation ripe: {listing} - repeatedly violated despite "
              f"the warning. Consider promoting to DENY in tool-craft.md (needs your approval).")


def main():
    state = {}
    if STATE_PATH.exists():
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    try:
        if state:
            candidates_nudge(state)
            last_run_nudge(state)
        violations_nudge()
    except Exception as e:
        # Surface as one line (lands in the briefing) instead of a swallowed traceback
        print(f"⚠️ candidates_nudge error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
