#!/usr/bin/env python3
"""
doctor-locks — Check for stale lock files.

Purpose: Detect lock files older than 5 minutes (likely orphaned).
Invoker: memory-doctor (dispatcher).
"""
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime

LOCKS_DIR = "src/.agent-memory/locks"
STALE_THRESHOLD_S = 300


def main():
    parser = argparse.ArgumentParser(description="Check for stale lock files")
    parser.add_argument("--root", default=".", help="Repo root")
    args = parser.parse_args()

    locks_path = Path(args.root) / LOCKS_DIR
    if not locks_path.exists():
        print("No lock files found")
        sys.exit(0)

    stale = []
    for lock_file in locks_path.glob("*.lock"):
        age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(lock_file))).total_seconds()
        if age > STALE_THRESHOLD_S:
            stale.append(f"{lock_file.name} (age: {int(age)}s)")

    if stale:
        print(f"Stale locks: {', '.join(stale)}")
        sys.exit(1)
    print("No stale locks")
    sys.exit(0)


if __name__ == "__main__":
    main()
