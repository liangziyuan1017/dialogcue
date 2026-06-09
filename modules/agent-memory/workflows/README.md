# workflows

Deterministic workflow files for the agent-memory module.

Each workflow orchestrates scripts in a fixed execution order with explicit success/failure conditions.

## Workflow Inventory

| Workflow | Skill | Scripts Used |
|---|---|---|
| memory-bootstrap | memory-bootstrap | discover-docs, validate-each, index-rebuild, bootstrap-report |
| memory-index | memory-index | discover-docs, content-hash, index-rebuild, index-report |
| memory-search | memory-search | lexical-search, semantic-search, hybrid-fuse, result-format |
| decision-record | decision-record | id-allocate, frontmatter-lint, lexical-search, content-hash, write-durable, index-rebuild |
| lesson-capture | lesson-capture | id-allocate, frontmatter-lint, lexical-search, write-durable, index-rebuild |
| metadata-enforce | metadata-enforce | discover-docs, frontmatter-lint, knowledge-validate, lint-report |
| governance-review | governance-review | rule-check, principle-check, boundary-check, review-report |
| memory-summarize | memory-summarize | summarize-check-eligibility, summarize-generate, id-allocate, frontmatter-lint, write-durable, index-rebuild |
| memory-prune | memory-prune | entropy-audit, tombstone-create, merge-propose, write-durable, rule-check, prune-report, index-rebuild |
