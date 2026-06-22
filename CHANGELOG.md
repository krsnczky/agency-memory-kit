# Changelog

All notable changes to agency-memory-kit are recorded here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.4] - 2026-06-22

### Added
- Bootstrap installers (`install.sh` for macOS/Linux, `install.ps1` for Windows): detect
  Python 3, offer to install it (Homebrew/apt/dnf/pacman/zypper, or winget on Windows), and
  print the exact value to enter at the plugin's **Python command** config prompt.
- `userConfig.python` in `plugin.json`: the plugin asks for the Python command on install, so
  the hooks run with the right interpreter on any OS (`python3` on macOS/Linux, `python` on
  Windows). All five hooks invoke `${user_config.python}`.
- Per-OS install documentation in the README (bootstrap step, Python-command notes).

### Fixed
- **Windows plugin load failure (BLOCKER):** removed the `"hooks"` key from `plugin.json`.
  Current Claude Code auto-loads `hooks/hooks.json`; declaring it again caused a "Duplicate
  hooks file" hard load failure that disabled the whole plugin.
- **Windows hook crash on non-UTF-8 locales (BLOCKER):** every entry script that prints
  (5 hooks + `consolidate.py`, `client_candidates.py`, `candidates_nudge.py`) now forces
  `sys.stdout/stderr` to UTF-8. On a cp1250 (etc.) console, emoji in hook output raised
  `UnicodeEncodeError` and aborted the prompt; macOS/Linux default to UTF-8 so it was invisible there.
- **`install.ps1` never selected `python`/`python3` (only `py -3`):** for a single-token
  command the arg slice `$parts[1..0]` is a *descending* PowerShell range that wrongly returned
  the command name as a spurious argument, so the probe failed. Guarded the slice for the
  single-token case (3 spots; the per-`$PyCmd` split is now computed once and reused).
- **`run-weekly.ps1` hardcoded `python`:** a scheduled run on a box where the real interpreter
  is `py -3`/`python3` could hit the Microsoft Store stub and fail silently. The runner now
  auto-detects the interpreter (prefers `py -3`), overridable via `AGENCY_PYTHON`.

### Changed
- World template `CLAUDE.md`: system/dev session logging now explicitly creates
  `system/logs/CHANGELOG.md` (and its folder) if it does not exist, instead of assuming it
  is already there.
- `run-weekly.ps1`: reads `ANTHROPIC_API_KEY` from a `.anthropic.env` key file when the env var
  is unset (parity with `run-weekly.sh`, keeps the key out of the registry), sets
  `PYTHONUTF8=1`, and its header now carries a PowerShell `Register-ScheduledTask` recipe with
  `-StartWhenAvailable` (launchd-style catch-up that `schtasks` can't set).
- README: actionable Windows "Python on PATH" troubleshooting (use `python`/`py -3` not
  `python3`; Microsoft Store alias-stub gotcha).

### Notes
- Verified end-to-end on real Windows (Win10/cp1250, Claude Code 2.1.185, Python 3.13, `dev`
  branch): plugin loads, all hooks fire, weekly consolidation runs (manual + Task Scheduler),
  and `run-weekly.ps1` reads the key from `.anthropic.env`.
- Still unverified on Windows: the `install.ps1` winget INSTALL path (the test used a python.org
  install), and interpreter detection on a box with no `py` launcher (the B1 fix targets exactly
  that case). Verify on next Windows pass.

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
