# Changelog

_System/dev changes. Append newest at top with a date and a tag:
[INFRA] [HOOK] [FIX] [DOC]._

---

## 2026-06-11

- [INFRA] **v0.2.2 - Linux scheduler support.** Added `agency-memory-consolidate.service.template`
  + `.timer.template` (systemd user timer) for the weekly run on Linux. `Persistent=true` is
  the launchd equivalent (catches a missed run after the machine was off); a plain-cron
  one-liner is in the timer header. README schedule section now lists macOS / Linux / cloud
  per OS. Note: the daily hooks already run on Linux (the one bash hook has a GNU `stat -c`
  fallback). Windows (pure-Python session-logger + python/python3 invocation + Task Scheduler)
  is the next cross-platform step.

## 2026-06-08

- [FIX] **v0.2.1.** `client_candidates.py` (point-of-use per-client surfacing) now includes the
  `client-learning` type in `CLIENT_TYPES` (was: only `wiki-promotion` + `sweep`). The
  `dream_extractor` v2 stream produces `client-learning` candidates, but they were never
  surfaced when loading a client - so the biggest new stream was invisible at point-of-use.
  Found during the live beta review. Added a CLIENT-LEARNING display block and updated the
  world scaffold `context-load-order.md` step 5 (accept path: client-learning -> the right
  section of `memory/learnings.md`).

## 2026-06-04

- [FIX] **v0.1.1.** `memory-guard` project-memory slug derivation now matches Claude Code's
  real scheme: every char outside `[A-Za-z0-9_-]` -> `-` (was: only `/`). Fixes worlds whose
  path contains a **space** (e.g. `.../Axon Digital`) - the derived dir mismatched Claude
  Code's actual `...-Axon-Digital`, so the guard read the wrong memory dir. Found in the Ádám
  beta. Verified against real slugs (incl. a `First project` -> `First-project` case). The
  explicit `memory_guard.project_memory_path` override remains as an escape hatch.
- [DOC] Same release rolls up the day's onboarding fixes: world scaffold `CLAUDE.md` +
  `CHANGELOG.md` stub, README install (desktop GUI first, both `/plugin` and CLI forms),
  MIT license. Version bumped 0.1.0 -> 0.1.1 so installs auto-update.

## 2026-06-03

- [INFRA] **Plugin conversion (full).** The kit is now a Claude Code plugin under
  `plugins/agency-memory/` with a `.claude-plugin/marketplace.json`. Engine/data split:
  scripts locate themselves via `${CLAUDE_PLUGIN_ROOT}` / `__file__`; user data (world)
  is resolved via `--world` / `AGENCY_WORLD_ROOT` -> `CLAUDE_PROJECT_DIR` -> cwd
  (`agency_common.py`).
- [INFRA] **Config layer (HU/EN).** Section names, protected/evergreen sets, curated
  prefix, and the memory-guard rules now come from `<world>/system/memory/world.json`,
  layered over the bundled English `world.default.json`. The engine hardcodes nothing.
  Verified: full + partial Hungarian override, with unset keys falling back to defaults.
- [HOOK] Hooks ported into the plugin (`hooks/hooks.json`, `${CLAUDE_PLUGIN_ROOT}`):
  `system-briefing.py` (was .sh; config-driven briefing heading), `context-injector.py`,
  `session-logger.sh`, and `memory-guard.py` (mechanism in the plugin; GUARDS list +
  project-memory path in the world config; no-op when no guards configured).
- [INFRA] **Runners** (templates, no auto-install): `run-weekly.sh` wrapper +
  `com.agency-memory.consolidate.plist.template` (launchd, runs missed jobs on wake) +
  `github-actions-consolidate.yml.template` (cloud, with the privacy trade-off noted).
- [INFRA] **Templates:** `templates/client/` (client scaffold) and `templates/world/`
  (world scaffold + `world.json.example` showing a Hungarian override).
- [FIX] Pure-plugin cutover: emptied the kit `.claude/settings.json` hooks block and
  deleted the superseded `.claude/hooks/` scripts and `system/memory-consolidation/`
  (replaced by the plugin copies).
- [DOC] README rewritten for the plugin model + an open-beta notice; added `SECURITY.md`
  (local-only model, the single Anthropic-API call, human-approval guarantees, vuln
  reporting); `install.sh` repurposed for the plugin flow.
- Note: full `claude plugin validate` + plugin enable is a manual step (CLI not available
  in the build session). Wiring a live instance onto the plugin is a separate, later step.
