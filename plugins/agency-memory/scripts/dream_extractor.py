#!/usr/bin/env python3
"""
dream_extractor.py
Purpose: The "cheap-Dreaming" extractor. For each cleanly single-client session (MEDIUM gate,
         no-mixing safe) it reads the RAW transcript text (the ~3% signal, tool-noise stripped)
         and the client's current learnings.md, then an LLM pass surfaces DURABLE learnings
         about THAT client that are NOT already recorded. This recovers learnings from sessions
         where the session-end capture never ran (abandoned/compacted sessions) - the transcript
         persists regardless. Includes bi-temporal dating (true_as_of) and a no-mixing leak check.
         DRY-RUN prints; candidates() returns {type, scope, text} for the consolidation cadence.
Options:
  python3 dream_extractor.py                 # last 7 days of MEDIUM single-client sessions
  python3 dream_extractor.py --days 24
Requires: anthropic + ANTHROPIC_API_KEY.
Notes:
  - MEDIUM gate (classify_client) is the no-mixing firewall: only sessions where one client
    dominates are mined, so every learning is about that one client. The prompt also says
    "only about <client>", and a post-pass DROPS any candidate naming another known client.
"""

import argparse
import json
import os
import re
import time
from pathlib import Path

import anthropic
import transcript_lib as tl

try:
    from agency_common import resolve_world_root, load_world_config
except Exception:
    def resolve_world_root(explicit=None):
        return explicit or os.environ.get("AGENCY_WORLD_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

    def load_world_config(world_root):
        return {}


def _output_language():
    """The world's output language for generated learnings (default English)."""
    try:
        return load_world_config(resolve_world_root()).get("output_language", "English")
    except Exception:
        return "English"

TEXT_CHAR_CAP = 44000   # ~12k tokens of transcript text per session

SYSTEM = ("You are the client-memory miner of an agency's AI system. You receive the raw text "
          "of ONE work session that was about a single client, plus that client's current "
          "learnings.md. You surface durable, account-specific learnings that are NOT already "
          "recorded. You NEVER invent; only what the transcript supports.")

PROMPT = """Client: {client}
Today: {today}

This session was about {client} only. Extract DURABLE learnings about {client} that are NOT
already in the learnings.md below.

A learning qualifies ONLY if: (a) durable (holds beyond this one day - a preference, a baseline,
a what-works/what-failed, a constraint), (b) actionable, (c) grounded in the transcript.
NOT a learning: a one-off task step, a raw daily metric with no takeaway, a restatement of an
existing entry, speculation. If something is about a DIFFERENT client, SKIP it.

For each learning output an object:
  - "learning": one grounded sentence, written in {language}
  - "true_as_of": the date this became true (YYYY-MM-DD) if the transcript shows it, else "unknown"
  - "confidence": "high" | "medium"

Output ONLY a JSON array (possibly empty), nothing else.

=== CURRENT learnings.md ===
{learnings}

=== RAW SESSION TEXT ({n} chars{trunc}) ===
{text}
"""


def clients_dir():
    return Path(resolve_world_root()) / "clients"


def known_clients():
    cd = clients_dir()
    if not cd.is_dir():
        return set()
    return {d.name for d in cd.iterdir()
            if d.is_dir() and not d.name.startswith((".", "_"))}


def mine(tdir, days=7, model="claude-opus-4-8"):
    today = time.strftime("%Y-%m-%d")
    cutoff = time.time() - days * 86400
    clients = known_clients()
    cdir = clients_dir()
    files = [f for f in tl.session_files(tdir) if os.path.getmtime(f) >= cutoff]
    targets = []
    for f in files:
        s = tl.scan_session(f)
        main_c, share, ok = tl.classify_client(s["clients"], "medium")
        if ok and main_c in clients:
            targets.append((f, main_c))

    client = anthropic.Anthropic()
    rows, tin, tout = [], 0, 0
    for f, main_c in targets:
        text = tl.extract_text(f)
        trunc = ", TRUNCATED" if len(text) > TEXT_CHAR_CAP else ""
        text = text[:TEXT_CHAR_CAP]
        lpath = cdir / main_c / "memory" / "learnings.md"
        learnings = lpath.read_text(encoding="utf-8") if lpath.exists() else "(no learnings.md)"
        prompt = PROMPT.format(client=main_c, today=today, learnings=learnings[:6000],
                               n=len(text), trunc=trunc, text=text,
                               language=_output_language())
        resp = client.messages.create(model=model, max_tokens=1200, system=SYSTEM,
                                      messages=[{"role": "user", "content": prompt}])
        tin += resp.usage.input_tokens
        tout += resp.usage.output_tokens
        try:
            m = re.search(r"\[.*\]", resp.content[0].text, re.DOTALL)
            items = json.loads(m.group(0)) if m else []
        except Exception:
            items = []
        others = clients - {main_c}
        for it in items:
            t = (it.get("learning") or "").lower()
            leak = next((c for c in others if c.replace("-", " ") in t or c in t), None)
            rows.append((main_c, it, leak))
    return rows, tin, tout


def candidates(tdir, days=7, model="claude-opus-4-8"):
    """Client-learning candidates in the {type, scope, text} shape. LEAK candidates (mention
    another client) are DROPPED, not queued - no-mixing safety over recall."""
    rows, _, _ = mine(tdir, days, model)
    out = []
    for client, it, leak in rows:
        if leak:
            continue
        date = it.get("true_as_of", "unknown")
        out.append({
            "type": "client-learning", "scope": client,
            "text": f"[as of: {date}] {it.get('learning','').strip()}",
            "true_as_of": date, "confidence": it.get("confidence", "?"),
        })
    return out


def main():
    ap = argparse.ArgumentParser(description="cheap-Dreaming client-learning miner")
    ap.add_argument("--dir")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--model", default="claude-opus-4-8")
    args = ap.parse_args()
    tdir = Path(args.dir) if args.dir else tl.transcript_dir()
    rows, tin, tout = mine(tdir, args.days, args.model)
    leaks = [r for r in rows if r[2]]
    print(f"=== dream_extractor | {len(rows)} candidates | leaks: {len(leaks)} | "
          f"tokens in={tin} out={tout} ===")
    by = {}
    for c, it, leak in rows:
        by.setdefault(c, []).append((it, leak))
    for c, items in by.items():
        print(f"\n### {c} ({len(items)})")
        for it, leak in items:
            mark = f"  LEAK->{leak}" if leak else ""
            print(f"  - [{it.get('confidence','?')} | as of: {it.get('true_as_of','?')}] {it.get('learning','').strip()}{mark}")


if __name__ == "__main__":
    main()
