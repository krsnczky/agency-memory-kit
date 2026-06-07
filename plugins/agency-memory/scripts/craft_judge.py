#!/usr/bin/env python3
"""
craft_judge.py
Purpose: Takes the mechanically-filtered recurring clusters from craft_detector and runs ONE
         batched LLM pass that decides, per cluster: is this a durable tool-craft lesson? If
         yes, state it as a rule, classify advisory vs enforceable (can it be a deterministic
         PreToolUse gate?), and give the scope (tool + condition). Output: tool-craft candidates
         in the shared {type, scope, text} shape for the candidate state machine.
         DRY-RUN prints candidates; candidates() returns them for the consolidation cadence.
Options:
  python3 craft_judge.py                # judge last 24 days, print candidates
  python3 craft_judge.py --model claude-sonnet-4-6
Requires: anthropic + ANTHROPIC_API_KEY.
Notes:
  - One batched call over all kept clusters (cheaper + lets the model dedup/compare).
  - Hard discrimination task (durable lesson vs transient noise) + the cost of a bad craft
    rule is high (cross-client behavior). Volume is a few/week, so model choice is about
    judgment quality, not price.
"""

import argparse
import json
import re
from pathlib import Path

import anthropic
import craft_detector as cd
import transcript_lib as tl

SYSTEM = ("You are the tool-craft analyzer of an agency's AI system (Claude Code running a "
          "marketing/ops agency: clients, ads platforms, CRM/Notion, scraping, file ops). You "
          "receive RECURRING tool failures and user-rejections that a mechanical detector "
          "already clustered (each appears across multiple sessions). Decide which ones are "
          "DURABLE TOOL-CRAFT LESSONS the agent should learn, vs transient noise.")

PROMPT = """For each cluster below, decide if it is a durable tool-craft lesson.

A LESSON is: a repeatable way the agent uses a tool wrong that has a concrete, statable fix
(e.g. "use pip3 not pip", "this API needs property X", "scrape client sites with the scraper
tool not a generic fetch", "read large files with offset/limit"). NOT a lesson: a one-off path
typo, a transient 404, a dead URL, "no matches found", a generic exit code.

For a REJECTION cluster, the "correction" line shows the tool the agent used INSTEAD after the
user rejected the original tool. Use it to state the right tool/approach (rejected tool ->
correction tool is the lesson).

For each REAL lesson output an object:
  - "tool": the tool the rule is about
  - "rule": the craft rule in ONE imperative sentence (the fix, not the symptom)
  - "enforceable": true ONLY if it can be a deterministic pre-tool-call gate
      (a checkable condition on the tool + its input). false if it needs judgment.
  - "scope": if enforceable, the condition ("when <X>"); else "advisory"
  - "evidence": "<count>x / <sessions> sessions"

Skip clusters that are NOT lessons (do not output them). Output ONLY a JSON array, nothing else.

CLUSTERS:
{clusters}
"""


def build_clusters_block(keep):
    lines = []
    for i, (sig, c, spread) in enumerate(keep, 1):
        s = c["samples"][0] if c["samples"] else ("", "", None)
        inp, snip = s[0], s[1]
        corr = s[2] if len(s) > 2 else None
        block = (f'{i}. kind={c["kind"]} tool={c["tool"]} count={c["count"]} sessions={spread}\n'
                 f'   sample_input: {inp!r}\n'
                 f'   sample_result: {snip!r}')
        if corr:
            block += f'\n   correction (what the agent did INSTEAD): tool={corr[0]} input={corr[1]!r}'
        lines.append(block)
    return "\n".join(lines)


def parse_json_array(text):
    m = re.search(r"\[.*\]", text.strip(), re.DOTALL)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except Exception:
        return []


def judge(tdir, days=24, min_sessions=2, model="claude-opus-4-8"):
    clusters, _, _, _ = cd.collect(tdir, days)
    keep = cd.filter_for_review(clusters, min_sessions)
    if not keep:
        return [], None
    resp = anthropic.Anthropic().messages.create(
        model=model, max_tokens=2000, system=SYSTEM,
        messages=[{"role": "user", "content": PROMPT.format(clusters=build_clusters_block(keep))}],
    )
    return parse_json_array(resp.content[0].text), resp.usage


def candidates(tdir, days=24, min_sessions=2, model="claude-opus-4-8"):
    """Tool-craft candidates in the {type, scope, text} shape. Tool-craft is SYSTEM-level
    (client-agnostic). The [GATE]/[ADVISORY] tag is embedded in text so the enforcement guard
    and the existing sync/review files work unchanged."""
    lessons, _ = judge(tdir, days, min_sessions, model)
    out = []
    for l in lessons:
        enf = bool(l.get("enforceable"))
        tag = f"[GATE: {l.get('scope','')}]" if enf else "[ADVISORY]"
        out.append({
            "type": "tool-craft", "scope": "system",
            "text": f"{tag} {l.get('tool','?')}: {l.get('rule','').strip()}",
            "enforceable": enf, "gate_scope": l.get("scope") if enf else None,
        })
    return out


def main():
    ap = argparse.ArgumentParser(description="Tool-craft LLM judge")
    ap.add_argument("--dir")
    ap.add_argument("--days", type=int, default=24)
    ap.add_argument("--min-sessions", type=int, default=2)
    ap.add_argument("--model", default="claude-opus-4-8")
    args = ap.parse_args()
    tdir = Path(args.dir) if args.dir else tl.transcript_dir()
    cands = candidates(tdir, args.days, args.min_sessions, args.model)
    print(f"=== craft_judge ({args.model}) | {len(cands)} tool-craft candidate ===")
    for c in cands:
        print(f"  {c['text']}")


if __name__ == "__main__":
    main()
