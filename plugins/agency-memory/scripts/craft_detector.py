#!/usr/bin/env python3
"""
craft_detector.py
Purpose: Mechanical (no-LLM, free) tool-craft detector. Reads recent session transcripts,
         flags tool moments (user-rejections + hard errors + content errors), pairs each
         with the tool_use that caused it (so we know WHAT was rejected/failed, not just the
         generic message), then CLUSTERS by a normalized signature and keeps only the
         high-signal subset:
           - ALL user-rejections that recur across >= min_sessions distinct sessions
           - RECURRING error clusters (>= min_sessions distinct sessions)
         The output is the LLM-judge input: a handful/week of real recurring issues instead
         of the raw ~hundreds/week of noise.
Options:
  python3 craft_detector.py                 # report over the last 7 days (world's transcripts)
  python3 craft_detector.py --days 24
  python3 craft_detector.py --min-sessions 2
Notes:
  - Pairs tool_result -> preceding tool_use via tool_use_id (fallback: last use).
  - For a REJECTION, also captures the NEXT tool_use (the correction = what the agent did
    instead) - that carries the lesson (e.g. WebFetch rejected -> firecrawl). The correction
    goes into the sample (judge context), NOT the signature (that fragments small clusters).
  - Clustering = exact match on a normalized signature (paths/numbers/quotes/ids masked).
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import transcript_lib as tl

REJECT_MARKERS = tl.REJECT_MARKERS
ERROR_MARKERS = tl.ERROR_MARKERS

# Transient harness self-corrections - the agent fixes these next turn, not craft lessons.
STRUCTURAL_DENY = (
    "has not been read yet", "file does not exist", "no such file or directory",
    "eisdir", "is a directory",
)
# Rejecting these is control-flow (plan/todo approval), not a tool-choice mistake.
CONTROL_FLOW_TOOLS = {"ExitPlanMode", "TodoWrite", "AskUserQuestion"}
# Tools whose result IS returned content (a buried "error" word = false positive, not a failure).
CONTENT_TOOLS = {"Read", "Glob", "Grep"}

_BARE_EXIT = re.compile(r"^exit code \d+\s*$")


def _input_summary(inp):
    if not isinstance(inp, dict):
        return str(inp)[:80]
    for k in ("command", "file_path", "url", "path", "pattern", "query"):
        if k in inp and isinstance(inp[k], str):
            return inp[k][:80]
    for v in inp.values():
        if isinstance(v, str):
            return v[:80]
    return ""


def _result_text(block):
    c = block.get("content", "")
    if isinstance(c, list):
        return " ".join(x.get("text", "") for x in c if isinstance(x, dict))
    return str(c)


def _classify(text, is_error, tool):
    low = text.lower().strip()
    if any(m in low for m in REJECT_MARKERS):
        return None if tool in CONTROL_FLOW_TOOLS else "rejection"
    if any(d in low for d in STRUCTURAL_DENY) or _BARE_EXIT.match(low):
        return None
    if is_error:
        return "hard_error"
    if tool in CONTENT_TOOLS:
        return None
    head = low[:80]
    structured = ("<tool_use_error>" in low or '"code"' in low
                  or low.startswith("error") or "exceeds maximum allowed tokens" in low
                  or any(m in head for m in ERROR_MARKERS))
    return "content_error" if structured else None


def walk_moments(path):
    """Flagged moments {kind, tool, input, snippet, correction} for one session. Each flagged
    tool_result is paired with the tool_use that produced it; rejections also get the next
    tool_use (the correction)."""
    events = []
    pending = {}
    last_use = ("?", "")
    for line in open(path, encoding="utf-8"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        att = o.get("attributionMcpTool") or o.get("attributionSkill") or o.get("attributionMcpServer")
        msg = o.get("message", o)
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                name = att or b.get("name", "?")
                summ = _input_summary(b.get("input"))
                pending[b.get("id")] = (name, summ)
                last_use = (name, summ)
                events.append(("use", name, summ))
            elif b.get("type") == "tool_result":
                txt = _result_text(b)
                tool, summ = pending.get(b.get("tool_use_id"), last_use)
                kind = _classify(txt, b.get("is_error", False), tool)
                if kind:
                    events.append(("res", kind, tool, summ, txt[:300]))

    out = []
    for i, e in enumerate(events):
        if e[0] != "res":
            continue
        _, kind, tool, summ, snip = e
        correction = None
        if kind == "rejection":
            for j in range(i + 1, min(i + 6, len(events))):
                if events[j][0] == "use":
                    correction = (events[j][1], events[j][2])
                    break
        out.append({"kind": kind, "tool": tool, "input": summ, "snippet": snip, "correction": correction})
    return out


def signature(moment):
    if moment["kind"] == "rejection":
        return f"rejection :: {moment['tool']}"
    s = moment["snippet"].lower()
    s = re.sub(r"/[^\s\"']+", "<path>", s)
    s = re.sub(r"\b[0-9a-f]{6,}\b", "<id>", s)
    s = re.sub(r"\d+", "<n>", s)
    s = re.sub(r"\"[^\"]*\"", "<q>", s)
    s = re.sub(r"'[^']*'", "<q>", s)
    s = re.sub(r"\s+", " ", s).strip()
    return f"{moment['kind']} :: {moment['tool']} :: {s[:140]}"


def collect(tdir, days):
    import time
    import os
    now = time.time()
    cutoff = now - days * 86400
    files = [f for f in tl.session_files(tdir) if os.path.getmtime(f) >= cutoff]
    clusters = defaultdict(lambda: {"kind": None, "tool": None, "count": 0,
                                    "sessions": set(), "samples": []})
    n_moments = 0
    for f in files:
        sid = Path(f).stem
        for m in walk_moments(f):
            n_moments += 1
            sig = signature(m)
            c = clusters[sig]
            c["kind"] = m["kind"]
            c["tool"] = m["tool"]
            c["count"] += 1
            c["sessions"].add(sid)
            if len(c["samples"]) < 2:
                c["samples"].append((m["input"], m["snippet"][:160], m.get("correction")))
    span = max((now - min((os.path.getmtime(f) for f in files), default=now)) / 86400, 1) if files else 1
    return clusters, len(files), n_moments, span


def filter_for_review(clusters, min_sessions=2):
    """Recurrence across DISTINCT sessions is the signal (a one-off, even repeated within a
    single session, is not a durable lesson). Applies to rejections too."""
    keep = []
    for sig, c in clusters.items():
        spread = len(c["sessions"])
        if spread >= min_sessions:
            keep.append((sig, c, spread))
    keep.sort(key=lambda x: (x[1]["kind"] != "rejection", -x[2], -x[1]["count"]))
    return keep


def _report(tdir, days, min_sessions):
    clusters, n_sess, n_mom, span = collect(tdir, days)
    keep = filter_for_review(clusters, min_sessions)
    rej = [k for k in keep if k[1]["kind"] == "rejection"]
    rec = [k for k in keep if k[1]["kind"] != "rejection"]
    pw = lambda n: n / span * 7
    print(f"=== craft_detector | {tdir} ===")
    print(f"sessions: {n_sess} | span: {span:.0f} days | raw moments: {n_mom} (~{pw(n_mom):.0f}/week)")
    print(f"-> clusters: {len(clusters)} | KEPT: {len(keep)} (~{pw(len(keep)):.0f}/week) [noise cut: {n_mom}->{len(keep)}]")
    print(f"\n--- REJECTIONS ({len(rej)}) ---")
    for sig, c, spread in rej:
        print(f"  [{c['count']}x / {spread} sess] {c['tool']}  e.g. {c['samples'][0][0]!r}" if c['samples'] else f"  {c['tool']}")
    print(f"\n--- RECURRING ERROR CLUSTERS (>= {min_sessions} sessions) ---")
    for sig, c, spread in rec[:20]:
        print(f"  [{c['count']}x / {spread} sess] {c['kind']} :: {c['tool']}")
        if c["samples"]:
            print(f"      e.g. {c['samples'][0][1]!r}")


def main():
    ap = argparse.ArgumentParser(description="Mechanical tool-craft detector")
    ap.add_argument("--dir")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--min-sessions", type=int, default=2)
    args = ap.parse_args()
    tdir = Path(args.dir) if args.dir else tl.transcript_dir()
    _report(tdir, args.days, args.min_sessions)


if __name__ == "__main__":
    main()
