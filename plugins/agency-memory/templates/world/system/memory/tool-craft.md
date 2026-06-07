# Tool-craft rules (approved)

The agent's tool-usage lessons, approved from the candidate pipeline. The enforceable rules
are read by the PreToolUse guard (tool_craft_guard.py); they start in WARN mode (warn, never
block). Advisory rules are delivered as context. A WARN rule is only promoted to DENY (a hard
block) with a separate, explicit human approval.

_Empty by default. The weekly consolidation proposes `tool-craft` candidates into
`tool-craft-candidates.md`; when you accept one, add it here (enforceable -> table, advisory
-> list)._

---

## Enforceable (WARN mode)

| #id | tool | match | mode | message |
|---|---|---|---|---|

<!--
Match DSL: `<input_field> <op> <pattern>`
  =~    regex search on str(input[field])      e.g. command =~ (?:^|[;&|])\s*pip\s
  has   pattern in input[field] (list or substring)   e.g. fields has actions
  notin str(input[field]) NOT in the comma-list       e.g. subagent_type notin claude,Explore,Plan
Example row:
| #1 | `Bash` | `command =~ (?:^|[;&|])\s*pip\s` | WARN | Use pip3 instead of pip. |
NB: the guard matches the raw command string; it cannot tell a pattern quoted inside a string
from a real invocation. WARN absorbs that; that is why new rules start as WARN, not DENY.
-->

## Advisory

_None yet._
