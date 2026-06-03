# Memory Policy

_System-level operational rule. The AI follows it during a session._

---

## Core principle: the client folder is the source of truth

There is **no global vault**. Every piece of client information lives in that client's
own folder and nowhere else. This is the no-mixing guarantee: client data can never
leak across clients, because there is no shared pile to leak through.

---

## The 4 memory types

| Type | Storage | Example | Lifetime |
|---|---|---|---|
| Structural fact | `wiki/*.md` | account ID, budget, ICP, brand rules | Until it changes - then update |
| Current focus | `wiki/hot.md` | open TODO, active situation, blocker | Weekly review - closed items out |
| Operational learning | `memory/learnings.md` | what worked, what didn't, recurring pattern | Max ~7 per section, then archive |
| Session-specific | session log (ephemeral) | intermediate reasoning, scratch calc | Lost at session end - intentional |

---

## Decision rules - what goes where

**Question: "Where do I write this?"**

- If a fact will still be true in the future -> `wiki/*.md`
- If it matters now but maybe not next week -> `wiki/hot.md`
- If it is a pattern that other sessions can use -> `memory/learnings.md`
- If it is only relevant in this session -> write it nowhere, let it be lost (that is fine)
- If it is a cross-client pattern (applies to several clients) -> `system/memory/cross-client-patterns.md`

**Duplication rule:** the same info lives in at most 2 places. If it is in `hot.md` and a `wiki` page, fine. If it is in `hot.md`, `learnings.md` AND a `wiki` page - that is noise.

---

## Routing rule (safety + clarity)

- Client info can ONLY go into the correct client's folder. Clients are never mixed.
- If it is **not clear which client** (multiple clients in one session, or ambiguous):
  do NOT guess. Put the learning in `system/memory/inbox.md` (quarantine) and flag the
  user to file it. Better nowhere than in the wrong client.

---

## Hygiene routine

### Weekly
- Review `wiki/hot.md`: delete closed TODOs or move them to `log.md`
- Remove stale focus points (>2 weeks unchanged)

### Monthly
- Archive `wiki/log.md` -> `wiki/log-YYYY-MM.md`
- Review `memory/learnings.md` sections: if a section has >7 entries, move the oldest to `memory/learnings-archive-YYYY.md`
  (the weekly `consolidate.py` run handles this automatically)

---

## What goes nowhere

- Temporary calculations, intermediate decisions that are not final
- Info the user already knows (no need to write it back)
- Errors and retries - only the end result matters
- "I'm trying this now" statuses
