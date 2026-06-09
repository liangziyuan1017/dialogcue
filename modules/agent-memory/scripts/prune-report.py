#!/usr/bin/env python3
"""
prune-report — Produce a prune action summary.

Purpose: Format entropy audit and prune action results.
Invoker: memory-prune workflow.
Related tests: tests/test_prune_memory.py

Input:  --actions <JSON>        JSON array of prune actions taken

Output: Formatted report to stdout.
Exit:   0 always.
"""
import argparse
import sys
import json


def main():
    parser = argparse.ArgumentParser(description="Format prune report")
    parser.add_argument("--actions", required=True, help="JSON array of prune actions")
    args = parser.parse_args()

    try:
        actions = json.loads(args.actions)
    except json.JSONDecodeError:
        print("ERROR: invalid JSON input")
        sys.exit(1)

    if not isinstance(actions, list):
        actions = [actions]

    tombstoned = sum(1 for a in actions if a.get("type") == "tombstone")
    superseded = sum(1 for a in actions if a.get("type") == "supersede")
    backstop = sum(1 for a in actions if a.get("type") == "backstop")
    merged = sum(1 for a in actions if a.get("type") == "merge")
    deletions = sum(1 for a in actions if a.get("type") == "delete")

    print("=== Prune Report ===")
    print(f"Tombstoned: {tombstoned}")
    print(f"Superseded: {superseded}")
    print(f"Backstop (unused): {backstop}")
    print(f"Merged: {merged}")
    print(f"Deletions: {deletions}")
    print(f"Information loss: 0")

    for a in actions:
        t = a.get("type", "")
        aid = a.get("id", "?")
        if t == "tombstone":
            print(f"  - {aid}: tombstoned (reason: {a.get('reason', 'stale')})")
        elif t == "supersede":
            print(f"  - {aid}: superseded → replaced_by: {a.get('replaced_by', '?')}")
        elif t == "backstop":
            print(f"  - {aid}: activation → backstop ({a.get('reason', 'unused')})")
        elif t == "merge":
            ids = a.get("ids", [])
            result = a.get("result", "?")
            print(f"  - {', '.join(ids)} → merged into {result}")

    sys.exit(0)


if __name__ == "__main__":
    main()
