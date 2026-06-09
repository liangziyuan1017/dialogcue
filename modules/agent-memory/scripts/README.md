# scripts

Tiny deterministic execution units for the agent-memory module.

## Script Inventory

| Script | Purpose | Invoker |
|---|---|---|
| discover-docs.py | Scan repo for durable memory documents | memory-bootstrap, memory-index, metadata-enforce |
| validate-each.py | Batch frontmatter validation | memory-bootstrap |
| id-allocate.py | Atomic ID allocation | decision-record, lesson-capture, memory-summarize |
| frontmatter-lint.py | Validate frontmatter against schemas | decision-record, lesson-capture, metadata-enforce, memory-summarize |
| write-durable.py | Append-first write with optimistic concurrency | decision-record, lesson-capture, memory-summarize, memory-prune |
| content-hash.py | SHA-256 content hash for change detection | memory-index |
| knowledge-validate.py | Validate knowledge: block enums | metadata-enforce |
| lint-report.py | Human-readable compliance report | metadata-enforce |
| index-rebuild.py | Full or incremental index rebuild | memory-bootstrap, memory-index, decision-record, lesson-capture, memory-summarize, memory-prune |
| index-report.py | Human-readable rebuild summary | memory-index |
| bootstrap-report.py | Human-readable bootstrap summary | memory-bootstrap |
| lexical-search.py | Exact and fuzzy text search | memory-search, decision-record, lesson-capture |
| semantic-search.py | Vector similarity search (stub) | memory-search |
| hybrid-fuse.py | Reciprocal-rank fusion | memory-search |
| result-format.py | Format ranked results with metadata | memory-search |
| rule-check.py | Check against rules.md invariants | governance-review |
| principle-check.py | Check against first-principles.md | governance-review |
| boundary-check.py | Check against memory boundaries | governance-review |
| review-report.py | Governance review report | governance-review |
| summarize-check-eligibility.py | Check L1 summarization thresholds | memory-summarize |
| summarize-generate.py | Generate L1 summary segment | memory-summarize |
| entropy-audit.py | Scan for stale/duplicate/superseded knowledge | memory-prune |
| tombstone-create.py | Create tombstone record | memory-prune |
| merge-propose.py | Propose merge of duplicate entries | memory-prune |
| prune-report.py | Prune action summary | memory-prune |
| memory-doctor.py | Diagnostic health check | manual, CI |

## Shared Utilities

- `common_utilities/` — shared parsing, hashing, I/O, and constants
- All scripts import from `common_utilities` rather than duplicating logic

## Design Principles

- One deterministic function per script where practical
- Clear I/O contracts (argparse, exit codes, JSON output)
- No routing, orchestration, or policy logic in scripts
- No host-specific assumptions (paths configurable via CLI args)
- `--now` parameter for deterministic replay of timestamp-dependent scripts
- `--state-dir` parameter for configurable state directory location
