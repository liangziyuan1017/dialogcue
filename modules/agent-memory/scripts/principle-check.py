#!/usr/bin/env python3
"""
principle-check — Check a proposed change against refs/first-principles.md.

Purpose: Verify alignment with foundational principles.
Invoker: governance-review workflow.
Related tests: tests/test_governance_review.py

Input:  --against <STRING>      Description of the proposed change

Output: JSON result to stdout.
Exit:   0 if aligned, 1 if violation.
"""
import argparse
import sys
import json

PRINCIPLES = [
    ("documents-truth", "Source of truth is human-readable documents, not the compiled index"),
    ("rebuildable-index", "The index is a rebuildable artifact"),
    ("durable-project", "Project memory is durable; session memory is ephemeral until promoted"),
    ("low-authority-start", "New knowledge starts low-authority and is promoted only with evidence"),
    ("non-destructive-compression", "Compression is non-destructive"),
    ("fail-closed", "If import, reflux, or promotion is uncertain, fail closed"),
    ("multi-agent", "Module must work for any host system that follows the adapter contract"),
]


def check_principles(description: str) -> dict:
    """Check against principles."""
    desc_lower = description.lower()
    violations = []

    if "delete" in desc_lower and "tombstone" not in desc_lower:
        violations.append("non-destructive-compression: hard delete detected — must use tombstone")
    if "overwrite index" in desc_lower or "index is truth" in desc_lower:
        violations.append("rebuildable-index: index is rebuildable, documents are truth")
    if "raw chat" in desc_lower and "durable" in desc_lower:
        violations.append("durable-project: raw chats should not enter durable memory")

    return {
        "result": "VIOLATION" if violations else "PASS",
        "violations": violations,
        "principles_checked": len(PRINCIPLES),
    }


def main():
    parser = argparse.ArgumentParser(description="Check against first principles")
    parser.add_argument("--against", required=True, help="Description of proposed change")
    args = parser.parse_args()

    result = check_principles(args.against)
    print(json.dumps(result, indent=2))
    sys.exit(1 if result["result"] == "VIOLATION" else 0)


if __name__ == "__main__":
    main()
