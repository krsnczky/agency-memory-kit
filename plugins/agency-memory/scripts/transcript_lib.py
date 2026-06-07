#!/usr/bin/env python3
"""
transcript_lib.py
Purpose: Shared, stdlib-only substrate for reading Claude Code session transcripts
         (the .jsonl files under ~/.claude/projects/<slug>/). Two downstream consumers:
           - cheap-Dreaming (dream_extractor): mines RAW transcripts of cleanly single-client
             sessions for durable client learnings (text-only, MEDIUM client gate).
           - tool-craft (craft_detector/craft_judge): mines tool errors / user-rejections /
             retries for craft lessons.
         This module ONLY reads + classifies (no LLM, no writes). Mechanical = free.
Options:
  python3 transcript_lib.py                 # self-test over the resolved world's transcripts
  python3 transcript_lib.py --dir <path>    # point at a specific transcript dir
  python3 transcript_lib.py --days 7        # window for the per-week extrapolation
Notes:
  - No third-party deps. Pure stdlib so it can run in any hook/cron.
  - Token estimate is chars/3.7 (a rough sizing figure, not a billing number).
  - The transcript dir is derived from a project root by the Claude Code slug rule
    (every non [A-Za-z0-9_-] char -> '-'), the same rule memory-guard uses.
"""

import argparse
import json
import os
import re
import time
from pathlib import Path

try:
    from agency_common import resolve_world_root
except Exception:  # standalone fallback
    def resolve_world_root(explicit=None):
        return explicit or os.environ.get("AGENCY_WORLD_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

CLIENT_RE = re.compile(r"clients/([a-z0-9\-]+)/")
TEMPLATE_DIRS = {"_new-client-template", "_template"}

REJECT_MARKERS = ("doesn't want to proceed", "user doesn't want", "tool use was rejected")
ERROR_MARKERS = ("error", "failed", "not found", "exception", "traceback",
                 "timed out", "invalid", "cannot ", "permission denied")

TOKEN_CHARS = 3.7


# --- locating transcripts --------------------------------------------------

def project_slug(project_root):
    """Claude Code derives the transcript dir name by replacing every char that is not
    [A-Za-z0-9_-] with '-' in the absolute project path."""
    return re.sub(r"[^A-Za-z0-9_-]", "-", str(Path(project_root).resolve()))


def transcript_dir(project_root=None):
    """Resolve ~/.claude/projects/<slug>/ for a project root (default: resolved world root)."""
    root = project_root or resolve_world_root()
    return Path.home() / ".claude" / "projects" / project_slug(root)


def session_files(tdir):
    tdir = Path(tdir)
    return sorted(tdir.glob("*.jsonl")) if tdir.is_dir() else []


# --- per-session scan (one pass, all signals) ------------------------------

def _result_text(block):
    c = block.get("content", "")
    if isinstance(c, list):
        return " ".join(x.get("text", "") for x in c if isinstance(x, dict))
    return str(c)


def scan_session(path):
    """One pass over a session file. Returns a dict of all mechanical signals."""
    clients = {}
    text_bytes = 0
    tool_use = {}
    sys_refs = 0
    dev_kw = 0
    first_ts = last_ts = None
    moments = []

    def _bump(d, k):
        d[k] = d.get(k, 0) + 1

    for line in open(path, encoding="utf-8"):
        for m in CLIENT_RE.finditer(line):
            c = m.group(1)
            if c not in TEMPLATE_DIRS:
                _bump(clients, c)
        sys_refs += line.count("system/")
        for kw in ("consolidate.py", "CHANGELOG", "hooks/", "agency-memory",
                   "memory-consolidation"):
            dev_kw += line.count(kw)

        try:
            o = json.loads(line)
        except Exception:
            continue

        ts = o.get("timestamp")
        if ts:
            if first_ts is None:
                first_ts = ts
            last_ts = ts

        att = o.get("attributionMcpTool") or o.get("attributionSkill") or o.get("attributionMcpServer")
        msg = o.get("message", o)
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, list):
            if isinstance(content, str):
                text_bytes += len(content)
            continue

        for b in content:
            if not isinstance(b, dict):
                continue
            t = b.get("type")
            if t == "text":
                text_bytes += len(b.get("text", ""))
            elif t == "tool_use":
                _bump(tool_use, b.get("name", "?"))
            elif t == "tool_result":
                tool = att or "builtin"
                txt = _result_text(b)
                low = txt.lower()
                if any(m in low for m in REJECT_MARKERS):
                    moments.append(("rejection", tool, txt[:300]))
                elif b.get("is_error"):
                    moments.append(("hard_error", tool, txt[:300]))
                elif len(txt) > 20 and any(m in low for m in ERROR_MARKERS):
                    moments.append(("content_error", tool, txt[:300]))

    return {
        "path": str(path),
        "clients": clients,
        "text_bytes": text_bytes,
        "tool_use": tool_use,
        "sys_refs": sys_refs,
        "dev_kw": dev_kw,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "moments": moments,
        "mtime": os.path.getmtime(path),
    }


# --- client gate (no-mixing) -----------------------------------------------

def classify_client(clients, gate="medium"):
    """Decide whether a session is safely attributable to ONE client.
    Returns (main_client, share, eligible). Gates:
      strict : exactly one client present
      medium : dominant >=90% of refs AND every other client < 5 refs   (recommended)
      loose  : dominant >=80% AND every other client < 10 refs
    A session that fails the gate must NOT be mined for client learnings (no-mixing)."""
    if not clients:
        return (None, 0.0, False)
    total = sum(clients.values())
    main = max(clients, key=clients.get)
    top = clients[main]
    share = top / total
    others = [n for c, n in clients.items() if c != main]
    max_other = max(others) if others else 0

    if gate == "strict":
        eligible = len([c for c in clients if clients[c] >= 1]) == 1
    elif gate == "loose":
        eligible = share >= 0.80 and max_other < 10
    else:
        eligible = share >= 0.90 and max_other < 5
    return (main, share, eligible)


# --- text extraction (strip tool noise) ------------------------------------

def extract_text(path):
    """User/assistant text turns only, tool_result/tool_use stripped. The cheap-Dreaming
    input (the signal, not the scraped-page/file-dump noise)."""
    out = []
    for line in open(path, encoding="utf-8"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        msg = o.get("message", o)
        c = msg.get("content") if isinstance(msg, dict) else None
        if isinstance(c, str):
            out.append(c)
        elif isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "text":
                    out.append(b.get("text", ""))
    return "\n".join(out)


def est_tokens(n_chars):
    return int(n_chars / TOKEN_CHARS)


# --- self-test -------------------------------------------------------------

def _selftest(tdir, days):
    files = session_files(tdir)
    if not files:
        print(f"No transcripts at: {tdir}")
        return
    now = time.time()
    scans = [scan_session(f) for f in files]
    span_days = max((now - min(s["mtime"] for s in scans)) / 86400, 1)
    raw_bytes = sum(os.path.getsize(s["path"]) for s in scans)
    text_bytes = sum(s["text_bytes"] for s in scans)
    medium = [s for s in scans if classify_client(s["clients"], "medium")[2]]
    medium_text = sum(s["text_bytes"] for s in medium)
    moments = sum(len(s["moments"]) for s in scans)

    print(f"=== transcript_lib self-test | {tdir} ===")
    print(f"sessions: {len(files)} | span: {span_days:.0f} days")
    print(f"[text ratio] raw={raw_bytes:,}b text={text_bytes:,}b ({100*text_bytes/max(raw_bytes,1):.1f}%)")
    print(f"[MEDIUM gate] {len(medium)} cleanly single-client (~{len(medium)/span_days*7:.1f}/week)"
          f" ~{int(medium_text/3.7/span_days*7):,} tok/week")
    print(f"[tool moments] {moments} total (~{moments/span_days*7:.0f}/week)")


def main():
    ap = argparse.ArgumentParser(description="Shared transcript substrate")
    ap.add_argument("--dir")
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()
    tdir = Path(args.dir) if args.dir else transcript_dir()
    _selftest(tdir, args.days)


if __name__ == "__main__":
    main()
