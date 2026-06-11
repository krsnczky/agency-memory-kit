# Changelog

All notable changes to agency-memory-kit are recorded here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Bootstrap installers (`install.sh` for macOS/Linux, `install.ps1` for Windows): detect
  Python 3, offer to install it (Homebrew/apt/dnf/pacman/zypper, or winget on Windows), and
  print the exact value to enter at the plugin's **Python command** config prompt.
- `userConfig.python` in `plugin.json`: the plugin asks for the Python command on install, so
  the hooks run with the right interpreter on any OS (`python3` on macOS/Linux, `python` on
  Windows). All five hooks invoke `${user_config.python}`.
- Per-OS install documentation in the README (bootstrap step, Python-command notes).

### Changed
- World template `CLAUDE.md`: system/dev session logging now explicitly creates
  `system/logs/CHANGELOG.md` (and its folder) if it does not exist, instead of assuming it
  is already there.

### Notes
- Windows is **provisional**: the `install.ps1` winget id and the Windows Python launcher
  name have not yet been verified end-to-end on a real machine. Verify before relying on it.

## [0.2.3] - 2026-06-11

### Changed
- Ported the session-logger hook from Bash to Python. All five hooks are now pure Python
  (stdlib only) and run on macOS, Linux, and Windows with no Bash dependency.

### Added
- `run-weekly.ps1`: Windows PowerShell wrapper for the weekly consolidation (Task Scheduler).

## [0.2.2] - 2026-06-11

### Added
- Linux systemd runner templates (`.service` + `.timer`) for the weekly consolidation, with
  `Persistent=true` so a run missed while the machine was off fires on next boot.

## [0.2.1] - 2026-06-08

### Fixed
- `client_candidates.py` now surfaces the `client-learning` stream at point-of-use (it was
  previously skipped), so open client-learning candidates show up when you work that client.

## [0.2.0] - 2026-06-07

### Added
- Self-improving tool-craft loop: mine recurring tool mistakes and user rejections from
  transcripts (`craft_detector.py` → `craft_judge.py`), promote durable lessons to
  `tool-craft.md`, and enforce them with a `PreToolUse` guard (`tool_craft_guard.py`) in
  WARN mode (it warns, never blocks, until you promote a rule).
- Cheap-Dreaming: mine client learnings from the raw transcripts of single-client sessions
  (`dream_extractor.py`), gated so no cross-client mixing can occur, feeding the existing
  human-approved candidate review pipeline.
- Cadence wiring: the weekly `consolidate.py` now also runs the tool-craft judge and the
  cheap-Dreaming miner, with cross-stream dedup and audit trail.
- Bi-temporal fact markers (`[true: ... | recorded: ...]`) for sharper stale detection.
- Self-bootstrap: an existing world automatically receives `system/memory/tool-craft.md` from
  the template on its first weekly run after upgrading; the engine never overwrites existing
  files.

## [0.1.1] - 2026-06-04

### Fixed
- `memory-guard.py` derives the project slug the same way Claude Code does, so the guard
  resolves the correct world path.

## [0.1.0]

### Added
- Initial release: per-client, no-mixing memory engine. Deterministic context loading
  (SessionStart briefing + UserPromptSubmit load-order injection), weekly consolidation with
  lossless per-client merge, human-approved candidate review, session-trace archiving, and a
  memory-guard. Engine and data (world) are separate; localizable via `world.json`.
