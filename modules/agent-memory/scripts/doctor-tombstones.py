#!/usr/bin/env python3
"""
doctor-tombstones — Check for expired tombstones eligible for physical deletion.

Purpose: Report tombstones past their retention period.
Invoker: memory-doctor (dispatcher).
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime

TOMBSTONES_DIR = "src/.agent-memory/tombstones"


def main():
    parser = argparse.ArgumentParser(description="Check for expired tombstones")
    parser.add_argument("--root", default=".", help="Repo root")
    args = parser.parse_args()

    tombstones_path = Path(args.root) / TOMBSTONES_DIR
    if not tombstones_path.exists():
        print("No tombstones found")
        sys.exit(0)

    expired = []
    for tf in tombstones_path.glob("*.tombstone.yaml"):
        with open(tf) as f:
            for line in f:
                if "retain_until:" in line:
                    retain_until = line.split(":", 1)[1].strip().strip('"')
                    try:
                        if datetime.now() > datetime.strptime(retain_until, "%Y-%m-%d"):
                            expired.append(f"{tf.name} (retain_until: {retain_until})")
                    except ValueError:
                        pass
                    break

    if expired:
        print(f"Expired tombstones eligible for deletion: {', '.join(expired)}")
        sys.exit(1)
    print("No expired tombstones")
    sys.exit(0)


if __name__ == "__main__":
    main()
