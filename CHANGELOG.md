# Changelog

All notable changes to agency-memory-kit are recorded here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.8] - 2026-07-13

Production incident round - three bugs reported from the second production world
(2026-07-10 weekly run), all three verified present in the first production world too.

### Fixed
- **Language drift corrupted non-English memory (SEVERE):** with `output_language`
  missing from a non-English world's `world.json`, the engine falls back to English and
  the consolidation prompt actively instructs the model to TRANSLATE the data (observed:
  a full file rewritten in English; bilingual duplication doubling another file). Three
  layers now: (1) `world.json.example` ships the four i18n keys (`output_language`,
  `placeholder_markers`, `placeholder`, `footer_prefix`) with a CRITICAL warning - they
  were missing from the example, which is how a production world ended up half-configured;
  (2) the prompts explicitly forbid translating existing entries or adding translated
  duplicates; (3) a language-drift guard compares the non-ASCII letter ratio of input vs
  output and SKIPS the write (+ audit flag) when the ratio drops below 60% of the input's.
- **"Lossless" accepted lossy shortening of surviving entries (SEVERE):** the 60%
  token-overlap survival check let the model shorten existing bullets and drop concrete
  facts (file paths, version numbers, "tell X" notes). Now: the prompts require existing
  entries to survive character-for-character (dedup may only drop exact duplicates of a
  more detailed entry), and `_reinject_dropped` re-injects any original bullet whose hard
  tokens (paths, filenames, version numbers, backticked spans) vanished from the section.
- **`max_tokens=3000` was a silent ceiling:** the consolidation is lossless, so output is
  input-sized - every learnings.md above ~3000 output tokens truncated, the safety skip
  kept the original, and the file just kept growing (self-worsening; the three largest
  files in both production worlds were stuck for weeks). Now world-configurable:
  `consolidate_max_tokens`, default 16000.
- **Skipped entities were invisible:** the audit trail only logged successes, so a stuck
  file went unnoticed until a human asked. Skips (truncation, language drift, API error)
  now write an audit line and the run ends with a warning listing every skipped entity.

## [0.2.7] - 2026-07-03

### Added
- **No-mixing guard on the agent write path** (memory-guard hook): writing under
  `clients/<X>/` with content that mentions ANOTHER known client triggers a WARN via
  `additionalContext`. Until now the machine no-mixing gate existed only on the
  transcript-mining path (dream_extractor leak check); the primary path - the agent
  writing a client's memory at session end - was convention-only. Automatic when the
  world has a `clients/` dir; no config needed; WARN-only (a conscious cross-client
  reference stays possible).
- **Briefing retention** (`briefing_keep_checkpoints`, default 0 = off): the
  verbatim-protected next-briefing section was a one-way valve - it only ever grew
  (the first production world hit 43KB injected at every session start). When enabled,
  the weekly system consolidation keeps the newest N checkpoint blocks and APPENDS the
  swept ones to `system/memory/archive/briefing-archive.md` - deterministic trim, no
  LLM involvement, nothing deleted. Block boundaries via `briefing_block_regex`
  (default: lines starting with `**...CHECKPOINT`).
- **Global/system candidates surface contentfully at session start**: they have no
  point-of-use venue (no client load ever shows them), so a bare count let them rot -
  the first production world had candidates 3+ weeks stale. `candidates_nudge` now
  prints the oldest few (cap 5, id + type + age + text) so they can be accepted or
  rejected on the spot.

## [0.2.6] - 2026-07-03

Silent-failure hardening + review-cycle quality-of-life round (sourced from the first
production world's infra audit; every item was verified against live hook behavior).

### Fixed
- **memory-guard warnings were invisible to the model** - the PreToolUse hook printed to
  plain stdout with exit 0, which Claude Code does not surface. Warnings now go through
  `hookSpecificOutput.additionalContext` (same pattern as tool_craft_guard). The hook had
  been a silent no-op since its first version.
- **A failed transcript-mining (Dreaming) run was silent** and its week of learnings aged
  out of the window for good. Now: the dream window is 10 days (weekly cadence + overlap,
  one missed run no longer loses data), the failure is recorded in
  `candidates-state.json["last_run"]`, and `candidates_nudge` warns at session start.
- **Truncated consolidation output went undetected**: `stop_reason == "max_tokens"` is now
  checked on both consolidation calls; the write is skipped and the original file kept.
- **The client next-briefing section was consolidated** (system-only verbatim before); a
  world that keeps a hand-curated briefing section in client files no longer loses it to
  the LLM pass.
- `candidates_nudge` crashed (swallowed traceback -> nudge silently missing) on a candidate
  with missing `type`/`scope` keys; all state access is now `.get()`-safe in the nudge,
  `write_review_files` and `_find_match`, and an unexpected nudge error prints one visible
  line into the briefing instead of vanishing. The nudge subprocess also runs with
  `sys.executable` (the configured plugin python) instead of a hardcoded `python3`.

### Added
- **Progressive disclosure for the per-prompt context injection**: if the world's
  `context-load-order.md` contains a `<!-- prompt-reminder:start/end -->` block, only that
  short block is injected per prompt; the FULL table is injected once per session start by
  system-briefing (SessionStart fires on compaction too, so the full table survives
  compaction). Without markers the behavior is unchanged (full file per prompt). The world
  template ships the marker block.
- **tool-craft Advisory delivery**: the approved Advisory section of `tool-craft.md` is now
  injected at session start (previously the advisory lessons were approved into the file
  but nothing ever delivered them to the model - the enforceable table was machine-read,
  the advisory list was dead).
- **WARN->DENY escalation surfacing**: `candidates_nudge` reads
  `tool-craft-violations.json` and flags rules hit >= 5 times as DENY-ripe (the escalation
  counter finally has a consumer).
- **`consolidate.py --reviews-only`**: regenerate the review .md files from
  `candidates-state.json` with no API calls - run it after accept/reject so the .md
  snapshots do not go stale; the review-file headers now state that the state file is the
  source of truth.
- **Observation taxonomy (`obs_type`)**: dream-mined client learnings are typed
  (decision / gotcha / result / rule / learning), carried through the candidate state and
  shown in review files and point-of-use surfacing - faster review, and the type can steer
  where an accepted learning lands.

### Changed
- `candidates_nudge` counts `client-learning` candidates as client-scoped (consistent with
  point-of-use surfacing in `client_candidates.py`); they were previously lumped into the
  "global" count.

## [0.2.5] - 2026-07-03

### Added
- **World-configurable placeholders, footer and output language** (completes the i18n
  genericization; found while dry-running a Hungarian world flip). Four new world-config keys
  with English defaults in `world.default.json`: `placeholder_markers`, `placeholder`,
  `footer_prefix`, `output_language`. Without these a non-English world silently corrupted
  data: the world's footer line leaked into section bodies on rebuild (the English
  `FOOTER_PREFIX` never matched), placeholder sections were mis-detected as content, and the
  rebuilt file mixed languages.
- LLM prompts (`consolidate.py` client + system, `dream_extractor.py` learnings,
  `craft_judge.py` rules) now instruct the model to write generated content in the world's
  `output_language`, so a non-English world gets learnings/rules in its own language
  deterministically instead of whatever the model picks up from the transcript.

### Fixed
- **Non-English "Next session briefing" lost its verbatim protection:** the system
  consolidation hardcoded `verbatim=("Next session briefing",)` instead of using the world's
  `next_briefing_heading`, so on a non-English world the hand-curated briefing section would
  have gone through the LLM instead of being preserved byte-for-byte. The consolidation
  prompts' EVERGREEN/footer/briefing references were also hardcoded English section names;
  they now come from the world config.

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
