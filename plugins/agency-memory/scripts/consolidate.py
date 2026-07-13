#!/usr/bin/env python3
"""
consolidate.py
Purpose: Weekly batch script - for every client, deduplicates learnings.md,
         resolves contradictions, and writes back a consolidated version.
         Also: system-level consolidation, candidate detection (promotion / sweep /
         wiki-promotion), cross-client patterns.
Options:
  python3 system/memory-consolidation/consolidate.py
  python3 system/memory-consolidation/consolidate.py --dry-run
  python3 system/memory-consolidation/consolidate.py --client acme-corp
  python3 system/memory-consolidation/consolidate.py --system-only
  python3 system/memory-consolidation/consolidate.py --cross-client-only
Requires: anthropic package + ANTHROPIC_API_KEY in the environment.
Notes:
  - Deterministic rebuild (rebuild_learnings) instead of a "missing section -> reject"
    validator (that false-positived on an empty placeholder section the LLM omits);
    garbage LLM output degrades to a no-op.
  - The system "Next session briefing" is preserved verbatim (live hand-curated handoff).
  - CHANGELOG window takes the head [:8000] (newest first); client logs take the tail
    [-8000:] (newest at bottom).
  - WEEKLY RUN IS LOSSLESS: no per-section entry cap, and protected sections never lose
    a unique entry (dedup/merge OK, eviction not). Archiving (superseded + stale) is a
    human-approved sweep candidate, never automatic.
Changelog:
  2026-05-31 - Extracted to agency-memory-kit; full English; deterministic rebuild.
  2026-06-03 - Phases 1-5 ported from the source instance:
               * Phase 1: removed the "max N entries per section" cap (it evicted good
                 entries); implicit-learning extraction is now a strict quality gate
                 (grounding + denylist + permission to add nothing) with no count limit;
                 ~500-line aggressive-dedup trigger; backup -> memory/archive/backup/.
               * Phase 2: weekly run is lossless. archive_faded is no longer called on the
                 weekly path (kept for the manual sweep-accept flow). Protected sections
                 (PROTECTED_*) re-inject any unique dropped bullet (_reinject_dropped).
               * Phase 3: candidate state machine (candidates-state.json): promotion +
                 sweep candidates flow through aging/identity tracking into review files
                 (promotion-candidates.md / sweep-candidates.md). Weekly run only DETECTS;
                 archiving happens with human approval. Nudge: candidates_nudge.py.
               * Phase 5: wiki-promotion candidates - durable account FACTS from a client's
                 operational learnings.md proposed into curated wiki/campaigns-<area>.md
                 files (separate stream from promotion: a GENERAL rule -> CLAUDE.md, an
                 account FACT -> wiki). Runs only for clients that keep curated per-area
                 files; gets the curated content so it never proposes a duplicate.
  2026-07-13 - Production incident round (bug report from the second production world,
               all three verified in the first one too):
               * max_tokens 3000 -> world-config consolidate_max_tokens (default 16000):
                 3000 was a silent ceiling - the largest learnings.md files truncated,
                 the safety skip kept them unconsolidated forever (self-worsening).
               * Language-drift guard: if the consolidated output loses >=50% of the
                 input's non-ASCII letter ratio (translation / bilingual duplication,
                 seen with a mis-set output_language), the write is skipped + flagged.
                 Prompts now also forbid translating or duplicating existing entries.
               * Lossless hardened: existing entries must survive character-for-character
                 (prompt) AND _reinject_dropped re-injects any bullet whose hard tokens
                 (paths, filenames, versions, backticked spans) vanished - the 60%
                 token-overlap check alone accepted lossy shortening.
               * Skip visibility: skipped entities (truncation, drift, API error) go to
                 consolidation-audit.md + an end-of-run warning; they used to be
                 invisible (audit logged successes only), hiding failures for weeks.
  2026-07-03 - Silent-failure hardening + review-cycle QoL:
               * stop_reason==max_tokens is detected on both consolidation calls: the
                 write is skipped and the original kept (no silent truncation).
               * Client next-briefing section is verbatim too (was system-only).
               * detect_new_extractors: dream window 7->10 days (overlap: one missed
                 weekly run no longer loses that week for good) + failure recorded in
                 state["last_run"] -> candidates_nudge warns at session start.
               * --reviews-only: regenerate review .md files from state with no API
                 (run after accept/reject so the .md snapshots do not go stale);
                 review-file headers state that candidates-state.json is the truth.
               * obs_type taxonomy (decision/gotcha/result/rule/learning) carried
                 through sync_candidates and shown in review files.
"""

import argparse
import json
import re
import sys

# Windows / non-UTF-8 locales: emoji in stdout would crash (e.g. cp1250). Force UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import anthropic
from datetime import datetime
from pathlib import Path

from agency_common import resolve_world_root, load_world_config

TODAY = datetime.now().strftime("%Y-%m-%d")

# World-resolved config (set by configure() at runtime). Section names, protected/
# evergreen sets, and paths are NOT hardcoded - they come from the world config layer
# (<world>/system/memory/world.json, English defaults bundled with the plugin), so a
# Hungarian (or any) instance overrides them. Module-level placeholders so references
# exist before configure() runs.
REPO_ROOT = None
CLIENTS_DIR = None
SECTIONS = None
SYSTEM_SECTIONS = None
PROTECTED_SECTIONS = None
PROTECTED_SYSTEM_SECTIONS = None
EVERGREEN_SECTIONS = None
CURATED_PREFIX = None
CURATED_GLOB = None
PROMOTION_CANDIDATES_PATH = None
SWEEP_CANDIDATES_PATH = None
WIKI_PROMOTION_CANDIDATES_PATH = None
CROSS_CLIENT_PATH = None
CANDIDATES_STATE_PATH = None


def configure(world_root):
    """Resolve every world-dependent global from the world config layer. Called once at
    the start of main(). The engine stays generic; the world supplies the section names
    (e.g. Hungarian) and lives at world_root."""
    global REPO_ROOT, CLIENTS_DIR
    global SECTIONS, SYSTEM_SECTIONS, PROTECTED_SECTIONS, PROTECTED_SYSTEM_SECTIONS, EVERGREEN_SECTIONS
    global CURATED_PREFIX, CURATED_GLOB
    global PROMOTION_CANDIDATES_PATH, SWEEP_CANDIDATES_PATH, WIKI_PROMOTION_CANDIDATES_PATH
    global CROSS_CLIENT_PATH, CANDIDATES_STATE_PATH
    global _PLACEHOLDER_MARKERS, PLACEHOLDER, FOOTER_PREFIX, OUTPUT_LANGUAGE, NEXT_BRIEFING_HEADING
    global BRIEFING_KEEP_CHECKPOINTS, BRIEFING_BLOCK_REGEX

    REPO_ROOT = Path(world_root)
    CLIENTS_DIR = REPO_ROOT / "clients"

    cfg = load_world_config(REPO_ROOT)
    SECTIONS = cfg["sections"]
    SYSTEM_SECTIONS = cfg["system_sections"]
    PROTECTED_SECTIONS = cfg["protected_sections"]
    PROTECTED_SYSTEM_SECTIONS = cfg["protected_system_sections"]
    EVERGREEN_SECTIONS = cfg["evergreen_sections"]
    CURATED_PREFIX = cfg["curated_prefix"]
    CURATED_GLOB = f"{CURATED_PREFIX}*.md"
    _PLACEHOLDER_MARKERS = tuple(cfg["placeholder_markers"])
    PLACEHOLDER = cfg["placeholder"]
    FOOTER_PREFIX = cfg["footer_prefix"]
    OUTPUT_LANGUAGE = cfg["output_language"]
    NEXT_BRIEFING_HEADING = cfg["next_briefing_heading"]
    # Briefing retention (#6): 0 = off (default, backward compatible). N>0: the weekly
    # system consolidation keeps only the newest N checkpoint blocks in the next-briefing
    # section and sweeps the rest to system/memory/archive/briefing-archive.md. Without
    # this the verbatim-protected briefing is a one-way valve - it only ever grows.
    BRIEFING_KEEP_CHECKPOINTS = int(cfg.get("briefing_keep_checkpoints", 0) or 0)
    BRIEFING_BLOCK_REGEX = cfg.get("briefing_block_regex", r"^\*\*[^\n]*CHECKPOINT")
    # Output cap for the consolidation LLM calls. The consolidation is lossless, so the
    # output is roughly input-sized: 3000 was a silent ceiling - every learnings.md that
    # consolidated above ~3000 tokens was skipped forever and only grew (self-worsening).
    global CONSOLIDATE_MAX_TOKENS
    CONSOLIDATE_MAX_TOKENS = int(cfg.get("consolidate_max_tokens", 16000) or 16000)

    mem = REPO_ROOT / "system" / "memory"
    PROMOTION_CANDIDATES_PATH = mem / "promotion-candidates.md"
    SWEEP_CANDIDATES_PATH = mem / "sweep-candidates.md"
    WIKI_PROMOTION_CANDIDATES_PATH = mem / "wiki-promotion-candidates.md"
    CROSS_CLIENT_PATH = mem / "cross-client-patterns.md"
    CANDIDATES_STATE_PATH = mem / "candidates-state.json"

# English defaults; configure() overrides all of these from the world config so a
# non-English world's placeholders/footer/output language are honored (data integrity:
# a mismatched footer prefix would leak footers into section bodies on rebuild).
_PLACEHOLDER_MARKERS = ("_No data", "_None yet", "_Empty")

PLACEHOLDER = "_No data yet._"

FOOTER_PREFIX = "_Last updated"

OUTPUT_LANGUAGE = "English"

NEXT_BRIEFING_HEADING = "Next session briefing"


def extract_bullets(text):
    """Meaningful "- " bullets (placeholders excluded)."""
    out = []
    for l in text.splitlines():
        s = l.strip()
        if s.startswith("- ") and not any(m in s for m in _PLACEHOLDER_MARKERS):
            out.append(s)
    return out


def split_sections(text):
    """(preamble, {section_title: body}) split by '## ' headers.
    preamble = the part before the first '## ' (title, description)."""
    parts = re.split(r"(?m)^## ", text)
    preamble = parts[0].rstrip()
    secs = {}
    for chunk in parts[1:]:
        nl = chunk.find("\n")
        if nl == -1:
            secs[chunk.strip()] = ""
        else:
            secs[chunk[:nl].strip()] = chunk[nl + 1:]
    return preamble, secs


def _clean_body(body):
    """Clean a section body: strip '---' separators and the footer line."""
    lines = []
    for l in body.split("\n"):
        s = l.strip()
        if s == "---" or s.startswith(FOOTER_PREFIX):
            continue
        lines.append(l)
    return "\n".join(lines).strip()


_HARD_TOKEN_RE = re.compile(
    r"`[^`]+`"                                  # backticked spans (commands, paths, ids)
    r"|(?<![\w`])/[\w~][\w./-]{3,}"             # absolute/anchored file paths
    r"|\b\d+\.\d+(?:\.\d+)*\b"                  # version numbers
    r"|\b[\w-]+\.(?:py|md|sh|json|yaml|yml|plist|txt|js|html)\b"  # filenames
)


def _hard_tokens(text):
    """Concrete facts a consolidation must never lose: paths, filenames, versions,
    backticked spans. Production incident: a 'lossless' pass shortened surviving
    bullets and dropped exactly these (a python path, a version, a 'tell Ricsi' note
    in backticks) - the 60% token-overlap survival check cannot see that."""
    return set(m.group(0) for m in _HARD_TOKEN_RE.finditer(text))


def _reinject_dropped(orig_body, new_body):
    """Lossless guarantee for protected sections: any original bullet that does NOT
    survive in the consolidated body (token overlap < 60%), OR that survived only as
    a lossy paraphrase (one of its hard tokens is gone from the whole section), is
    appended back verbatim. Dedup/merge is preserved (a reworded/merged bullet
    survives because its tokens overlap), but neither a UNIQUE entry nor a concrete
    fact can be lost on a weekly run. Re-injection may briefly duplicate a shortened
    variant; the next pass dedups keeping the more detailed one (prompt rule)."""
    orig_bullets = extract_bullets(orig_body)
    new_sets = [_tokens(b) for b in extract_bullets(new_body)]
    dropped = [b for b in orig_bullets if not _survives(_tokens(b), new_sets)]
    for b in orig_bullets:
        if b in dropped:
            continue
        lost = [t for t in _hard_tokens(b) if t not in new_body]
        if lost:
            dropped.append(b)
    if not dropped:
        return new_body
    base = new_body.rstrip()
    if not base or base == PLACEHOLDER:
        return "\n".join(dropped)
    return base + "\n" + "\n".join(dropped)


def rebuild_learnings(llm_output, original, sections, today, verbatim=(), protected=()):
    """Deterministic rebuild from the fixed section schema.
    - Bodies come from the LLM output; `verbatim` sections AND any missing/empty
      section fall back to the ORIGINAL (safe fallback).
    - If the LLM output is unusable (no sections), everything falls back to the
      original = no-op (never writes garbage).
    - In `protected` sections no unique entry can be lost (weekly lossless): dropped
      original bullets are re-injected (_reinject_dropped).
    Replaces the old 'missing section -> reject' validator, which false-positived on
    an empty section (the LLM omitted the placeholder)."""
    preamble, orig_secs = split_sections(original)
    _, out_secs = split_sections(llm_output)
    parts = [preamble, ""]
    for s in sections:
        orig_body = _clean_body(orig_secs.get(s, ""))
        if s in verbatim:
            body = orig_body
        else:
            cand = _clean_body(out_secs.get(s, ""))
            body = cand if cand else orig_body
            if s in protected:
                body = _reinject_dropped(orig_body, body)
        parts.append(f"## {s}\n\n{body if body else PLACEHOLDER}\n")
        parts.append("---\n")
    # Footer derived from FOOTER_PREFIX so _clean_body strips it on the next run
    # regardless of the world's language.
    parts.append(f"{FOOTER_PREFIX}: {today} | Session: weekly-consolidation_")
    return "\n".join(parts)


def _tokens(b):
    """Set of meaningful tokens (no dates, punctuation, short words)."""
    b = b.lower()
    b = re.sub(r"\d{4}-\d{2}-\d{2}", " ", b)
    b = re.sub(r"[^a-z0-9áéíóöőúüű ]", " ", b)
    return {t for t in b.split() if len(t) > 2}


def _survives(old_tok, candidate_sets, thresh=0.6):
    """Survives (i.e. did NOT fade): if >=60% of a candidate bullet's tokens are present.
    Reword-tolerant: a reworded/merged entry counts as kept."""
    if not old_tok:
        return True
    for cs in candidate_sets:
        if cs and len(old_tok & cs) / len(old_tok) >= thresh:
            return True
    return False


def archive_faded(old_text, new_text, archive_path):
    """What was in old but is gone from the consolidated new -> archive (not deleted).
    Token-containment comparison to filter reword noise. Deterministic, no LLM call.

    NOTE (Phase 2): the WEEKLY run no longer calls this (weekly is lossless). Kept for
    the manual sweep-accept flow (superseded + stale, with human approval)."""
    old_b = extract_bullets(old_text)
    new_sets = [_tokens(b) for b in extract_bullets(new_text)]
    existing_archive = archive_path.read_text(encoding="utf-8") if archive_path.exists() else ""
    archive_sets = [_tokens(b) for b in extract_bullets(existing_archive)]
    batch_sets = []

    faded = []
    for b in old_b:
        ot = _tokens(b)
        if _survives(ot, new_sets) or _survives(ot, archive_sets) or _survives(ot, batch_sets):
            continue
        faded.append(b)
        batch_sets.append(ot)

    if not faded:
        return 0

    block = f"\n## Faded / consolidated {TODAY}\n\n" + "\n".join(faded) + "\n"
    if existing_archive:
        archive_path.write_text(existing_archive + block, encoding="utf-8")
    else:
        title = ("# Operational Memory ARCHIVE\n\n"
                 "Not auto-loaded - searchable on demand (grep). "
                 "Holds entries that fell out of learnings.md (reword/merge overlaps with "
                 "the live file are an intentional safety net).\n")
        archive_path.write_text(title + block, encoding="utf-8")
    return len(faded)


def get_clients():
    """All client folder names (skips _template and hidden dirs)."""
    if not CLIENTS_DIR.exists():
        return []
    return [
        d.name for d in CLIENTS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_") and not d.name.startswith(".")
    ]


def read_file(path):
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _ensure_tool_craft_scaffold():
    """Existing worlds (scaffolded before the tool-craft feature) have no tool-craft.md, and an
    engine update never re-scaffolds world data. Seed it from the plugin template if MISSING so
    the feature self-bootstraps (the engine creates a missing scaffold file; it never overwrites
    an existing one). Lets a 0.1.x -> 0.2.0 upgrade pick up the feature with no manual step."""
    try:
        target = REPO_ROOT / "system" / "memory" / "tool-craft.md"
        if target.exists():
            return
        tmpl = Path(__file__).resolve().parent.parent / "templates" / "world" / "system" / "memory" / "tool-craft.md"
        if tmpl.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(tmpl.read_text(encoding="utf-8"), encoding="utf-8")
            print("  [scaffold] seeded missing tool-craft.md from template (0.2.0 upgrade)")
    except Exception:
        pass


def _audit_consolidation(scope, before, after, backup_path):
    """Lightweight audit trail: one line per consolidation into consolidation-audit.md, pointing
    at the pre-consolidation backup (the diffable record of what changed). Never breaks the run."""
    try:
        p = REPO_ROOT / "system" / "memory" / "consolidation-audit.md"
        if not p.exists():
            p.write_text("# Consolidation audit trail\n\n_One line per run; the backup is the diffable "
                         "pre-consolidation state. The weekly LLM pass resolves contradictions; the "
                         "backup -> current diff shows what it merged/replaced._\n\n", encoding="utf-8")
        rel = backup_path.relative_to(REPO_ROOT) if str(backup_path).startswith(str(REPO_ROOT)) else backup_path
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"- {TODAY} | {scope} | {before}->{after} chars | backup: `{rel}`\n")
    except Exception:
        pass


SKIPPED = []  # (scope, reason) - end-of-run visibility; a silent skip hid failures for weeks


def _audit_skip(scope, reason):
    """Skips go into the audit trail too - a skipped entity used to be invisible
    (the audit only recorded successes, so a stuck file went unnoticed for weeks)."""
    SKIPPED.append((scope, reason))
    try:
        p = REPO_ROOT / "system" / "memory" / "consolidation-audit.md"
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"- {TODAY} | {scope} | SKIPPED: {reason}\n")
    except Exception:
        pass


def _lang_ratio(text):
    """Share of non-ASCII letters among all letters - a cheap, language-agnostic
    fingerprint (Hungarian ~10%, English ~0%)."""
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return 0.0
    return sum(1 for c in alpha if ord(c) > 127) / len(alpha)


def _language_drifted(before, after):
    """True when a non-English (accented) file came back substantially de-accented:
    the model translated to English or added translated duplicates (duplication
    roughly HALVES the ratio, hence the 0.6 factor - a legit consolidation barely
    moves it). Guards against a misconfigured output_language corrupting the data."""
    rb, ra = _lang_ratio(before), _lang_ratio(after)
    return rb >= 0.01 and ra < rb * 0.6, rb, ra


def consolidate_client(client_dir_name, dry_run=False):
    client_path = CLIENTS_DIR / client_dir_name
    learnings_path = client_path / "memory" / "learnings.md"
    log_path = client_path / "wiki" / "log.md"

    learnings = read_file(learnings_path)
    if not learnings:
        print(f"  [{client_dir_name}] learnings.md missing - skipped")
        return False

    # Not enough real data yet
    if PLACEHOLDER in learnings and learnings.count("- ") < 2:
        print(f"  [{client_dir_name}] Not enough data to consolidate - skipped")
        return False

    log_content = read_file(log_path) or ""
    sections_str = "\n".join(f"- {s}" for s in SECTIONS)

    prompt = f"""You are the memory-consolidation script of an agency's AI system.
You receive one client's learnings.md and its log.md session journal.
Your job: return the CONSOLIDATED, cleaned version of learnings.md.

Client: {client_dir_name}
Date: {TODAY}

CURRENT LEARNINGS.MD:
{learnings}

LOG.MD (recent session summaries):
{log_content[-8000:] if log_content else "None."}

Consolidation tasks:
1. DEDUPLICATION: if two entries say the same thing, keep the more detailed/recent one VERBATIM - never merge into a shorter paraphrase
2. CONFLICT RESOLUTION: if two entries conflict, use log.md to decide which is newer/correct
3. IMPLICIT LEARNINGS: pull EVERY genuine, durable learning out of log.md that learnings does not yet contain. No count limit, but a STRICT gate:
   - It is a learning ONLY if: (a) durable (not a one-off event), (b) actionable, (c) generalizes above a single day's number.
   - NOT a learning (skip it): a one-off event, a raw daily metric with no takeaway, a rewording of an existing entry, speculation.
   - GROUNDING REQUIRED: only write it down if a concrete log.md entry (date/event) supports it. With no concrete log evidence, do NOT write it.
   - If there is no genuine learning at all: add nothing.
4. STRUCTURE: keep the {len(SECTIONS)} sections. NO per-section entry cap - keep every genuinely useful entry. If the file grows past ~500 lines, prioritize more aggressive dedup/merge to compress (but do NOT drop content just for size).
5. FORMAT: each entry prefixed with "- ", with a date if relevant

Sections:
{sections_str}

IMPORTANT RULES:
- Write ALL content in {OUTPUT_LANGUAGE} - NEVER translate an existing entry and NEVER add a translated duplicate of one; the file must stay monolingual
- EXISTING entries are either kept CHARACTER-FOR-CHARACTER or dropped as exact duplicates of a more detailed entry - never shorten, summarize or reword them. Concrete facts (file paths, IDs, version numbers, dates, names, commands, "tell X" notes) must survive verbatim
- Return only the learnings.md content, nothing else
- Keep the header and the footer (the "{FOOTER_PREFIX.lstrip('_')}" line)
- If a section has no data, keep the "{PLACEHOLDER}" placeholder
- Agency-general: PPC, SEO, creative, email, strategy, pricing all belong here
- EVERGREEN sections ({", ".join(f'"{s}"' for s in EVERGREEN_SECTIONS)}): merge only TRUE duplicates, NEVER drop a unique learning
- The footer line should be: {FOOTER_PREFIX.lstrip('_')}: {TODAY} | Session: weekly-consolidation
- NEVER delete a genuinely useful entry just because it is old"""

    client_api = anthropic.Anthropic()

    try:
        # Streaming is required at this max_tokens: the SDK cuts non-streaming
        # requests at ~10 minutes, and a large learnings.md generates longer
        # (observed: the biggest file died with a network timeout, not truncation).
        with client_api.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=CONSOLIDATE_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            response = stream.get_final_message()
    except Exception as e:
        print(f"  [{client_dir_name}] API error: {e}")
        _audit_skip(client_dir_name, f"API error: {e}")
        return False

    if response.stop_reason == "max_tokens":
        print(f"  [{client_dir_name}] TRUNCATED output (max_tokens={CONSOLIDATE_MAX_TOKENS} hit) - write skipped, original kept")
        _audit_skip(client_dir_name, f"truncated at max_tokens={CONSOLIDATE_MAX_TOKENS}")
        return False

    consolidated = response.content[0].text.strip()

    # Deterministic rebuild: fixed schema, missing/empty section -> original fallback.
    # protected= : in protected sections a dropped unique bullet is re-injected (weekly lossless).
    # The next-briefing section (if this world has it in client files) is a hand-curated
    # handoff - verbatim, same as the system file.
    consolidated = rebuild_learnings(consolidated, learnings, SECTIONS, TODAY,
                                     verbatim=(NEXT_BRIEFING_HEADING,),
                                     protected=PROTECTED_SECTIONS)

    # Language guard: a mis-set output_language makes the model TRANSLATE the file
    # (observed in production: full English rewrite / bilingual duplication) - skip.
    drifted, rb, ra = _language_drifted(learnings, consolidated)
    if drifted:
        print(f"  [{client_dir_name}] LANGUAGE DRIFT (non-ASCII letters {rb:.1%} -> {ra:.1%}) - "
              f"write skipped, original kept. Check world.json output_language!")
        _audit_skip(client_dir_name, f"language drift {rb:.1%}->{ra:.1%} (check output_language)")
        return False

    if dry_run:
        print(f"\n  [{client_dir_name}] DRY RUN - consolidated output:")
        print("-" * 60)
        print(consolidated[:2000])
        if len(consolidated) > 2000:
            print(f"  ... ({len(consolidated)} chars total)")
        print("-" * 60)
        return True

    # Backup of the old version (pre-consolidation snapshot)
    backup_path = client_path / "memory" / "archive" / "backup" / f"learnings-backup-{TODAY}.md"
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    if not backup_path.exists():
        backup_path.write_text(learnings, encoding="utf-8")

    # Weekly run = LOSSLESS: no archiving. Protected sections guarantee preservation
    # (rebuild_learnings protected=). Archiving (superseded + stale) goes through the
    # Phase 3 sweep-candidate path with human approval.
    learnings_path.write_text(consolidated, encoding="utf-8")
    _audit_consolidation(client_dir_name, len(learnings), len(consolidated), backup_path)
    print(f"  [{client_dir_name}] OK - consolidated ({len(learnings)} -> {len(consolidated)} chars, lossless)")
    return True


def apply_briefing_retention(text, archive_path, dry_run=False):
    """#6: trim the next-briefing section to the newest BRIEFING_KEEP_CHECKPOINTS blocks
    (blocks are newest-first by convention); swept blocks are APPENDED to the archive
    file, never deleted. Intro lines before the first checkpoint marker are kept.
    No-op when retention is off (0), the section is missing, or there is nothing over
    the limit. Runs AFTER rebuild_learnings, so it operates on the verbatim-preserved
    section."""
    if BRIEFING_KEEP_CHECKPOINTS <= 0:
        return text
    lines = text.split("\n")
    try:
        h = next(i for i, l in enumerate(lines)
                 if l.startswith("## ") and l[3:].strip() == NEXT_BRIEFING_HEADING)
    except StopIteration:
        return text
    end = h + 1
    while end < len(lines) and lines[end].strip() != "---" and not lines[end].startswith("## "):
        end += 1
    body = "\n".join(lines[h + 1:end])
    starts = [m.start() for m in re.finditer(BRIEFING_BLOCK_REGEX, body, re.M)]
    if len(starts) <= BRIEFING_KEEP_CHECKPOINTS:
        return text
    cut = starts[BRIEFING_KEEP_CHECKPOINTS]
    kept = body[:cut].rstrip("\n")
    swept = body[cut:].strip()
    n_swept = len(starts) - BRIEFING_KEEP_CHECKPOINTS
    if dry_run:
        print(f"  [briefing-retention] dry-run: would sweep {n_swept} old checkpoint block(s) to {archive_path.name}")
        return text
    if swept:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with open(archive_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n## Swept from the next-briefing section | {TODAY}\n\n{swept}\n")
    print(f"  [briefing-retention] {n_swept} old checkpoint block(s) swept to {archive_path.name} "
          f"(kept: newest {BRIEFING_KEEP_CHECKPOINTS})")
    return "\n".join(lines[:h + 1] + kept.split("\n") + [""] + lines[end:])


def consolidate_system(dry_run=False):
    """Consolidate system/memory/learnings.md against the CHANGELOG.md."""
    learnings_path = REPO_ROOT / "system" / "memory" / "learnings.md"
    changelog_path = REPO_ROOT / "system" / "logs" / "CHANGELOG.md"

    learnings = read_file(learnings_path)
    if not learnings:
        print(f"  [system] learnings.md missing - skipped")
        return False

    if PLACEHOLDER in learnings and learnings.count("- ") < 2:
        print(f"  [system] Not enough data - skipped")
        return False

    log_content = read_file(changelog_path) or ""
    sections_str = "\n".join(f"- {s}" for s in SYSTEM_SECTIONS)

    prompt = f"""You are the memory-consolidation script of an agency's AI system.
You receive the system-development learnings (system/memory/learnings.md) and the CHANGELOG.md.
Your job: return the CONSOLIDATED, cleaned version of learnings.md.

Date: {TODAY}

CURRENT LEARNINGS.MD:
{learnings}

CHANGELOG.MD (recent changes, newest first):
{log_content[:8000] if log_content else "None."}

Consolidation tasks:
1. DEDUPLICATION: if two entries say the same thing, keep the more detailed/recent one VERBATIM - never merge into a shorter paraphrase
2. CONFLICT RESOLUTION: use the CHANGELOG to decide which is newer/correct
3. IMPLICIT LEARNINGS: pull EVERY genuine, durable learning out of the CHANGELOG that learnings does not yet contain. No count limit, but a STRICT gate:
   - It is a learning ONLY if: (a) durable (not a one-off event), (b) actionable, (c) generalizes above a single change.
   - NOT a learning (skip it): a one-off event, a raw commit description with no takeaway, a rewording of an existing entry, speculation.
   - GROUNDING REQUIRED: only write it down if a concrete CHANGELOG entry (date/tag) supports it. With no concrete evidence, do NOT write it.
   - If there is no genuine learning at all: add nothing.
4. STRUCTURE: keep the {len(SYSTEM_SECTIONS)} sections. NO per-section entry cap - keep every genuinely useful entry. If the file grows past ~500 lines, prioritize more aggressive dedup/merge to compress (but do NOT drop content just for size).
5. FORMAT: each entry prefixed with "- ", with a date if relevant

Sections:
{sections_str}

IMPORTANT RULES:
- Write ALL content in {OUTPUT_LANGUAGE} - NEVER translate an existing entry and NEVER add a translated duplicate of one; the file must stay monolingual
- EXISTING entries are either kept CHARACTER-FOR-CHARACTER or dropped as exact duplicates of a more detailed entry - never shorten, summarize or reword them. Concrete facts (file paths, IDs, version numbers, dates, names, commands, "tell X" notes) must survive verbatim
- Return only the learnings.md content, nothing else
- Keep the header and the footer (the "{FOOTER_PREFIX.lstrip('_')}" line)
- If a section has no data, keep the "{PLACEHOLDER}" placeholder
- Do NOT modify the "{NEXT_BRIEFING_HEADING}" section - it is the live hand-curated handoff; leave it empty, the script preserves it verbatim
- EVERGREEN sections ({", ".join(f'"{s}"' for s in PROTECTED_SYSTEM_SECTIONS)}): merge only TRUE duplicates, NEVER drop a unique learning
- The footer line should be: {FOOTER_PREFIX.lstrip('_')}: {TODAY} | Session: weekly-consolidation
- NEVER delete a genuinely useful entry just because it is old"""

    client_api = anthropic.Anthropic()
    try:
        # Streaming required - see consolidate_client
        with client_api.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=CONSOLIDATE_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            response = stream.get_final_message()
    except Exception as e:
        print(f"  [system] API error: {e}")
        _audit_skip("system", f"API error: {e}")
        return False

    if response.stop_reason == "max_tokens":
        print(f"  [system] TRUNCATED output (max_tokens={CONSOLIDATE_MAX_TOKENS} hit) - write skipped, original kept")
        _audit_skip("system", f"truncated at max_tokens={CONSOLIDATE_MAX_TOKENS}")
        return False

    consolidated = response.content[0].text.strip()

    # Deterministic rebuild; "Next session briefing" verbatim from the original
    # (live handoff injected by the SessionStart hook - NOT consolidated).
    consolidated = rebuild_learnings(
        consolidated, learnings, SYSTEM_SECTIONS, TODAY,
        verbatim=(NEXT_BRIEFING_HEADING,),
        protected=PROTECTED_SYSTEM_SECTIONS,
    )

    # Language guard (see consolidate_client)
    drifted, rb, ra = _language_drifted(learnings, consolidated)
    if drifted:
        print(f"  [system] LANGUAGE DRIFT (non-ASCII letters {rb:.1%} -> {ra:.1%}) - "
              f"write skipped, original kept. Check world.json output_language!")
        _audit_skip("system", f"language drift {rb:.1%}->{ra:.1%} (check output_language)")
        return False

    # Briefing retention (#6): verbatim protects the section from the LLM; this trims
    # it deterministically so it does not grow without bound.
    consolidated = apply_briefing_retention(
        consolidated,
        REPO_ROOT / "system" / "memory" / "archive" / "briefing-archive.md",
        dry_run=dry_run,
    )

    if dry_run:
        print(f"\n  [system] DRY RUN - consolidated output:")
        print("-" * 60)
        print(consolidated[:2000])
        print("-" * 60)
        return True

    backup_path = REPO_ROOT / "system" / "memory" / "archive" / "backup" / f"learnings-backup-{TODAY}.md"
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    if not backup_path.exists():
        backup_path.write_text(learnings, encoding="utf-8")

    # Weekly run = LOSSLESS (see consolidate_client). Archiving -> Phase 3 sweep.
    learnings_path.write_text(consolidated, encoding="utf-8")
    _audit_consolidation("system", len(learnings), len(consolidated), backup_path)
    print(f"  [system] OK - consolidated ({len(learnings)} -> {len(consolidated)} chars, lossless)")
    return True


def _parse_candidate_bullets(body):
    """Clean '- ' bullets from an LLM response (NO-CANDIDATES sentinel -> empty)."""
    first = body.upper().split("\n")[0]
    if "NO CANDIDATE" in first or "NO CROSS-CLIENT" in first or body.strip().upper().startswith("NO "):
        return []
    out = []
    for l in body.splitlines():
        s = l.strip()
        if s.startswith("- ") and len(s) > 4:
            out.append(s)
    return out


def detect_promotion_candidates(dry_run=False):
    """One pass over all learnings: durable, GENERAL rule candidates.
    Returns list[dict] {type,scope,text} - does NOT write a file (sync_candidates handles it)."""
    parts = []
    sys_l = read_file(REPO_ROOT / "system" / "memory" / "learnings.md")
    if sys_l:
        parts.append(f"### [system]\n{sys_l[:2500]}")
    for c in sorted(get_clients()):
        cl = read_file(CLIENTS_DIR / c / "memory" / "learnings.md")
        if cl and cl.count("- ") >= 1 and not (cl.count("- ") < 2 and PLACEHOLDER in cl):
            parts.append(f"### [{c}]\n{cl[:1500]}")
    if not parts:
        print("  [promotion] Not enough learnings - skipped")
        return []

    combined = "\n\n".join(parts)
    prompt = f"""You are the memory-promotion analyzer of an agency's AI system.
You receive all accumulated learnings (system + clients). Your job: surface the DURABLE,
GENERAL rule candidates that deserve to become a permanent instruction.

Date: {TODAY}

ACCUMULATED LEARNINGS:
{combined}

What makes a GOOD promotion candidate:
- A general behavioral/process rule (NOT a single-client fact, NOT a one-off event)
- Recurs in several places/sessions, or is foundational (affects everything)
- Concrete and actionable

Target layer (where it would live):
- "global memory" - the user's working style, general process
- "agent CLAUDE.md (which)" - a domain craft rule (loaded only on routing)
- "project CLAUDE.md" - a rule affecting the whole coordinator

Rules:
- ONLY high-confidence candidates, MAX 5. Fewer is better.
- A client-specific fact, campaign data, or one-off decision -> NOT a candidate.
- Concise.
- OUTPUT: ONLY the candidate bullets, one per line, no other text (no intro, no outro).
  Format each bullet exactly like this:
  - **[target layer]** the rule in one sentence — _why it is worth promoting_
- If there is no real candidate -> exactly this: NO CANDIDATES"""

    try:
        resp = anthropic.Anthropic().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        print(f"  [promotion] API error: {e}")
        return []

    bullets = _parse_candidate_bullets(resp.content[0].text.strip())
    if dry_run:
        print(f"\n  [promotion] DRY RUN - {len(bullets)} candidates:")
        for b in bullets:
            print(f"    {b}")
    return [{"type": "promotion", "scope": "global", "text": b} for b in bullets]


def detect_cross_client_patterns(dry_run=False):
    """One pass over all client learnings: patterns recurring across MULTIPLE clients.
    Siloed client folders structurally cannot see cross-client connections.
    Writes abstract tactical patterns (what works / what failed / what recurs) with
    client evidence. Internal strategic memory - NOT placed in a client folder, no client-data mixing."""
    parts = []
    for c in sorted(get_clients()):
        cl = read_file(CLIENTS_DIR / c / "memory" / "learnings.md")
        if cl and cl.count("- ") >= 2 and PLACEHOLDER not in cl[:200]:
            parts.append(f"### [{c}]\n{cl[:1800]}")
    if len(parts) < 2:
        print("  [cross-client] <2 clients have real learnings - skipped")
        return False

    combined = "\n\n".join(parts)
    prompt = f"""You are the cross-client pattern analyzer of an agency's AI system.
You receive all active clients' learnings. Your job: surface patterns that recur across
MULTIPLE clients - the kind you cannot see while working on a single client.

Date: {TODAY}

CLIENT LEARNINGS:
{combined}

What to look for (only what appears in AT LEAST 2 clients):
- A tactic that worked in several places (bid strategy, campaign structure, creative approach)
- A recurring problem / pitfall (tracking, compliance, learning reset, budget pacing)
- A vertical-specific pattern (e-comm vs services vs restaurant)
- A platform-level learning (Google/Meta) that spans clients

Format per pattern:
- **[pattern in one sentence]** — _evidence: which clients (name), and what it means in practice_

Rules:
- ONLY real patterns appearing in 2+ clients. Fewer, high-confidence is better. MAX 8.
- A single-client fact (account ID, specific budget) is NOT a pattern.
- Abstract tactical level - do not copy raw client data.
- Concise.
- If there is no real cross-client pattern -> exactly this: NO CROSS-CLIENT PATTERN"""

    try:
        resp = anthropic.Anthropic().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        print(f"  [cross-client] API error: {e}")
        return False

    body = resp.content[0].text.strip()

    if dry_run:
        print(f"\n  [cross-client] DRY RUN - patterns:")
        print("-" * 60)
        print(body[:1500])
        print("-" * 60)
        return True

    content = (f"# Cross-client patterns\n\n"
               f"_Regenerated weekly by consolidate.py. Recurring tactics, pitfalls, and "
               f"vertical patterns across multiple clients - what the siloed client folders "
               f"cannot see. Your agency's internal strategic memory, NOT a client data store._\n\n"
               f"_Last run: {TODAY} | candidates-state.json is the source of truth - this file is a snapshot; after accept/reject refresh with `consolidate.py --reviews-only`_\n\n---\n\n{body}\n")
    CROSS_CLIENT_PATH.write_text(content, encoding="utf-8")
    print(f"  [cross-client] OK - patterns -> {CROSS_CLIENT_PATH.relative_to(REPO_ROOT)}")
    return True


def _strip_evergreen(text):
    """Remove the sweep-exempt (EVERGREEN) section bodies so we never propose archiving from them."""
    preamble, secs = split_sections(text)
    keep = [f"## {name}\n{body}" for name, body in secs.items() if name not in EVERGREEN_SECTIONS]
    return preamble + "\n\n" + "\n\n".join(keep)


def detect_sweep_candidates(dry_run=False):
    """Sweep candidates: superseded (a newer entry overrides the same entity) + stale
    (a finished campaign / one-off event). Per source (clients + system). Evergreen
    sections skipped. ONLY detects - never archives. Returns list[dict] {type,scope,text}."""
    sources = [("system", REPO_ROOT / "system" / "memory" / "learnings.md")]
    for c in sorted(get_clients()):
        sources.append((c, CLIENTS_DIR / c / "memory" / "learnings.md"))

    detected = []
    for scope, path in sources:
        raw = read_file(path)
        if not raw or raw.count("- ") < 3:
            continue
        body = _strip_evergreen(raw)[:4000]
        prompt = f"""You are the memory-maintenance pass of an agency's AI system. You receive one source's operational learnings.
Your job: surface ARCHIVABLE (sweep) candidates. ONLY two reasons count:

(a) SUPERSEDED: there is a NEWER entry about the same entity (campaign/setting/decision) that overrides the old one - the old one is no longer valid.
(b) STALE: a finished one-off event, a closed/ended campaign, or a learning proven invalid.

BI-TEMPORAL SIGNAL: if an entry carries an `[as of: YYYY-MM-DD]` marker and that date is OLD (months ago) AND it is about a finished/closed thing, it is a STRONGER stale candidate. The "as of" date = when it was true (not when recorded); an old "as of" date on a passing event = outdated. A durable baseline/preference with an old date is NOT stale.

Date: {TODAY}
Source: [{scope}]

LEARNINGS:
{body}

Rules:
- ONLY a sure candidate. If it is uncertain whether it is still relevant -> do NOT flag it. Fewer is better.
- A durable/evergreen learning, baseline, ROAS history, or working craft rule -> NEVER flag.
- OUTPUT: ONLY the candidate bullets, one per line, no other text.
  Format each bullet exactly like this (quote the entry to archive):
  - «short quote of the entry to archive» — [superseded|stale] _reason in one sentence_
- If there is no candidate -> exactly this: NO CANDIDATES"""
        try:
            resp = anthropic.Anthropic().messages.create(
                model="claude-sonnet-4-6",
                max_tokens=900,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            print(f"  [sweep] API error ({scope}): {e}")
            continue
        bullets = _parse_candidate_bullets(resp.content[0].text.strip())
        for b in bullets:
            detected.append({"type": "sweep", "scope": scope, "text": b})

    if dry_run:
        print(f"\n  [sweep] DRY RUN - {len(detected)} candidates:")
        for d in detected:
            print(f"    [{d['scope']}] {d['text']}")
    return detected


def _client_curated_files(client):
    """A client's existing curated per-area campaign files: [(area, Path), ...].
    Convention: wiki/campaigns-<area>.md (e.g. campaigns-google.md). Optional - a client
    with none simply gets no wiki-promotion candidates (Phase 5 no-ops for it)."""
    wiki = CLIENTS_DIR / client / "wiki"
    if not wiki.is_dir():
        return []
    return [(p.stem.replace(CURATED_PREFIX, ""), p) for p in sorted(wiki.glob(CURATED_GLOB))]


def detect_wiki_promotion_candidates(dry_run=False):
    """Wiki-promotion candidates (Phase 5): a durable ACCOUNT FACT in a client's operational
    learnings.md that belongs in a curated campaigns-<area>.md but is not there yet. SEPARATE
    stream from promotion (a GENERAL rule -> CLAUDE.md; an account fact -> wiki). Runs only for
    clients that keep curated per-area files; gets the curated content so it never proposes a
    duplicate. ONLY detects, never writes to the wiki. Returns list[dict] {type:'wiki-promotion',scope:client,text}."""
    detected = []
    for c in sorted(get_clients()):
        curated_files = _client_curated_files(c)
        if not curated_files:
            continue  # no curated per-area file -> nowhere to promote to
        cl = read_file(CLIENTS_DIR / c / "memory" / "learnings.md")
        if not cl or cl.count("- ") < 3 or any(m in cl[:200] for m in _PLACEHOLDER_MARKERS):
            continue
        wiki_blob = "\n\n".join(
            f"### {CURATED_PREFIX}{area}.md (current content)\n{(read_file(path) or '')[:4000]}"
            for area, path in curated_files
        )
        targets = ", ".join(f"{CURATED_PREFIX}{area}.md" for area, _ in curated_files)
        prompt = f"""You are the memory-curator pass of an agency's AI system. You receive a client's OPERATIONAL
learnings.md (auto-accumulated, updated across sessions) and the current content of that client's CURATED
per-area campaign files. Your job: surface the DURABLE ACCOUNT FACTS in the operational memory that belong
in a curated campaigns-<area>.md but are NOT there yet.

Date: {TODAY}
Client: {c}
Target files (you may ONLY propose into these): {targets}

CURATED WIKI (current content - NEVER propose anything it already contains):
{wiki_blob}

OPERATIONAL LEARNINGS (the source):
{cl[:3000]}

What makes a GOOD wiki-promotion candidate:
- A durable, account-specific fact/tactic/baseline that holds for this client long-term
  (what works / what structurally failed, a performance baseline, a historical reference, a durable setting/constraint)
- Belongs in the curated file whose area matches the learning's domain
- NOT already in the curated wiki

What is NOT a candidate:
- A general behavioral/process rule (that is the other stream -> CLAUDE.md, never here)
- A one-off / finished event, a dated operational step (that is sweep)
- A client communication preference
- Anything the curated wiki ALREADY contains

Rules: ONLY high-confidence candidates, max 5/client. Fewer is better. Concise.
OUTPUT: ONLY the candidate bullets, one per line, no other text. Format exactly:
- «short quote of the fact to promote» → campaigns-<area>.md _why it is durable, which section_
If there is no real candidate -> exactly this: NO CANDIDATES"""
        try:
            resp = anthropic.Anthropic().messages.create(
                model="claude-sonnet-4-6",
                max_tokens=900,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            print(f"  [wiki-promotion] API error ({c}): {e}")
            continue
        bullets = _parse_candidate_bullets(resp.content[0].text.strip())
        for b in bullets:
            detected.append({"type": "wiki-promotion", "scope": c, "text": b})

    if dry_run:
        print(f"\n  [wiki-promotion] DRY RUN - {len(detected)} candidates:")
        for d in detected:
            print(f"    [{d['scope']}] {d['text']}")
    return detected


# --- Candidate state tracking (candidates-state.json) ---
# Goal: aging (first_seen) + 'do not re-offer a rejected one'. Identity-match uses the
# existing token-overlap engine (symmetric containment) - reword-tolerant, no new mechanism.

def load_state():
    if CANDIDATES_STATE_PATH.exists():
        try:
            return json.loads(CANDIDATES_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"next_id": 1, "candidates": []}


def save_state(state):
    CANDIDATES_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _same_candidate(a, b, thresh=0.6):
    """Symmetric identity match: containment of either token set into the other >= thresh.
    Reword-tolerant - a widening/narrowing rewrite does not break identity (hence not the one-way _survives)."""
    if not a or not b:
        return False
    inter = len(a & b)
    return inter / len(a) >= thresh or inter / len(b) >= thresh


def _find_match(detected, candidates):
    """Existing candidate that is the same as the detected one (same type+scope, symmetric token overlap)."""
    dtok = _tokens(detected["text"])
    for c in candidates:
        if c.get("type") == detected["type"] and c.get("scope") == detected["scope"] and _same_candidate(dtok, _tokens(c.get("text", ""))):
            return c
    return None


def sync_candidates(detected, state):
    """Merge freshly detected candidates into the state:
    - existing (any status) match -> last_seen updated, first_seen/status kept (rejected does NOT return to open)
    - new -> id, first_seen=today, status=open
    Open candidates not re-detected this run are kept (waiting for review; LLM non-determinism does not drop them).
    obs_type (observation taxonomy: decision/gotcha/result/rule/learning) is carried when the
    extractor provides it - it speeds up review and can steer where an accept lands."""
    for d in detected:
        m = _find_match(d, state["candidates"])
        if m:
            m["last_seen"] = TODAY
            m["text"] = d["text"]  # freshest wording, but identity/status stay
            if d.get("obs_type"):
                m["obs_type"] = d["obs_type"]
        else:
            entry = {
                "id": state["next_id"], "type": d["type"], "scope": d["scope"],
                "text": d["text"], "first_seen": TODAY, "last_seen": TODAY, "status": "open",
            }
            if d.get("obs_type"):
                entry["obs_type"] = d["obs_type"]
            state["candidates"].append(entry)
            state["next_id"] += 1
    return state


def _weeks_since(date_str):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return (datetime.now() - d).days // 7
    except Exception:
        return 0


def write_review_files(state):
    """Write the open candidates into the review .md files (promotion / sweep / wiki-promotion), with id + age."""
    opens = [c for c in state.get("candidates", []) if c.get("status") == "open"]
    promo = [c for c in opens if c.get("type") == "promotion"]
    sweep = [c for c in opens if c.get("type") == "sweep"]
    wiki = [c for c in opens if c.get("type") == "wiki-promotion"]

    def fmt(c):
        w = _weeks_since(c.get("first_seen", ""))
        age = "this week" if w == 0 else f"{w}w waiting"
        obs = f" [{c['obs_type']}]" if c.get("obs_type") else ""
        return f"- `#{c.get('id', '?')}` [{c.get('scope', '?')}]{obs} ({age}) {c.get('text', '')}"

    pc = (f"# Promotion candidates\n\n"
          f"_Regenerated weekly. General rule candidates -> CLAUDE.md / global memory. "
          f"You decide; the auto-pipeline NEVER writes to a hand-curated CLAUDE.md. "
          f"Accept/reject by the candidate's `#id`._\n\n_Last run: {TODAY} | candidates-state.json is the source of truth - this file is a snapshot; after accept/reject refresh with `consolidate.py --reviews-only`_\n\n---\n\n"
          + ("\n".join(fmt(c) for c in promo) if promo else "_No open promotion candidates._") + "\n")
    PROMOTION_CANDIDATES_PATH.write_text(pc, encoding="utf-8")

    sc = (f"# Sweep candidates (for archiving)\n\n"
          f"_Regenerated weekly. Superseded or stale entries - proposed for archiving. "
          f"Evergreen sections ({', '.join(EVERGREEN_SECTIONS)}) are exempt. "
          f"Archived ONLY with your approval. Accept/reject by the candidate's `#id`._\n\n"
          f"_Last run: {TODAY} | candidates-state.json is the source of truth - this file is a snapshot; after accept/reject refresh with `consolidate.py --reviews-only`_\n\n---\n\n"
          + ("\n".join(fmt(c) for c in sweep) if sweep else "_No open sweep candidates._") + "\n")
    SWEEP_CANDIDATES_PATH.write_text(sc, encoding="utf-8")

    wc = (f"# Wiki-promotion candidates (account fact -> campaigns-<area>.md)\n\n"
          f"_Regenerated weekly. Durable account facts from operational learnings.md that belong in a "
          f"curated per-area campaign file (the second layer: operational -> curated). SEPARATE from promotion "
          f"candidates (a GENERAL rule -> CLAUDE.md; an account fact -> wiki). The auto-pipeline NEVER writes to "
          f"the curated wiki - ONLY with your approval. Accept/reject by the candidate's `#id`._\n\n"
          f"_Last run: {TODAY} | candidates-state.json is the source of truth - this file is a snapshot; after accept/reject refresh with `consolidate.py --reviews-only`_\n\n---\n\n"
          + ("\n".join(fmt(c) for c in wiki) if wiki else "_No open wiki-promotion candidates._") + "\n")
    WIKI_PROMOTION_CANDIDATES_PATH.write_text(wc, encoding="utf-8")

    # Cadence: tool-craft + client-learning review files (new candidate types)
    craft = [c for c in opens if c.get("type") == "tool-craft"]
    learn = [c for c in opens if c.get("type") == "client-learning"]
    tc = (f"# Tool-craft candidates (system-level, enforcement)\n\n"
          f"_Regenerated weekly. Tool-usage craft lessons from transcript mining. Once approved, "
          f"add to `tool-craft.md` (WARN gate / advisory). Accept/reject by the candidate's `#id`._\n\n"
          f"_Last run: {TODAY} | candidates-state.json is the source of truth - this file is a snapshot; after accept/reject refresh with `consolidate.py --reviews-only`_\n\n---\n\n"
          + ("\n".join(fmt(c) for c in craft) if craft else "_No open tool-craft candidates._") + "\n")
    (REPO_ROOT / "system" / "memory" / "tool-craft-candidates.md").write_text(tc, encoding="utf-8")
    cl = (f"# Client-learning candidates (cheap-Dreaming)\n\n"
          f"_Regenerated weekly. Client learnings mined from raw transcripts (MEDIUM gate, no-mixing). "
          f"Once approved, add to the client's learnings.md / wiki. Accept/reject by the candidate's `#id`._\n\n"
          f"_Last run: {TODAY} | candidates-state.json is the source of truth - this file is a snapshot; after accept/reject refresh with `consolidate.py --reviews-only`_\n\n---\n\n"
          + ("\n".join(fmt(c) for c in learn) if learn else "_No open client-learning candidates._") + "\n")
    (REPO_ROOT / "system" / "memory" / "client-learning-candidates.md").write_text(cl, encoding="utf-8")

    print(f"  [candidates] open: {len(promo)} promotion + {len(sweep)} sweep + {len(wiki)} wiki-promotion "
          f"+ {len(craft)} tool-craft + {len(learn)} client-learning -> review files + state")


NEW_EXTRACTORS_STATUS = {"ok": True, "error": None}


def detect_new_extractors(dry_run=False):
    """Cadence: tool-craft (craft_judge) + client-learning (dream_extractor) candidates from
    transcript mining. FAULT-TOLERANT: if anything fails (API/transcript/import), the existing
    consolidation does NOT break - returns [] and moves on; the failure is recorded in
    NEW_EXTRACTORS_STATUS (-> state last_run -> nudge warning) so it is not silent.
    The dream window is 10 days (weekly cadence + overlap): one missed weekly run no longer
    loses that week's transcript learnings for good. dry_run: no API calls (candidates()
    would be costly), just notes it would run."""
    if dry_run:
        print("  [new-extractors] dry-run: skipped (avoid API cost)")
        return []
    try:
        import transcript_lib
        import craft_judge
        import dream_extractor
    except Exception as e:
        print(f"  [new-extractors] import error, skipped: {e}")
        NEW_EXTRACTORS_STATUS.update(ok=False, error=f"import: {e}")
        return []
    try:
        tdir = transcript_lib.transcript_dir(REPO_ROOT)  # explicit world-root (cron cwd != root)
        craft = craft_judge.candidates(tdir)
        learn = dream_extractor.candidates(tdir, days=10)
        # cross-stream dedup: a client-learning that is really a tool-craft -> system-level (dropped here)
        ctok = [_tokens(c["text"]) for c in craft]
        learn = [l for l in learn if not any(_same_candidate(_tokens(l["text"]), ct) for ct in ctok)]
        print(f"  [new-extractors] {len(craft)} tool-craft + {len(learn)} client-learning")
        return craft + learn
    except Exception as e:
        print(f"  [new-extractors] run error, skipped: {e}")
        NEW_EXTRACTORS_STATUS.update(ok=False, error=f"run: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(description="Learnings consolidation across all clients + system")
    parser.add_argument("--dry-run", action="store_true", help="Show only, no writes")
    parser.add_argument("--client", help="Single client only (e.g. acme-corp)")
    parser.add_argument("--system-only", action="store_true", help="Only system/memory/learnings.md")
    parser.add_argument("--cross-client-only", action="store_true", help="Only the cross-client pattern analysis")
    parser.add_argument("--reviews-only", action="store_true",
                        help="Regenerate the review .md files from candidates-state.json (no API; run after accept/reject)")
    parser.add_argument("--world", help="World root (user data). Default: AGENCY_WORLD_ROOT / CLAUDE_PROJECT_DIR / cwd")
    args = parser.parse_args()

    configure(resolve_world_root(args.world))

    if args.reviews_only:
        write_review_files(load_state())
        return

    if args.cross_client_only:
        print(f"\nCross-client pattern analysis | {TODAY}")
        detect_cross_client_patterns(dry_run=args.dry_run)
        return

    if args.dry_run:
        print(f"DRY RUN mode - no file writes")

    success = 0

    if not args.client:
        print(f"\nSystem consolidation | {TODAY}")
        if consolidate_system(dry_run=args.dry_run):
            success += 1

    if args.system_only:
        print(f"\nDone: system/memory/learnings.md consolidated" if success else "\nDone: no change")
        return

    clients = [args.client] if args.client else get_clients()
    if not clients:
        print("No client folders found.")
        sys.exit(1)

    print(f"\nClient consolidation: {len(clients)} clients | {TODAY}\n")
    client_success = 0
    for client in sorted(clients):
        result = consolidate_client(client, dry_run=args.dry_run)
        if result:
            client_success += 1

    # Candidate detection (promotion + sweep + wiki-promotion) + cross-client: only on a full run
    if not args.client:
        print(f"\nCandidate detection (promotion + sweep + wiki-promotion) | {TODAY}")
        detected = (detect_promotion_candidates(dry_run=args.dry_run)
                    + detect_sweep_candidates(dry_run=args.dry_run)
                    + detect_wiki_promotion_candidates(dry_run=args.dry_run)
                    + detect_new_extractors(dry_run=args.dry_run))
        if not args.dry_run:
            _ensure_tool_craft_scaffold()  # self-bootstrap for 0.1.x -> 0.2.0 upgrades
            state = sync_candidates(detected, load_state())
            # Run health record -> candidates_nudge warns at session start if the
            # Dreaming branch failed (otherwise the failure is silent)
            state["last_run"] = {"date": TODAY,
                                 "new_extractors_ok": NEW_EXTRACTORS_STATUS["ok"],
                                 "error": NEW_EXTRACTORS_STATUS["error"]}
            save_state(state)
            write_review_files(state)
        print(f"\nCross-client pattern analysis | {TODAY}")
        detect_cross_client_patterns(dry_run=args.dry_run)

    print(f"\nDone: system={'OK' if success else 'skip'} | clients: {client_success}/{len(clients)}")
    if SKIPPED:
        listing = ", ".join(f"{s} ({r})" for s, r in SKIPPED)
        print(f"⚠️ {len(SKIPPED)} entity SKIPPED this run: {listing} - see consolidation-audit.md")


if __name__ == "__main__":
    main()
