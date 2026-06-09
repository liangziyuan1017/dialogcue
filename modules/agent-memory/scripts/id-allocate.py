#!/usr/bin/env python3
"""
id-allocate — Atomically allocate the next ID for a document kind.

Purpose: Reserve IDs through a lock file; reject duplicates; retry on collision.
Invoker: decision-record, lesson-capture, memory-summarize workflows.
Related tests: tests/test_write_decision.py, tests/test_write_lesson.py, tests/test_concurrency.py

Input:  --kind <ADR|LL|SUM|MP>   Document kind prefix
        --slug <string>          (optional) Slug for SUM/MP IDs
        --now <ISO_TIMESTAMP>    Override current timestamp for deterministic replay
        --state-dir <PATH>       State directory (default: src/.agent-memory)

Output: JSON with allocated ID to stdout.
Exit:   0 on success, 1 on lock timeout or error.
"""
import argparse
import sys
import json
import time
import os
from pathlib import Path
from datetime import datetime

LOCK_TIMEOUT = 30


def _resolve_paths(state_dir: str):
    """Resolve paths relative to state-dir."""
    base = Path(state_dir)
    return {
        "lock_dir": base / "locks",
        "allocator_file": base / "state" / "id-allocator.json",
    }


def acquire_lock(lock_dir: Path) -> bool:
    """Acquire the ID allocation lock file. Returns True if acquired."""
    lock_dir.mkdir(parents=True, exist_ok=True)
    lockfile = lock_dir / "id-allocation.lock"
    deadline = time.time() + LOCK_TIMEOUT
    while time.time() < deadline:
        try:
            fd = os.open(lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except FileExistsError:
            time.sleep(0.1)
    return False


def release_lock(lock_dir: Path) -> None:
    """Release the ID allocation lock file."""
    lockfile = lock_dir / "id-allocation.lock"
    try:
        os.remove(lockfile)
    except FileNotFoundError:
        pass


def read_allocator(allocator_file: Path) -> dict:
    """Read the current ID allocation state."""
    if not allocator_file.exists():
        allocator_file.parent.mkdir(parents=True, exist_ok=True)
        return {"ADR": 0, "LL": 0, "SUM": 0, "MP": 0}
    with open(allocator_file, "r") as f:
        return json.load(f)


def write_allocator(state: dict, allocator_file: Path) -> None:
    """Write updated ID allocation state."""
    allocator_file.parent.mkdir(parents=True, exist_ok=True)
    with open(allocator_file, "w") as f:
        json.dump(state, f, indent=2)


def allocate(kind: str, slug: str | None = None, now: datetime | None = None,
             state_dir: str = "src/.agent-memory") -> str:
    """Allocate the next ID for the given kind."""
    if kind not in ("ADR", "LL", "SUM", "MP"):
        raise ValueError(f"Unknown ID kind: {kind} (use ADR, LL, SUM, or MP)")

    paths = _resolve_paths(state_dir)

    if not acquire_lock(paths["lock_dir"]):
        raise TimeoutError(f"Could not acquire id-allocation.lock within {LOCK_TIMEOUT}s")

    try:
        state = read_allocator(paths["allocator_file"])
        state[kind] = state.get(kind, 0) + 1
        next_num = state[kind]

        ts_now = now or datetime.now()

        if kind in ("ADR", "LL"):
            new_id = f"{kind}-{next_num:03d}"
        elif kind == "SUM":
            ts = ts_now.strftime("%Y%m%d-%H%M")
            slug_part = slug or "summary"
            new_id = f"SUM-{ts}-{slug_part}"
        elif kind == "MP":
            ts = ts_now.strftime("%Y%m%d%H%M%S")
            slug_part = slug or "proposal"
            new_id = f"MP-{ts}-{slug_part}"

        write_allocator(state, paths["allocator_file"])
        return new_id
    finally:
        release_lock(paths["lock_dir"])


def main():
    parser = argparse.ArgumentParser(description="Atomically allocate document IDs")
    parser.add_argument("--kind", required=True, choices=["ADR", "LL", "SUM", "MP"], help="Document kind prefix")
    parser.add_argument("--slug", default=None, help="Slug for SUM/MP IDs")
    parser.add_argument("--now", default=None, help="Override current timestamp (ISO format) for deterministic replay")
    parser.add_argument("--state-dir", default="src/.agent-memory", help="State directory (default: src/.agent-memory)")
    args = parser.parse_args()

    now = datetime.fromisoformat(args.now) if args.now else None

    try:
        new_id = allocate(args.kind, args.slug, now, args.state_dir)
        print(json.dumps({"id": new_id, "kind": args.kind}))
        sys.exit(0)
    except TimeoutError as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(2)
    except ValueError as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
