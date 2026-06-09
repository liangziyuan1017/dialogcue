#!/usr/bin/env python3
"""
lint-report — Produce a human-readable metadata compliance report.

Purpose: Format validation results into a readable summary.
Invoker: metadata-enforce workflow.
Related tests: tests/test_validate_frontmatter.py

Input:  --results <JSON>     JSON array of per-file validation results

Output: Formatted report to stdout.
Exit:   0 always (formatting only).
"""
import argparse
import sys
import json


def main():
    parser = argparse.ArgumentParser(description="Format metadata compliance report")
    parser.add_argument("--results", required=True, help="JSON array of validation results")
    args = parser.parse_args()

    try:
        results = json.loads(args.results)
    except json.JSONDecodeError:
        print("ERROR: invalid JSON input")
        sys.exit(1)

    if not isinstance(results, list):
        results = [results]

    passed = sum(1 for r in results if r.get("valid", False))
    failed = sum(1 for r in results if not r.get("valid", False))

    print("=== Metadata Compliance Report ===")
    print(f"Files checked: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Violations: {failed}")
    print()

    if failed > 0:
        print("Violations:")
        for r in results:
            if not r.get("valid", False):
                file_name = r.get("file", "unknown")
                for v in r.get("violations", []):
                    print(f"  - {file_name}: {v}")

    sys.exit(0)


if __name__ == "__main__":
    main()
