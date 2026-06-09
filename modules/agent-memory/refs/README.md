# Reference Index

This directory contains normalized, reusable reference documents extracted from the source material and rewritten for the independent `agent-memory` module.

## Reference Set

| File | Purpose |
|---|---|
| `first-principles.md` | Axioms and worldview |
| `governance-structure.md` | Governance hierarchy and truth sources |
| `shared-rules.md` | Operational rules |
| `collaboration-protocol.md` | Why-First handoff and challenge protocol |
| `metadata-contract.md` | Frontmatter contract for durable docs |
| `knowledge-objects.md` | Durable knowledge metadata model |
| `lessons-template.md` | LL-XXX template and quality gates |
| `memory-architecture.md` | Retrieval, indexing, and summarization patterns |
| `memory-entropy-reduction.md` | Lifecycle, pruning, and non-destructive compression |
| `expedition-memory.md` | External-project bootstrap and reflux |
| `memory-lessons.md` | Operational lessons from prior memory system experience |
| `anti-drift-protocol.md` | Drift prevention and vision alignment |
| `sop.md` | Standard operating procedures |

## Source-to-Target Migration Matrix

| Source file in `temp/` | Action | Target artifact |
|---|---|---|
| `decisions-first-principles.md` | keep, normalize | `refs/first-principles.md` |
| `shared-rules.md` | keep, de-cat ✓ | `refs/shared-rules.md` |
| `decisions-collaboration-protocol.md` | keep, normalize | `refs/collaboration-protocol.md` |
| `decisions-metadata-contract.md` | keep, normalize | `refs/metadata-contract.md` |
| `decisions-knowledge-objects.md` | keep, extend | `refs/knowledge-objects.md` |
| `lessons-system.md` | split | `refs/lessons-template.md` |
| `memory-f102-architecture.md` | abstract impl details | `refs/memory-architecture.md` |
| `memory-entropy-reduction.md` | keep, normalize | `refs/memory-entropy-reduction.md` |
| `features-expedition-memory.md` | keep, normalize | `refs/expedition-memory.md` |
| `memory-hindsight-integration.md` | extract lessons only | `refs/memory-lessons.md` |
| `features-anti-drift.md` | keep, normalize | `refs/anti-drift-protocol.md` |
| `sop.md` | keep, de-cat ✓ | `refs/sop.md` |
| `docs-overview.md` | absorb | `README.md`, `refs/README.md` |
| `README.md` | absorb | `README.md`, `refs/README.md` |
| `vision.md` | absorb selective principles | `refs/governance-structure.md` |

## Normalization Rules

- Public module docs must not depend on Cat Cafe terminology.
- Historical source naming may be mentioned only in short provenance notes.
- References are pattern documents, not workflow files and not implementation scripts.
