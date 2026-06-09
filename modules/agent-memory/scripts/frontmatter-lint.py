#!/usr/bin/env python3
"""
frontmatter-lint — Validate frontmatter against schemas/frontmatter.schema.yaml.

Purpose: Check required fields, enum values, and schema_version.
Invoker: decision-record, lesson-capture, metadata-enforce, memory-summarize workflows.
Related tests: tests/test_schemas.py, tests/test_validate_frontmatter.py

Input:  --file <PATH>           Validate a single file's frontmatter
        --input <YAML_STRING>   Validate inline YAML frontmatter
        --schema <NAME>         (optional) Additional schema to validate against

Output: JSON validation result to stdout.
Exit:   0 if valid, 1 if violations found.
"""
import argparse
import sys
import json
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_utilities import load_yaml_frontmatter, fail, _parse_simple_yaml
from common_utilities.constants import (
    REQUIRED_FIELDS, DOC_KIND_ENUM, STATUS_ENUM, AUTHORITY_ENUM,
    ACTIVATION_ENUM, KNOWLEDGE_STATUS_ENUM, EXPORTABILITY_ENUM,
    ARTIFACT_TYPE_ENUM, DOMAIN_ENUM, SCOPE_ENUM,
    LESSON_ID_PATTERN, ADR_ID_PATTERN,
)

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_frontmatter_from_file(filepath: str) -> dict:
    """Extract YAML frontmatter from a markdown file."""
    return load_yaml_frontmatter(Path(filepath))[0]


def parse_frontmatter_string(text: str) -> dict:
    """Extract YAML frontmatter from text."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}

    return _parse_simple_yaml(lines[1:end_idx])


def validate_frontmatter(fm: dict, schema: str | None = None) -> list[str]:
    """Validate frontmatter against schema. Returns list of violation strings."""
    violations = []

    for field in REQUIRED_FIELDS:
        if field not in fm:
            violations.append(f"MISSING: {field}")

    if "doc_kind" in fm:
        if fm["doc_kind"] not in DOC_KIND_ENUM:
            violations.append(f"INVALID: doc_kind = \"{fm['doc_kind']}\" (use: {'|'.join(DOC_KIND_ENUM)})")

        if "id" in fm and fm["doc_kind"] == "lesson":
            if not re.match(LESSON_ID_PATTERN, str(fm["id"])):
                violations.append(f"INVALID: id = \"{fm['id']}\" (lesson IDs must match {LESSON_ID_PATTERN})")
        if "id" in fm and fm["doc_kind"] == "decision":
            if not re.match(ADR_ID_PATTERN, str(fm["id"])):
                violations.append(f"INVALID: id = \"{fm['id']}\" (ADR IDs must match {ADR_ID_PATTERN})")

    if "status" in fm and fm["status"] not in STATUS_ENUM:
        violations.append(f"INVALID: status = \"{fm['status']}\" (use: {'|'.join(STATUS_ENUM)})")

    if "created" in fm and not DATE_PATTERN.match(str(fm["created"])):
        violations.append(f"INVALID: created = \"{fm['created']}\" (must be YYYY-MM-DD)")

    if "schema_version" not in fm:
        violations.append("MISSING: schema_version")

    if schema == "lesson":
        lesson_violations = _validate_lesson(fm)
        violations.extend(lesson_violations)

    return violations


def _validate_lesson(fm: dict) -> list[str]:
    """Validate lesson-specific fields."""
    violations = []
    lesson_slots = ["pitfall", "root_cause", "trigger_conditions", "fix", "guard", "source_anchor"]
    for slot in lesson_slots:
        if slot not in fm or not fm[slot]:
            violations.append(f"MISSING_LESSON_SLOT: {slot} (lesson requires 7 slots)")

    if "source_anchor" in fm:
        anchors = fm["source_anchor"]
        if isinstance(anchors, list) and len(anchors) < 1:
            violations.append("QG5_FAILURE: source_anchor must have at least 1 reference")
    else:
        violations.append("QG5_FAILURE: source_anchor is required")

    return violations


def main():
    parser = argparse.ArgumentParser(description="Validate document frontmatter")
    parser.add_argument("--file", default=None, help="Path to a document to validate")
    parser.add_argument("--input", default=None, help="Inline YAML frontmatter string")
    parser.add_argument("--schema", default=None, choices=["lesson"], help="Additional schema to validate")
    args = parser.parse_args()

    if args.file:
        fm = parse_frontmatter_from_file(args.file)
    elif args.input:
        raw = args.input.strip()
        if raw.startswith("---"):
            fm = parse_frontmatter_string(raw)
        else:
            fm = parse_frontmatter_string("---\n" + raw + "\n---")
    else:
        print(json.dumps({"error": "Either --file or --input is required"}))
        sys.exit(1)

    violations = validate_frontmatter(fm, args.schema)

    result = {
        "valid": len(violations) == 0,
        "violations": violations,
        "checked_fields": list(fm.keys()),
    }
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
