#!/usr/bin/env python3
"""
boundary-check — Check a proposed change against memory boundaries (rules.md §2).

Purpose: Verify the change doesn't violate memory class boundaries.
Invoker: governance-review workflow.
Related tests: tests/test_governance_review.py

Input:  --against <STRING>      Description of the proposed change

Output: JSON result to stdout.
Exit:   0 if within boundaries, 1 if violation.
"""
import argparse
import sys
import json

BOUNDARIES = {
    "allowed": ["ADRs", "decision records", "lessons with source anchors", "validated facts", "project summaries"],
    "blocked": ["raw chats", "speculative ideas", "unfinished disagreements", "tool logs"],
}


def check_boundaries(description: str) -> dict:
    """Check if change respects memory boundaries."""
    desc_lower = description.lower()
    violations = []

    blocked_triggers = {
        "raw chat": "raw chats must not enter durable memory",
        "raw transcript": "raw transcripts must not enter durable memory",
        "speculative": "speculative ideas without evidence must not enter durable memory",
        "tool log": "tool execution logs must not enter durable memory",
        "unfinished": "unfinished disagreements must not enter durable memory",
    }

    for trigger, message in blocked_triggers.items():
        if trigger in desc_lower:
            violations.append(f"rules.md §2: {message}")

    return {
        "result": "VIOLATION" if violations else "PASS",
        "violations": violations,
    }


def main():
    parser = argparse.ArgumentParser(description="Check memory boundaries")
    parser.add_argument("--against", required=True, help="Description of proposed change")
    args = parser.parse_args()

    result = check_boundaries(args.against)
    print(json.dumps(result, indent=2))
    sys.exit(1 if result["result"] == "VIOLATION" else 0)


if __name__ == "__main__":
    main()
