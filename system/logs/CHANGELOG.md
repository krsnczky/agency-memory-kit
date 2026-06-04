# Changelog

_System/dev changes. Append newest at top with a date and a tag:
[INFRA] [HOOK] [FIX] [DOC]._

---

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
