# Agency Memory Kit

Deterministic, folder-based memory for [Claude Code](https://claude.com/claude-code)
when you run an agency with many clients. Packaged as a Claude Code **plugin**.

## Open beta, read this first

This is an **open beta**, not a finished product. It is a first attempt at solving
agency memory, shared in the open: from the people, for the people. Use it however you
want, fork it, tear it apart. Just keep in mind while you use it that this is genuinely
the open beta of a first try, so expect rough edges and treat your real client data with
care (keep backups, review what the weekly run proposes before you accept it). Nothing
here writes to your hand-curated files or archives anything without your approval, by
design, but you are still the last line of defense.

## The idea

Most "AI memory" tools use a global vault: one shared pile the model reads and writes
across every project. For an agency that is a liability - client A's data can surface
while you work on client B.

This kit takes the opposite stance:

> **The client folder is the single source of truth. There is no global vault.**

Client data cannot leak across clients because there is no shared pile to leak through.
Memory loading is deterministic (a hook injects a fixed load order, not a fuzzy
similarity search), and memory capture is agent-driven into the one client folder the
session is actually about. When it is ambiguous which client a learning belongs to, it
goes to a quarantine inbox and you file it - it is never guessed into the wrong folder.

## Engine and data are separate

The plugin is the **engine** (hooks + scripts + config schema). Your agency's **data**
is a separate "world": a folder with `clients/` and `system/memory/`. One engine can
serve many worlds, and the engine never hardcodes your section names or language - those
live in your world config (`system/memory/world.json`), which overrides the plugin's
English defaults. A Hungarian agency ships a Hungarian `world.json`; the engine does not
change.

- The scripts find **themselves** via `${CLAUDE_PLUGIN_ROOT}`.
- They find **your data** via, in order: `--world` / `AGENCY_WORLD_ROOT`, then
  `CLAUDE_PROJECT_DIR` (set by Claude Code for hooks), then the current directory.

## How it works

- **Load (start of every prompt):** a `UserPromptSubmit` hook injects your world's
  `system/memory/context-load-order.md`, which tells Claude exactly which client files
  to read for the task at hand.
- **Continuity (start of every session):** a `SessionStart` hook injects the
  "Next session briefing" from `system/memory/learnings.md` for system/dev work.
- **Guard (before a Write/Edit):** a `PreToolUse` hook surfaces the memory constraints
  you configured for matching file paths (optional, off until you configure guards).
- **Capture (end of session / before compact):** Claude writes learnings into the
  correct client's folder per the rules in `CLAUDE.md` and `compact-protocol.md`.
- **Hygiene (weekly):** `consolidate.py` dedups and merges each client's `learnings.md`
  losslessly (no entry is evicted automatically), regenerates `cross-client-patterns.md`,
  and surfaces candidate lists - durable rules worth promoting, plus superseded/stale
  entries proposed for archiving. Archiving and promotion happen only with your approval.
- **Self-improving tool-craft (weekly, since 0.2.0):** the weekly run mines your session
  transcripts for *recurring* tool mistakes (the same tool used wrong across several
  sessions, or a tool you keep rejecting). It proposes them as `tool-craft` candidates.
  When you approve one, it becomes a rule in `system/memory/tool-craft.md`. Enforceable
  rules are read by a `PreToolUse` guard that **warns** before the matching call (WARN-only,
  it never blocks). A rule only becomes a hard block with a separate, explicit approval -
  so the system goes from "I told you" to "you can't", on your say-so.
- **cheap-Dreaming (weekly, since 0.2.0):** for sessions that were cleanly about a single
  client, the weekly run mines the *raw* transcript for durable client learnings that the
  end-of-session capture missed (e.g. abandoned/compacted sessions). A strict single-client
  gate keeps no-mixing intact; candidates go to `client-learning-candidates.md` for review.

## Requirements

- Claude Code with plugin support
- Python 3 (the hooks and scripts use it). The plugin asks for the command name at install
  time (the **Python command** config prompt) - usually `python3` on macOS/Linux, `python` on
  Windows. Don't know if you have it? Run the bundled bootstrap script (below) - it detects or
  installs Python and prints the exact value to enter.
- `anthropic` Python package + `ANTHROPIC_API_KEY` - only for the weekly `consolidate.py`
  (since 0.2.0 it also runs the tool-craft judge and the cheap-Dreaming miner, which adds a
  small per-run cost that scales with how many sessions you had that week)

### Upgrading from 0.1.x to 0.2.0

The engine update brings the new scripts, the `PreToolUse` tool-craft guard, and the
`tool-craft.md` template. Your existing world data is never overwritten, so the new
`system/memory/tool-craft.md` is **seeded automatically** on your first weekly
`consolidate.py` run after the update (the guard is a harmless no-op until it exists). No
manual step. The guard ships in **WARN mode**: it warns, never blocks, until you explicitly
promote a rule.

## Install

> The plugin installs from the **marketplace** (`.claude-plugin/marketplace.json`). Two
> surfaces: the **Claude desktop app** (GUI), or a **terminal** (a Claude Code session's
> `/plugin` commands, or the `claude plugin` CLI). The `/plugin` command is **not** available
> in the VS Code / JetBrains extension UI - use the desktop app or a terminal. If `claude` is
> not on your `PATH`, call it by its full path (commonly `~/.local/bin/claude`).

**0. (Recommended) Run the bootstrap script first.** It checks for Python 3 (offers to
install it via Homebrew/apt/winget if missing), then prints the exact value to type into the
plugin's **Python command** prompt in step 1. Skip this only if you already know your Python
command works.

```bash
# macOS / Linux - from the folder that contains your clone
bash agency-memory-kit/install.sh
```
```powershell
# Windows (PowerShell) - from inside your clone
powershell -ExecutionPolicy Bypass -File install.ps1
```

**1. Add the marketplace and enable the plugin.**

*Desktop app (recommended):* open the plugin manager (Customize / Settings) -> **Add
marketplace** -> in the URL field enter the repo as a GitHub `owner/repo` (e.g.
`krsnczky/agency-memory-kit`) or its git URL -> **Sync** -> open the synced marketplace and
enable the **agency-memory** plugin. The GUI takes a GitHub repo or git URL only (not a local
path), so the repo must be on GitHub and your account must have access (collaborator on a
private repo, or public).

*Terminal (alternative):* in a Claude Code session run `/plugin marketplace add
./agency-memory-kit` then `/plugin install agency-memory@agency-memory-kit`. Same thing via
the `claude plugin` CLI (copy-paste friendly) - a local path must start with `./` (a bare `.`
is rejected), so run it from the folder that *contains* your clone:

```bash
claude plugin marketplace add ./agency-memory-kit    # or <owner/repo or git-url>
claude plugin install agency-memory@agency-memory-kit
```

During install the plugin asks for the **Python command** - enter the value the bootstrap
script printed in step 0 (`python3` on macOS/Linux, `python` on Windows). This is the command
the hooks use to run their scripts.

**2. Mind the install scope.** Plugins install at `--scope user` by default = active in
**every** Claude Code project you open. If you already run Claude Code in another repo that
ships its **own** memory hooks, a user-scope install double-fires there. To bind it to one
world, install with local scope from inside that world:

```bash
cd /path/to/my-world
claude plugin install agency-memory@agency-memory-kit --scope local
```

**3. Set up a world (your data root).** Use this repo's root as a ready-made world, or
scaffold a fresh one from the bundled template (run from your clone):

```bash
cp -r agency-memory-kit/plugins/agency-memory/templates/world/. /path/to/my-world/
```

The scaffold ships a `CLAUDE.md` (the memory protocol the agent follows), the
`system/memory/` files, and an empty `clients/`. Run Claude Code from your world folder;
the hooks fire automatically and resolve your data via `CLAUDE_PROJECT_DIR`.

**4. (Optional) Localize.** In your world, copy `system/memory/world.json.example` to
`system/memory/world.json` and edit it to override section names, the briefing heading,
the curated-file prefix, and the memory guards. Anything you do not set falls back to the
plugin's English defaults.

> Modifying the plugin itself? `claude plugin validate <path-to-plugin>` checks the manifest
> (a developer sanity check, not needed to install or use the plugin).

## Usage

**Create a client.** Copy the bundled client template into your world's `clients/`:
```bash
cp -r agency-memory-kit/plugins/agency-memory/templates/client /path/to/my-world/clients/acme-corp
```
Then fill in the placeholders in `clients/acme-corp/wiki/`. (If you are working inside this
kit repo itself, `bash new-client.sh acme-corp` does the same from `clients/_template`.)

**Daily:** just work. Mention the client, Claude loads its context. At session end (or
when you `/compact`), Claude writes the session's learnings into that client's folder.

**Customize the load order:** edit `system/memory/context-load-order.md` so the
task-specific rows match your agency's work (the shipped rows are examples).

**Weekly consolidation (optional, recommended).** Run it against your world:
```bash
AGENCY_WORLD_ROOT=/path/to/my-world bash plugins/agency-memory/runners/run-weekly.sh
```
`run-weekly.sh` sources `~/.anthropic.env` (so a key not in your shell rc is still found)
and runs `consolidate.py --world ...`. It dedups/merges each client's `learnings.md`
losslessly, consolidates the system learnings against `system/logs/CHANGELOG.md`,
regenerates `cross-client-patterns.md`, and refreshes the candidate review files tracked
in `candidates-state.json`. The "Next session briefing" is preserved verbatim. Nothing is
archived or promoted automatically - those are your approvals, surfaced by id.

**Schedule it.** Templates ship in `plugins/agency-memory/runners/` (fill the
placeholders, none auto-installs):

- `com.agency-memory.consolidate.plist.template` - **macOS** launchd. Preferred locally:
  if the Mac is asleep at the scheduled time, launchd runs the missed job on next wake;
  plain cron silently skips it.
- `agency-memory-consolidate.service.template` + `.timer.template` - **Linux** systemd
  user timer. `Persistent=true` is the launchd equivalent: a missed run (machine off)
  fires on next boot. A plain-cron one-liner is in the timer template's header.
- `run-weekly.ps1` - **Windows** PowerShell wrapper for Task Scheduler (the schedule +
  catch-up note is in its header). Provisional: the cross-platform hooks are in place, but
  Windows has not been end-to-end tested yet.
- `github-actions-consolidate.yml.template` - **any OS**, machine-independent cloud run.
  Trade-off: it checks out your world (client data) on a GitHub runner, so keep the world
  repo private, and do not make the cloud path your only path if the data is sensitive.

The daily hooks are all pure-Python (stdlib only), so they run on macOS, Linux, and
Windows with no bash dependency. The hook command uses whatever you entered at the **Python
command** config prompt on install (`python3` on macOS/Linux, `python` on Windows - the
bootstrap script in step 0 prints the right value). To change it later, edit the plugin's
config or re-run `/plugin`.

## Structure

```
.claude-plugin/
  marketplace.json          marketplace catalog
plugins/agency-memory/
  .claude-plugin/plugin.json
  hooks/
    hooks.json              hook wiring (uses ${CLAUDE_PLUGIN_ROOT})
    scripts/                system-briefing.py, context-injector.py,
                            session-logger.sh, memory-guard.py
  scripts/
    agency_common.py        world-root resolution + config loader
    consolidate.py          weekly consolidation + candidate detection
    candidates_nudge.py, client_candidates.py
    world.default.json      English default config
  runners/                  run-weekly.sh + launchd / GitHub Actions templates
  templates/
    client/                 scaffold for a new client
    world/                  scaffold for a new world (+ world.json.example)

# a WORLD (your data; this repo root is also a working one):
system/
  memory/                   memory-policy, context-load-order, compact-protocol,
                            world.json (optional), learnings, inbox,
                            candidates-state.json + generated review files
  logs/                     CHANGELOG.md + sessions/
clients/
  _template/                source for new-client.sh
  <your clients>/
CLAUDE.md                   the memory protocol Claude follows
```

## Security

The plugin operates on local files only and sends no telemetry. The one network call in
the whole kit is the optional weekly `consolidate.py`, which sends your learnings to the
Anthropic API to summarize them. By design, nothing is archived, promoted, or written to
your hand-curated files without your approval. Full details, the data-handling notes, and
how to report a vulnerability are in [SECURITY.md](SECURITY.md). Read it before pointing
the kit at real client data.

## License

[MIT](LICENSE). Open beta (see the top of this README): use it, fork it, build on it.
No warranty, and the API/data caveats in [SECURITY.md](SECURITY.md) are yours to manage.
