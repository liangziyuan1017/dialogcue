#!/usr/bin/env python3
"""
doctor-index — Check if the memory index is stale.

Purpose: Compare index rebuild timestamp against document modification times.
Invoker: memory-doctor (dispatcher).
"""
import argparse
import sys
import json
import os
from pathlib import Path
from datetime import datetime

INDEX_FILE = "src/.agent-memory/index.json"
DOC_DIRS = ["docs/decisions", "docs/lessons", "docs/summaries"]


def main():
    parser = argparse.ArgumentParser(description="Check index staleness")
    parser.add_argument("--root", default=".", help="Repo root")
    args = parser.parse_args()

    root = Path(args.root)
    index_path = root / INDEX_FILE
    if not index_path.exists():
        print("No index found — run memory-bootstrap or index-rebuild")
        sys.exit(1)

    with open(index_path) as f:
        index = json.load(f)
    last_rebuild = index.get("last_full_rebuild") or index.get("last_incremental_rebuild")
    if not last_rebuild:
        print("Index has no rebuild timestamp")
        sys.exit(1)

    rebuild_time = datetime.fromisoformat(last_rebuild)
    stale = 0
    for subdir in DOC_DIRS:
        full = root / subdir
        if not full.is_dir():
            continue
        for f in full.rglob("*.md"):
            if datetime.fromtimestamp(os.path.getmtime(f)) > rebuild_time:
                stale += 1

    if stale:
        print(f"Index may be stale: {stale} doc(s) modified since {last_rebuild}")
        sys.exit(1)
    print("Index is up to date")
    sys.exit(0)


if __name__ == "__main__":
    main()
