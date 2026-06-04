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

## Requirements

- Claude Code with plugin support
- `python3` (the hooks and scripts use it)
- `anthropic` Python package + `ANTHROPIC_API_KEY` - only for the weekly `consolidate.py`

## Install

> **Installation goes through the marketplace** (`.claude-plugin/marketplace.json`) - that
> is the catalog the plugin installs from. You can drive it two ways, both in a **terminal**:
> the `/plugin ...` slash commands inside a terminal Claude Code session, or the
> `claude plugin ...` CLI subcommands. The `/plugin` command is **not** available in the
> VS Code / JetBrains extension UI, so use a terminal. If `claude` is not on your `PATH`,
> call it by its full path (commonly `~/.local/bin/claude`).

**1. (Optional) Validate the plugin** from your clone:

```bash
claude plugin validate ./agency-memory-kit/plugins/agency-memory
```

**2. Add the marketplace and install.** Inside a terminal Claude Code session, the slash form:

```
/plugin marketplace add ./agency-memory-kit
/plugin install agency-memory@agency-memory-kit
```

Or the equivalent CLI (copy-paste friendly). A local marketplace path must start with `./`
(a bare `.` is rejected), so run it from the folder that *contains* your clone:

```bash
claude plugin marketplace add ./agency-memory-kit
claude plugin install agency-memory@agency-memory-kit
# once hosted on git you can instead use: claude plugin marketplace add <owner/repo or git-url>
```

**3. Mind the install scope.** Both forms install at `--scope user` by default, which makes
the plugin active in **every** Claude Code project you open. If you already run Claude Code
in another repo that ships its **own** memory hooks, a user-scope install double-fires there.
To bind it to one world, `cd` into that world and install with local scope:

```bash
cd /path/to/my-world
claude plugin install agency-memory@agency-memory-kit --scope local
# slash equivalent (in a session started from that folder): /plugin install agency-memory@agency-memory-kit --scope local
```

**4. Set up a world (your data root).** Use this repo's root as a ready-made world, or
scaffold a fresh one from the bundled template (run from your clone):

```bash
cp -r agency-memory-kit/plugins/agency-memory/templates/world/. /path/to/my-world/
```

The scaffold ships a `CLAUDE.md` (the memory protocol the agent follows), the
`system/memory/` files, and an empty `clients/`. Run Claude Code from your world folder;
the hooks fire automatically and resolve your data via `CLAUDE_PROJECT_DIR`.

**5. (Optional) Localize.** In your world, copy `system/memory/world.json.example` to
`system/memory/world.json` and edit it to override section names, the briefing heading,
the curated-file prefix, and the memory guards. Anything you do not set falls back to the
plugin's English defaults.

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

**Schedule it.** Two templates ship in `plugins/agency-memory/runners/` (fill the
placeholders, neither auto-installs):

- `com.agency-memory.consolidate.plist.template` - macOS launchd. Preferred locally:
  if the Mac is asleep at the scheduled time, launchd runs the missed job on next wake;
  plain cron silently skips it.
- `github-actions-consolidate.yml.template` - machine-independent cloud run. Trade-off:
  it checks out your world (client data) on a GitHub runner, so keep the world repo
  private, and do not make the cloud path your only path if the data is sensitive.

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
