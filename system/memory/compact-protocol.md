# Compact Protocol

_What to save, where, and how before `/compact` or "compact"._
_The context-injector.py hook detects the trigger and injects these instructions
before Claude processes the compact request._

---

## Save protocol - in order

### 1. Identify the client

If there was an active client this session: identify it and save into its folder.
If there were multiple clients: save into each.
If it was an internal session (your own agency): save into your agency's own folder.

---

### 2. `clients/[client]/wiki/log.md` - ALWAYS

Append to the current `## YYYY-MM-DD` section (create it if missing).

**Tags:**

| Tag | When to use |
|---|---|
| `[DECISION]` | The client or your team decided something |
| `[RESULT]` | Performance data, metric, comparison |
| `[PROBLEM]` | Identified problem, error, blocker |
| `[MEETING]` | Meeting summary, participants, topics |
| `[CLIENT]` | Client-specific context, preference |

**Example:**
```
## 2026-05-27
[DECISION] Target raised - approved by client
[PROBLEM] Tracking discrepancy: 12% gap between sources
[RESULT] CPA: 1820 (target: 2000) - good week
```

---

### 3. `clients/[client]/wiki/hot.md` - IF focus changed

Only update if:
- Something new started or stopped
- A new blocker or problem was identified
- Priority changed
- The next step became clear

If nothing changed: skip it.

---

### 4. `clients/[client]/memory/learnings.md` - IF there was a durable learning

Only append if a pattern emerged that **matters in future sessions**:
- Client-specific preference
- Industry/seasonal specificity
- A recurring behavioral pattern

If not: skip it.

---

### 5. `system/memory/cross-client-patterns.md` - ONLY if cross-client pattern

Only write here if something applies across several clients (a tactic, a pitfall,
an industry pattern). This file is normally regenerated weekly by `consolidate.py`,
so manual edits here are rare.

---

## Quick decision tree

```
Had a client? -> log.md (always) + memory/learnings.md (if learning)
  Focus changed?          -> hot.md
  Durable learning?       -> learnings.md
  Cross-client pattern?   -> cross-client-patterns.md
Ambiguous which client?   -> system/memory/inbox.md (quarantine) + flag
```

---

## THEN run the compact.
