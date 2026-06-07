#!/usr/bin/env python3
"""
tool_craft_guard.py
Purpose: PreToolUse enforcement guard. Reads the APPROVED enforceable rules from the world's
         system/memory/tool-craft.md (the enforceable WARN section), evaluates the about-to-run
         tool call against each rule's machine match, and in WARN MODE surfaces a warning
         (via the hookSpecificOutput.additionalContext JSON) + increments a per-rule violation
         counter. It NEVER blocks (WARN-only). The violation counter is the escalation signal
         (a WARN rule that keeps getting hit -> propose DENY, which requires a separate human
         approval; DENY is not implemented here).
Modes:
  python3 tool_craft_guard.py --selftest      # mock tool calls
  echo '<json>' | python3 tool_craft_guard.py # PreToolUse hook mode (reads {tool_name,tool_input})
Wiring: PreToolUse hook (hooks.json). World root resolved from AGENCY_WORLD_ROOT /
        CLAUDE_PROJECT_DIR (Claude Code sets the latter for hook processes).
Match DSL (in tool-craft.md): `<input_field> <op> <pattern>`
  =~    regex search on str(input[field])
  has   pattern in input[field] (list membership or substring)
  notin str(input[field]) NOT in the comma-list pattern
Note: matches the raw command string; it cannot distinguish a pattern quoted inside a string
      from a real invocation. WARN absorbs that; DENY would need care.
"""

import json
import os
import re
import sys
from pathlib import Path


def world_root():
    return (os.environ.get("AGENCY_WORLD_ROOT")
            or os.environ.get("CLAUDE_PROJECT_DIR")
            or os.getcwd())


def rules_path():
    return Path(world_root()) / "system" / "memory" / "tool-craft.md"


def violations_path():
    return Path(world_root()) / "system" / "memory" / "tool-craft-violations.json"


_ROW = re.compile(r"^\|\s*#(\d+)\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|\s*WARN\s*\|\s*(.+?)\s*\|\s*$")


def load_rules(path=None):
    """Parse the enforceable WARN table. Returns [{id, tool, field, op, pattern, msg}]."""
    path = path or rules_path()
    rules = []
    if not path.exists():
        return rules
    in_enf = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_enf = "Enforceable" in line
            continue
        if not in_enf:
            continue
        m = _ROW.match(line)
        if not m:
            continue
        rid, tool, match, msg = m.groups()
        parts = match.strip().split(None, 2)
        if len(parts) != 3:
            continue
        field, op, pattern = parts
        rules.append({"id": int(rid), "tool": tool, "field": field,
                      "op": op, "pattern": pattern, "msg": msg})
    return rules


def _matches(rule, tool_input):
    val = tool_input.get(rule["field"])
    if val is None:
        return False
    op, pat = rule["op"], rule["pattern"]
    if op == "=~":
        return re.search(pat, str(val)) is not None
    if op == "has":
        if isinstance(val, (list, tuple, set)):
            return pat in val
        return pat in str(val)
    if op == "notin":
        return str(val) not in [x.strip() for x in pat.split(",")]
    return False


def check(tool_name, tool_input, rules=None):
    rules = rules if rules is not None else load_rules()
    return [r for r in rules if r["tool"] == tool_name and _matches(r, tool_input)]


def _bump_violations(hits):
    path = violations_path()
    counts = {}
    if path.exists():
        try:
            counts = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            counts = {}
    for r in hits:
        counts[str(r["id"])] = counts.get(str(r["id"]), 0) + 1
    try:
        path.write_text(json.dumps(counts, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return counts


def _selftest():
    rules = load_rules()
    print(f"=== tool_craft_guard self-test | {len(rules)} enforceable WARN rules from {rules_path()} ===")
    for r in rules:
        print(f"  #{r['id']} {r['tool']}: {r['field']} {r['op']} {r['pattern']!r}")
    cases = [
        ("Bash", {"command": "pip install requests"}, "pip example"),
        ("Bash", {"command": "echo hello"}, "benign Bash"),
    ]
    for tool, inp, label in cases:
        hits = check(tool, inp, rules)
        print(f"  {label}: warn={len(hits) > 0}" + (f" -> {hits[0]['msg']}" if hits else ""))


def _hook_mode():
    """PreToolUse hook entry. WARN-only: ALLOW + inject warning via additionalContext.
    NB: exit-0 stderr is NOT surfaced to the model - the warning MUST go through the JSON."""
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        sys.exit(0)
    hits = check(data.get("tool_name", ""), data.get("tool_input", {}) or {})
    if hits:
        _bump_violations(hits)
        msg = " | ".join(f"tool-craft #{r['id']}: {r['msg']}" for r in hits)
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "additionalContext": msg,
            }
        }))
    sys.exit(0)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        _hook_mode()
