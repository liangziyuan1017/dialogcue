#!/usr/bin/env python3
"""
discover-docs — Scan a repo root for durable memory documents.

Purpose: Discover all .md files under docs/decisions/, docs/lessons/, docs/summaries/.
Invoker: memory-bootstrap, memory-index, metadata-enforce workflows.
Related tests: tests/test_bootstrap_memory.py, tests/test_rebuild_index.py

Input:  --root <PATH>           Repo root directory
        --changed-since <TS>    (optional) Only return files modified since timestamp
        --all                   Return all docs (default)

Output: JSON list of file paths to stdout.
Exit:   0 on success, 1 on error.
"""
import argparse
import sys
import json
import os
from pathlib import Path
from datetime import datetime

DOC_SUBDIRS = ["docs/decisions", "docs/lessons", "docs/summaries"]


def discover_docs(root: Path, changed_since: str | None = None) -> list[str]:
    """Discover all .md files in durable doc subdirectories."""
    results = []
    for subdir in DOC_SUBDIRS:
        full_path = root / subdir
        if not full_path.is_dir():
            continue
        for f in sorted(full_path.rglob("*.md")):
            if changed_since:
                try:
                    mtime = os.path.getmtime(f)
                    since_ts = datetime.fromisoformat(changed_since).timestamp()
                    if mtime <= since_ts:
                        continue
                except (ValueError, OSError):
                    pass
            results.append(str(f.resolve()))
    return results


def main():
    parser = argparse.ArgumentParser(description="Discover durable memory documents")
    parser.add_argument("--root", required=True, help="Repo root directory")
    parser.add_argument("--changed-since", default=None, help="Only files modified since ISO timestamp")
    parser.add_argument("--all", action="store_true", help="Return all docs")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(json.dumps({"error": f"not a directory: {root}"}))
        sys.exit(1)

    files = discover_docs(root, args.changed_since)
    print(json.dumps({"files": files, "count": len(files)}, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
