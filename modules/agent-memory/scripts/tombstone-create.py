#!/usr/bin/env python3
"""
tombstone-create — Create a tombstone record for a deprecated entry.

Purpose: Non-destructive removal: tombstone with audit log and 90-day retention.
Invoker: memory-prune workflow.
Related tests: tests/test_prune_memory.py

Input:  --id <DOC_ID>            Document ID to tombstone
        --reason <STRING>        Reason for tombstoning
        --retention-days <N>     Days before physical deletion (default: 90)
        --now <ISO_TIMESTAMP>    Override current timestamp for deterministic replay
        --state-dir <PATH>       State directory (default: src/.agent-memory)

Output: JSON confirmation with tombstone path.
Exit:   0 on success, 1 on error.
"""
import argparse
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta


def create_tombstone(doc_id: str, reason: str, retention_days: int,
                     now: datetime, state_dir: str) -> dict:
    """Create a tombstone record."""
    tombstone_dir = Path(state_dir) / "tombstones"
    tombstone_dir.mkdir(parents=True, exist_ok=True)

    retain_until = now + timedelta(days=retention_days)

    tombstone = {
        "id": doc_id,
        "tombstoned_at": now.isoformat(),
        "reason": reason,
        "retain_until": retain_until.strftime("%Y-%m-%d"),
        "retention_days": retention_days,
        "original_hash": "",
    }

    tombstone_path = tombstone_dir / f"{doc_id}.tombstone.yaml"
    with open(tombstone_path, "w", encoding="utf-8") as f:
        f.write(f"# Tombstone for {doc_id}\n")
        f.write(f"id: {doc_id}\n")
        f.write(f"tombstoned_at: {tombstone['tombstoned_at']}\n")
        f.write(f"reason: \"{reason}\"\n")
        f.write(f"retain_until: {tombstone['retain_until']}\n")
        f.write(f"retention_days: {retention_days}\n")

    return {
        "id": doc_id,
        "tombstone_path": str(tombstone_path),
        "retain_until": tombstone["retain_until"],
    }


def main():
    parser = argparse.ArgumentParser(description="Create tombstone for deprecated entry")
    parser.add_argument("--id", required=True, help="Document ID")
    parser.add_argument("--reason", required=True, help="Reason for tombstoning")
    parser.add_argument("--retention-days", type=int, default=90, help="Retention period in days")
    parser.add_argument("--now", default=None, help="Override current timestamp (ISO format) for deterministic replay")
    parser.add_argument("--state-dir", default="src/.agent-memory", help="State directory (default: src/.agent-memory)")
    args = parser.parse_args()

    now = datetime.fromisoformat(args.now) if args.now else datetime.now()
    result = create_tombstone(args.id, args.reason, args.retention_days, now, args.state_dir)
    print(json.dumps(result, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
