# Context Load Order

_Mandatory load order per task type. Injected before every prompt by the UserPromptSubmit hook._
_If a required file does not exist for a client: flag it, do not silently skip._
_Edit the task table below to match your agency's work. The rows are examples._

---

## Base load (before every task)

1. `clients/[client]/.claude/CLAUDE.md` - pointer file
2. `clients/[client]/wiki/index.md` - navigation, IDs, budget
3. `clients/[client]/wiki/hot.md` - current state, open TODOs
4. `clients/[client]/memory/learnings.md` - operational learnings (full load = primary client memory)
5. **Candidate surfacing (point-of-use, optional):** only relevant once the weekly consolidation has run (it ships with the agency-memory plugin and writes `candidates-state.json`). If there are open candidates for THIS client (client-learning, wiki-promotion or sweep), surface them for review (id + text) - **for this client only**, never mix in another's. Accept/reject by `#id`: on accept you apply it (client-learning -> the right section of `memory/learnings.md`; wiki-promotion fact -> `campaigns-[area].md`; sweep -> archive) and set the status in `candidates-state.json` to `accepted`/`rejected`. (The plugin ships `client_candidates.py` to print one client's open candidates; until you have wired the weekly run, skip this step.)

---

## Task-specific additions (examples - customize these)

| Task type | Trigger words | Required load on top of base |
|---|---|---|
| Strategy / advisory | should we, how do we position, risk, which direction | `wiki/profil.md` + `system/memory/cross-client-patterns.md` |
| Creative / copy | ad copy, headline, asset, copy, creative | `wiki/brand.md` |
| Competitor research | competitor, market, gap analysis | `wiki/competitors/index.md` |
| Reporting | weekly report, how is the campaign doing | `wiki/campaigns.md` + `wiki/change-log.md` |

---

## Flag rule

If the task-specific required file does **not exist** for the client:
- Do not silently skip it
- Flag: "[filename] not found for this client - continue with base context?"

If the **client cannot be identified**:
- Do not load anything
- Ask: "Which client is this about?"
