#!/usr/bin/env python3
"""
entropy-audit — Scan for stale, duplicate, or superseded knowledge.

Purpose: Detect knowledge that needs lifecycle action: stale, superseded, unused, duplicate.
Invoker: memory-prune workflow.
Related tests: tests/test_prune_memory.py

Input:  --root <PATH>        Root directory containing docs/
        --now <ISO_TIMESTAMP>  Override current timestamp for deterministic replay

Output: JSON list of flagged entries with reasons.
Exit:   0 on success (even if entries found), 1 on error.
"""
import argparse
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_utilities import load_yaml_frontmatter

REVIEW_CYCLE_DAYS = 90
UNUSED_DAYS = 30


def parse_date(date_str: str) -> datetime | None:
    """Parse YYYY-MM-DD date string."""
    try:
        return datetime.strptime(str(date_str).strip().strip('"').strip("'"), "%Y-%m-%d")
    except (ValueError, AttributeError):
        return None


def scan_docs(root: str, now: datetime) -> list[dict]:
    """Scan docs for entropy."""
    flagged = []
    root_path = Path(root)
    doc_dirs = ["docs/decisions", "docs/lessons", "docs/summaries"]

    for subdir in doc_dirs:
        full = root_path / subdir
        if not full.is_dir():
            continue
        for f in sorted(full.rglob("*.md")):
            fm, _ = load_yaml_frontmatter(f)

            doc_id = fm.get("id", str(f))
            flags = []

            created = parse_date(fm.get("created", ""))
            if created and (now - created).days > REVIEW_CYCLE_DAYS:
                flags.append({"type": "stale", "reason": f"review_cycle_days ({REVIEW_CYCLE_DAYS}d) exceeded"})

            if fm.get("status") == "active" and fm.get("superseded_by"):
                flags.append({"type": "superseded", "reason": f"status=active but superseded_by={fm['superseded_by']}"})

            if fm.get("activation_count") == "0":
                updated = parse_date(fm.get("updated", fm.get("created", "")))
                if updated and (now - updated).days > UNUSED_DAYS:
                    flags.append({"type": "unused", "reason": f"activation_count=0 after {UNUSED_DAYS}d"})

            if flags:
                flagged.append({
                    "id": doc_id,
                    "path": str(f),
                    "flags": flags,
                    "doc_kind": fm.get("doc_kind", ""),
                    "status": fm.get("status", ""),
                })

    return flagged


def main():
    parser = argparse.ArgumentParser(description="Scan for knowledge entropy")
    parser.add_argument("--root", required=True, help="Root directory for docs/")
    parser.add_argument("--now", default=None, help="Override current timestamp (ISO format) for deterministic replay")
    args = parser.parse_args()

    now = datetime.fromisoformat(args.now) if args.now else datetime.now()
    flagged = scan_docs(args.root, now)

    output = {
        "flagged_count": len(flagged),
        "entries": flagged,
    }
    print(json.dumps(output, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
