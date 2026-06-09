#!/usr/bin/env python3
"""
index-report — Produce a human-readable index rebuild summary.

Purpose: Format index rebuild results.
Invoker: memory-index workflow.
Related tests: tests/test_rebuild_index.py

Input:  --indexed <N> --skipped <N> --conflicts <N>

Output: Formatted report to stdout.
Exit:   0 always.
"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Format index rebuild report")
    parser.add_argument("--indexed", type=int, required=True, help="Docs indexed")
    parser.add_argument("--skipped", type=int, default=0, help="Docs skipped")
    parser.add_argument("--conflicts", type=int, default=0, help="Hash conflicts")
    args = parser.parse_args()

    total = args.indexed + args.skipped
    print(f"{args.indexed} docs indexed, {args.skipped} unchanged, {args.conflicts} hash conflicts")
    print(f"Total documents: {total}")

    if args.conflicts > 0:
        print(f"WARNING: {args.conflicts} hash conflicts detected — verify duplicates manually")

    sys.exit(0)


if __name__ == "__main__":
    main()
