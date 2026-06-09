#!/usr/bin/env python3
"""
review-report — Produce a governance review report with pass/violation/caution.

Purpose: Format governance review results.
Invoker: governance-review workflow.
Related tests: tests/test_governance_review.py

Input:  --results <JSON>        JSON array of per-category check results

Output: Formatted review report to stdout.
Exit:   0 if all pass, 1 if any violation.
"""
import argparse
import sys
import json


def main():
    parser = argparse.ArgumentParser(description="Format governance review report")
    parser.add_argument("--results", required=True, help="JSON array of check results")
    args = parser.parse_args()

    try:
        results = json.loads(args.results)
    except json.JSONDecodeError:
        print("ERROR: invalid JSON input")
        sys.exit(1)

    if not isinstance(results, list):
        results = [results]

    passed = sum(1 for r in results if r.get("result") == "PASS")
    violations = sum(1 for r in results if r.get("result") == "VIOLATION")
    cautions = sum(1 for r in results if r.get("result") == "CAUTION")

    if violations > 0:
        overall = "VIOLATION"
    elif cautions > 0:
        overall = "CAUTION"
    else:
        overall = "PASS"

    print("=== Governance Review Report ===")
    print(f"Result: {overall}")
    print()

    if violations > 0:
        print("Violations:")
        for r in results:
            if r.get("result") == "VIOLATION":
                cat = r.get("category", "unknown")
                for v in r.get("violations", []):
                    print(f"  - {cat}: {v}")
        print()

    if cautions > 0:
        print("Cautions:")
        for r in results:
            if r.get("result") == "CAUTION":
                print(f"  - {r.get('category', 'unknown')}: {r.get('reason', '')}")
        print()

    print(f"Passed: {passed} of {len(results)} rule categories")

    sys.exit(1 if violations > 0 else 0)


if __name__ == "__main__":
    main()
