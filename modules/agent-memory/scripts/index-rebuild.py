#!/usr/bin/env python3
"""
index-rebuild — Build or rebuild the searchable memory index.

Purpose: Full or incremental index rebuild from durable documents.
Invoker: memory-bootstrap, memory-index, decision-record, lesson-capture,
         memory-summarize, memory-prune workflows.
Related tests: tests/test_rebuild_index.py

Input:  --scope <full|incremental>    Rebuild scope
        --files <PATHS...>            (optional) Specific files to index
        --root <PATH>                 (optional) Repo root for full rebuild discovery
        --acquire-lock                Attempt to acquire the index lock
        --now <ISO_TIMESTAMP>         Override current timestamp for deterministic replay
        --state-dir <PATH>            State directory (default: src/.agent-memory)

Output: JSON rebuild report to stdout.
Exit:   0 on success, 1 on error, 2 on lock timeout.
"""
import argparse
import sys
import json
import os
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_utilities import compute_content_hash, load_yaml_frontmatter, write_json, read_json, ensure_dir

LOCK_TIMEOUT = 30


def _resolve_paths(state_dir: str):
    """Resolve index paths relative to state-dir."""
    base = Path(state_dir)
    return {
        "index_dir": base,
        "index_file": base / "index.json",
        "state_file": base / "state" / "index-state.json",
        "lock_file": base / "locks" / "index-rebuild.lock",
    }


def acquire_lock(lock_file: Path) -> bool:
    """Try to acquire the index rebuild lock."""
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + LOCK_TIMEOUT
    while time.time() < deadline:
        try:
            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except FileExistsError:
            time.sleep(0.1)
    return False


def release_lock(lock_file: Path) -> None:
    """Release the index rebuild lock."""
    try:
        os.remove(lock_file)
    except FileNotFoundError:
        pass


def build_index_entry(filepath: str, now: datetime) -> dict:
    """Build an index entry from a document."""
    fm, body = load_yaml_frontmatter(Path(filepath))

    entry = {
        "path": filepath,
        "content_hash": compute_content_hash(Path(filepath)),
        "indexed_at": now.isoformat(),
    }

    for k in ("id", "title", "doc_kind", "status", "feature_ids", "topics", "created"):
        if k in fm:
            entry[k] = fm[k]

    if body:
        entry["body_preview"] = body.strip()[:500]

    return entry


def load_index(index_file: Path) -> dict:
    """Load existing index."""
    if index_file.exists():
        return read_json(index_file)
    return {"entries": {}, "last_full_rebuild": None, "last_incremental_rebuild": None}


def save_index(index: dict, index_file: Path) -> None:
    """Save index to file."""
    ensure_dir(index_file.parent)
    write_json(index, index_file)


def rebuild_full(root: str, now: datetime, paths: dict) -> dict:
    """Full index rebuild."""
    root_path = Path(root)
    doc_dirs = ["docs/decisions", "docs/lessons", "docs/summaries"]

    index = {"entries": {}, "last_full_rebuild": now.isoformat(), "last_incremental_rebuild": None}
    indexed = 0
    conflicts = 0

    for subdir in doc_dirs:
        full = root_path / subdir
        if not full.is_dir():
            continue
        for f in sorted(full.rglob("*.md")):
            entry = build_index_entry(str(f), now)
            doc_id = entry.get("id", str(f))
            if doc_id in index["entries"]:
                conflicts += 1
            index["entries"][doc_id] = entry
            indexed += 1

    index["doc_count"] = indexed
    index["hash_conflicts"] = conflicts
    save_index(index, paths["index_file"])
    return index


def rebuild_incremental(files: list[str], now: datetime, paths: dict) -> dict:
    """Incremental index rebuild for specific files."""
    index = load_index(paths["index_file"])
    indexed = 0
    skipped = 0
    conflicts = 0

    for f in files:
        entry = build_index_entry(f, now)
        doc_id = entry.get("id", str(f))
        old_hash = index["entries"].get(doc_id, {}).get("content_hash", "")

        if old_hash == entry["content_hash"] and doc_id in index["entries"]:
            skipped += 1
            continue

        if doc_id in index["entries"] and old_hash != entry["content_hash"]:
            conflicts += 1

        index["entries"][doc_id] = entry
        indexed += 1

    index["last_incremental_rebuild"] = now.isoformat()
    save_index(index, paths["index_file"])
    return {
        "indexed": indexed,
        "skipped": skipped,
        "conflicts": conflicts,
        "last_incremental_rebuild": index["last_incremental_rebuild"],
    }


def main():
    parser = argparse.ArgumentParser(description="Rebuild memory index")
    parser.add_argument("--scope", required=True, choices=["full", "incremental"], help="Rebuild scope")
    parser.add_argument("--files", nargs="*", default=None, help="Specific files (incremental)")
    parser.add_argument("--root", default=None, help="Repo root (full)")
    parser.add_argument("--acquire-lock", action="store_true", help="Acquire index lock")
    parser.add_argument("--now", default=None, help="Override current timestamp (ISO format) for deterministic replay")
    parser.add_argument("--state-dir", default="src/.agent-memory", help="State directory (default: src/.agent-memory)")
    args = parser.parse_args()

    now = datetime.fromisoformat(args.now) if args.now else datetime.now()
    paths = _resolve_paths(args.state_dir)

    if args.acquire_lock:
        if not acquire_lock(paths["lock_file"]):
            print(json.dumps({"error": "index-rebuild.lock held by another process", "timeout_s": LOCK_TIMEOUT}))
            sys.exit(2)

    try:
        if args.scope == "full":
            root = args.root or "."
            result = rebuild_full(root, now, paths)
            print(json.dumps({
                "docs_indexed": result["doc_count"],
                "hash_conflicts": result["hash_conflicts"],
                "last_full_rebuild": result["last_full_rebuild"],
                "index_location": str(paths["index_file"]),
            }, indent=2))
        else:
            if not args.files:
                print(json.dumps({"error": "--files required for incremental rebuild"}))
                sys.exit(1)
            result = rebuild_incremental(args.files, now, paths)
            print(json.dumps(result, indent=2))

        sys.exit(0)
    finally:
        if args.acquire_lock:
            release_lock(paths["lock_file"])


if __name__ == "__main__":
    main()
