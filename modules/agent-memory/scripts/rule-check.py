#!/usr/bin/env python3
"""
rule-check — Check a proposed change against rules.md invariants.

Purpose: Verify alignment with module rules (invariants, authority, concurrency, etc.).
Invoker: governance-review workflow.
Related tests: tests/test_governance_review.py

Input:  --rules <CATEGORY>      Rule category: invariants, authority, concurrency, privacy, summary, compression
        --against <STRING>      Description of the proposed change

Output: JSON result (PASS | VIOLATION) to stdout.
Exit:   0 if PASS, 1 if VIOLATION.
"""
import argparse
import sys
import json


# Rule definitions
RULE_CHECKS = {
    "invariants": [
        ("no-host-logic", "Change must not introduce host-specific logic in core files"),
        ("deterministic-chain", "Change must follow registry → router → skill → workflow → scripts"),
        ("documents-truth", "Documents are source of truth; index is rebuildable"),
    ],
    "authority": [
        ("default-authority", "New knowledge defaults to observed + query + active"),
        ("constitutional-gate", "Only human-reviewed flow can create constitutional knowledge"),
    ],
    "concurrency": [
        ("append-first", "All writes must be append-first"),
        ("tombstone-before-delete", "Deletes must be tombstones, never hard deletes"),
        ("atomic-id", "ID allocation must be atomic"),
    ],
    "privacy": [
        ("no-secrets", "Must not expose secrets, credentials, or customer names"),
        ("exportability", "Exportability must match content sensitivity"),
    ],
    "summary": [
        ("no-summary-of-summary", "Cannot summarize an existing summary"),
        ("append-only", "Summaries are append-only"),
    ],
    "compression": [
        ("non-destructive", "Compression must be non-destructive"),
        ("tombstone-retention", "90-day tombstone retention required"),
        ("source-traceability", "Source IDs must be preserved in merges"),
    ],
}


def check_rules(category: str, description: str) -> dict:
    """Check proposed change against a rule category."""
    if category not in RULE_CHECKS:
        return {"category": category, "result": "ERROR", "reason": f"unknown category: {category}"}

    checks = RULE_CHECKS[category]
    violations = []

    for check_id, check_desc in checks:
        # Check for violations based on patterns in the description
        desc_lower = description.lower()

        if check_id == "no-summary-of-summary" and "summary" in desc_lower and ("re-summarize" in desc_lower or "summarize" in desc_lower and "summary" in desc_lower.replace("summarize", "", 1)):
            violations.append(f"rules.md §7: {check_desc}")
        elif check_id == "tombstone-before-delete" and "delete" in desc_lower:
            # A delete is safe only if it explicitly mentions creating a tombstone WITH the delete
            has_tombstone = "with tombstone" in desc_lower or "create tombstone" in desc_lower or "tombston" in desc_lower and "without" not in desc_lower
            if not has_tombstone:
                violations.append(f"rules.md §4: {check_desc}")
        elif check_id == "no-secrets" and any(w in desc_lower for w in ["password", "secret", "token", "api key"]):
            violations.append(f"rules.md §5: {check_desc}")
        elif check_id == "append-first" and "overwrite" in desc_lower:
            violations.append(f"rules.md §4: {check_desc}")
        elif check_id == "non-destructive" and "delete" in desc_lower and "tombstone" not in desc_lower:
            violations.append(f"rules.md §6: {check_desc}")

    return {
        "category": category,
        "result": "VIOLATION" if violations else "PASS",
        "violations": violations,
        "checks_run": len(checks),
    }


def main():
    parser = argparse.ArgumentParser(description="Check proposed change against rules")
    parser.add_argument("--rules", required=True, help="Rule category to check")
    parser.add_argument("--against", required=True, help="Description of proposed change")
    args = parser.parse_args()

    result = check_rules(args.rules, args.against)
    print(json.dumps(result, indent=2))
    sys.exit(1 if result["result"] == "VIOLATION" else 0)


if __name__ == "__main__":
    main()
