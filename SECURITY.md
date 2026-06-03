# Security Policy

This is an open-beta plugin (see the README). Read this before you point it at real
client data. The model is deliberately simple and stated honestly below, including its
one external call and its limits.

## What the plugin touches

The agency-memory plugin operates on **local files only**:

- your **world** folder (`clients/`, `system/memory/`, `system/logs/`)
- the Claude Code project auto-memory directory (`~/.claude/projects/<slug>/memory`),
  read-only, only when you configure memory guards

The plugin itself sends **no telemetry** and stores nothing outside your machine.

## The one external call (be aware of it)

`consolidate.py` (the optional, weekly hygiene run) sends your accumulated
`learnings.md` and `CHANGELOG.md` content to the **Anthropic API** to dedup and
summarize. This is the only network call in the kit, and it happens only when you run
that script. It needs your `ANTHROPIC_API_KEY`. If your learnings contain sensitive
client detail, that detail is sent to the API on that run. Day-to-day use (the hooks)
makes no external call.

## What the design guarantees

Not by trusting the agent to behave, but by structure:

| Guarantee | How |
| --- | --- |
| No global vault, no cross-client leak | There is no shared pile. Memory lives in per-client folders; nothing merges them. |
| Loading is deterministic | A hook injects a fixed load order, not a fuzzy similarity search that could pull the wrong client's data. |
| No guessed attribution | When it is unclear which client a learning belongs to, it goes to a quarantine inbox for you to file. It is never written into a client folder on a guess. |
| The weekly run is lossless | Dedup/merge only. No entry is evicted automatically; protected sections re-inject any dropped unique entry. |
| Nothing is archived or promoted automatically | Superseded/stale entries and promotion candidates are only surfaced for review. They change a file only after you accept them by id. |
| Hand-curated files are never overwritten by automation | The pipeline writes to operational `learnings.md` and to generated review files, never to your `CLAUDE.md`. |

There are four hooks (SessionStart, UserPromptSubmit, Stop, PreToolUse). They inject
context and surface constraints; they do not exfiltrate or delete anything.

## Data handling

- **Secrets:** keep `ANTHROPIC_API_KEY` in `~/.anthropic.env` (chmod 600), never in the
  repo. `.gitignore` already excludes backups and Python caches.
- **Sensitivity:** your world holds client data. Keep the world repository **private**.
- **Cloud trade-off:** the GitHub Actions runner template checks out your world (client
  data) onto a GitHub runner. It is opt-in. Prefer the local launchd runner for
  sensitive data, and never make the cloud path your only path.

## Reporting a vulnerability

Please report privately, not in a public issue. Use this repository's **GitHub Security
Advisories** ("Report a vulnerability"), or open a minimal private issue asking for a
secure channel. Since this is an open beta maintained as a side project, expect a
best-effort response, not an SLA.

## Scope

Covered: the plugin engine (hooks, scripts, config schema) in this repository. Not
covered: your own world content, the Anthropic API and its data handling, Claude Code
itself, and any third-party runner (cron, launchd, GitHub Actions) you choose to wire up.

## Philosophy

Your context is yours. The client folder is the single source of truth, there is no
global vault to leak through, and no automated step rewrites or deletes what you did not
approve. The kit's job is to keep that boundary clean, not to ask you to trust it blindly.
