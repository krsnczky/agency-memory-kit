# Agency memory (coordinator)

This world gives Claude Code a deterministic, folder-based memory for an agency that
juggles multiple clients. **The client folder is the single source of truth. There is
no global vault.** Client data cannot leak across clients because there is no shared
pile to leak through.

> Rename and extend this file for your agency (add your departments, routing, house
> rules). The two sections below are the memory protocol - keep them.

---

## Client context - automatic load

Whenever a client is mentioned, follow this order FIRST (the UserPromptSubmit hook
injects the full table from `system/memory/context-load-order.md` at the start of
every prompt):

1. `clients/[client]/.claude/CLAUDE.md` - pointer file
2. `clients/[client]/wiki/index.md` + `clients/[client]/wiki/hot.md`
3. The task-specific page(s) per `system/memory/context-load-order.md`
4. `clients/[client]/memory/learnings.md` - operational memory (full load)

If a required file does not exist for a client: flag it, do not silently skip.
If the client cannot be identified: ask which client, load nothing.

---

## Memory - end of session (structured ingest)

Capture is **agent-driven** (the AI writes it, not a script guessing the client).
This is the no-mixing guarantee: during a session the AI knows which client it is
working on, so the info always lands in the right folder.

### Critical routing rule (safety + clarity)

- Client info can ONLY go into the correct client's folder. Clients are never mixed.
- If it is **not clear which client** (multiple clients in one session, or ambiguous):
  do NOT guess. Put the learning in `system/memory/inbox.md` (quarantine) and flag the
  user to file it. Better nowhere than in the wrong client.

### Session type (first step)

| Session type | Content | Primary log |
|---|---|---|
| **System/dev** | scripts, hooks, config changes, infra | `system/logs/CHANGELOG.md` + `system/memory/learnings.md` "Next session briefing" |
| **Client work** | campaign, decision, meeting, result, report | `clients/[client]/wiki/log.md` |

**Client work session** (only for the confidently identified client):
1. `clients/[client]/wiki/log.md` - append with tags [DECISION] [RESULT] [PROBLEM] [MEETING] [CLIENT]
2. `clients/[client]/wiki/hot.md` - update if focus or priority changed
3. `clients/[client]/memory/learnings.md` - append if there was a durable learning

**System/dev session:**
1. `system/logs/CHANGELOG.md` - append the change
2. `system/memory/learnings.md` "Next session briefing" - update if the next session needs to know something (the SessionStart hook injects this automatically)

Do this automatically at the end of every session. Do not ask whether to - just do it.

---

## Files in this world

- `system/memory/memory-policy.md` - what goes where, the memory types, hygiene
- `system/memory/context-load-order.md` - task-specific load order (customize this)
- `system/memory/compact-protocol.md` - what to save before /compact
- `system/memory/inbox.md` - quarantine for ambiguous learnings
- `system/memory/world.json` - (optional) localize section names / language; copy from `world.json.example`
- `system/memory/learnings.md` - system/dev cross-session memory (+ "Next session briefing")
- `clients/<client>/` - one folder per client (`.claude/CLAUDE.md`, `wiki/`, `memory/learnings.md`)

The weekly consolidation, the candidate review files, and `cross-client-patterns.md` are
produced by the **agency-memory plugin** (its `consolidate.py`, run via a plugin runner),
not by anything in this world. They appear under `system/memory/` after the first run.
