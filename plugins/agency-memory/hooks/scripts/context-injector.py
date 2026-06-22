#!/usr/bin/env python3
"""
context-injector.py
Purpose: UserPromptSubmit hook - two jobs:
  1. Injects the contents of <world>/system/memory/context-load-order.md before
     every prompt.
  2. Detects compact commands and injects compact-protocol.md.
Trigger: UserPromptSubmit
Changelog:
  2026-05-27 - Initial version (context-load-order injection)
  2026-05-27 - Compact detection added
  2026-05-31 - Extracted to agency-memory-kit; removed dead kgraph fallback line
  2026-06-03 - Plugin conversion: paths via agency_common world-root (not cwd)
"""

import json
import sys

# Windows / non-UTF-8 locales: emoji in stdout would crash (e.g. cp1250). Force UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
from agency_common import resolve_world_root  # noqa: E402

WORLD = resolve_world_root()
CONTEXT_LOAD_ORDER = WORLD / "system" / "memory" / "context-load-order.md"
COMPACT_PROTOCOL = WORLD / "system" / "memory" / "compact-protocol.md"

COMPACT_KEYWORDS = [
    "/compact",
    "compact",
    "compactalj",
    "compactálj",
]


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None


def main():
    user_message = ""
    try:
        data = json.load(sys.stdin)
        user_message = data.get("prompt", "").lower().strip()
    except Exception:
        pass  # If no stdin, context-load-order still shows

    # 1. Compact detection
    is_compact = any(kw in user_message for kw in COMPACT_KEYWORDS)
    if is_compact:
        protocol = read_file(COMPACT_PROTOCOL)
        if protocol:
            print(f"\n🔔 COMPACT TRIGGER DETECTED\n\n{protocol}\n")
        else:
            print("""
🔔 COMPACT TRIGGER DETECTED

Before the compact runs, save session memory:
1. clients/[client]/wiki/log.md       -> append session events with [tag]
2. clients/[client]/wiki/hot.md       -> update if focus changed
3. clients/[client]/memory/learnings.md -> append if there was a durable learning

THEN run the compact.
""")

    # 2. Context load order injection (always)
    content = read_file(CONTEXT_LOAD_ORDER)
    if content:
        print(f"\n📋 CONTEXT LOAD ORDER (system/memory/context-load-order.md)\n{content}\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
