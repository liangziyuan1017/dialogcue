# tests

Deterministic verification of module behavior.

## Test Inventory

| Test File | What It Verifies | Fixtures Used |
|---|---|---|
| test_schemas.py | Schema validation (required fields, enums, patterns) | structured-repo |
| test_templates.py | Template placeholder structure | templates/ |
| test_search_memory.py | Search ranking, exact lookup, degradation | structured-repo |
| test_write_lesson.py | Lesson capture, quality gates, dedup | tempfile |
| test_summarize_conversation.py | Eligibility, L1 generation, no-summary-of-summary | tempfile |
| test_prune_memory.py | Non-destructive prune, tombstones, merges | structured-repo |
| test_concurrency.py | Concurrent ID allocation, optimistic concurrency | tempfile |
| test_migration.py | Migration matrix, de-cat, schema consistency | refs/, schemas/ |
| test_adapters.py | Adapter integrity, independence | adapters/ |

## Running Tests

```bash
cd modules/agent-memory
python -m pytest tests/ -v
```
