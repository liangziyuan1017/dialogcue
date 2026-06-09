#!/usr/bin/env python3
"""
knowledge-validate — Validate optional knowledge: block against schemas/knowledge-object.schema.yaml.

Purpose: Check authority, activation, status, exportability enums.
Invoker: metadata-enforce workflow.
Related tests: tests/test_validate_frontmatter.py

Input:  --file <PATH>       Validate knowledge block in a document

Output: JSON validation result.
Exit:   0 if valid (or no knowledge block), 1 if violations.
"""
import argparse
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_utilities import load_yaml_frontmatter
from common_utilities.constants import (
    AUTHORITY_ENUM, ACTIVATION_ENUM, KNOWLEDGE_STATUS_ENUM, EXPORTABILITY_ENUM,
)


def validate_knowledge(fm: dict) -> list[str]:
    """Validate knowledge block fields."""
    violations = []

    if "knowledge" not in fm:
        return violations

    authority = fm.get("authority", "")
    activation = fm.get("activation", "")
    kstatus = fm.get("knowledge_status", fm.get("status", ""))
    exportability = fm.get("exportability", "")

    if authority and authority not in AUTHORITY_ENUM:
        violations.append(f"INVALID: authority = \"{authority}\" (use: {'|'.join(AUTHORITY_ENUM)})")

    if activation and activation not in ACTIVATION_ENUM:
        violations.append(f"INVALID: activation = \"{activation}\" (use: {'|'.join(ACTIVATION_ENUM)})")

    if kstatus and kstatus not in KNOWLEDGE_STATUS_ENUM:
        violations.append(f"INVALID: knowledge.status = \"{kstatus}\" (use: {'|'.join(KNOWLEDGE_STATUS_ENUM)})")

    if exportability and exportability not in EXPORTABILITY_ENUM:
        violations.append(f"INVALID: exportability = \"{exportability}\" (use: {'|'.join(EXPORTABILITY_ENUM)})")

    return violations


def main():
    parser = argparse.ArgumentParser(description="Validate knowledge block")
    parser.add_argument("--file", required=True, help="Document path")
    args = parser.parse_args()

    fm = load_yaml_frontmatter(Path(args.file))[0]
    violations = validate_knowledge(fm)

    result = {
        "file": args.file,
        "has_knowledge_block": "knowledge" in fm or "authority" in fm,
        "valid": len(violations) == 0,
        "violations": violations,
    }
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
