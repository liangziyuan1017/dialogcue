---
name: metadata-enforce
description: >
  Validate document frontmatter and metadata compliance across durable memory files.
  Use when: the project needs metadata hygiene or schema compliance checks.
  Not for: creating new decisions, lessons, or search queries.
  Output: a metadata validation report with missing or invalid fields.
triggers:
  - "check metadata"
  - "validate frontmatter"
  - "are docs compliant"
  - "metadata check"
  - "frontmatter lint"
---

# Metadata Enforce

Route metadata compliance checks to the metadata-enforce workflow.

## What this skill does

1. Confirms the task is about metadata quality rather than content retrieval or creation
2. Routes compliance checks to the metadata-enforce workflow
3. Keeps schema validation concerns separate from memory writes

## When to use

- Durable memory documents need compliance checking
- Frontmatter drift or missing fields must be reported

## When NOT to use

- A new ADR or lesson needs to be created
- The task is a search for existing knowledge

## Execution

→ Read `workflows/metadata-enforce.md` for the ordered execution steps.
→ Run commands from `modules/agent-memory/scripts/`.

## Tests

| Test | Path | Verifies |
|---|---|---|
| validate_frontmatter | `tests/test_validate_frontmatter.py` | Required fields, enum validation, all fixture docs valid |
| validate_knowledge_block | `tests/test_validate_frontmatter.py` | Knowledge block authority/activation/status/exportability enums |

## Examples

- **Full directory scan**: `metadata-enforce --root docs/` → compliance report with per-file violations and summary counts
- **Single file check**: `metadata-enforce --file docs/decisions/ADR-003.md` → reports `MISSING: schema_version` if absent
