#!/usr/bin/env python3
"""
content-hash — Compute SHA-256 content hash for each document.

Purpose: Detect changes for incremental indexing.
Invoker: memory-index workflow.
Related tests: tests/test_rebuild_index.py

Input:  --file <PATH>       Single file to hash
        --files <PATHS>     Multiple files (space-separated or JSON list)

Output: JSON with file→hash mapping to stdout.
Exit:   0 on success, 1 on error.
"""
import argparse
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_utilities import compute_content_hash


def main():
    parser = argparse.ArgumentParser(description="Compute content hashes for documents")
    parser.add_argument("--file", default=None, help="Single file path")
    parser.add_argument("--files", default=None, nargs="*", help="Multiple file paths")
    args = parser.parse_args()

    if args.file:
        files = [args.file]
    elif args.files:
        files = args.files
    else:
        print(json.dumps({"error": "Either --file or --files is required"}))
        sys.exit(1)

    results = {}
    errors = []
    for f in files:
        try:
            results[f] = compute_content_hash(Path(f))
        except FileNotFoundError:
            errors.append(f"file not found: {f}")
        except Exception as e:
            errors.append(f"error hashing {f}: {str(e)}")

    output = {"hashes": results, "count": len(results)}
    if errors:
        output["errors"] = errors

    print(json.dumps(output, indent=2))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
