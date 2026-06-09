# Schemas

Machine-readable reusable schema contracts for `agent-memory`.

## Schema Inventory

| Schema | Purpose | Standalone | Composable |
|---|---|---|---|
| `frontmatter.schema.yaml` | Required metadata for every durable document | Yes | Base layer |
| `knowledge-object.schema.yaml` | Multi-axis knowledge authority model | No | Extends frontmatter |
| `decision-record.schema.yaml` | ADR-specific fields (Why-First format) | No | Extends frontmatter |
| `lesson.schema.yaml` | LL-XXX 7-slot template + 5 quality gates | No | Extends frontmatter |
| `memory-index.schema.yaml` | Searchable index entry structure | Yes | Independent |
| `conversation-summary.schema.yaml` | LSM compaction summary segment | No | Extends frontmatter |
| `module-config.schema.yaml` | Module configuration (backend, search, features) | Yes | Independent |

## Composition Rules

1. **Every durable document** uses `frontmatter.schema.yaml` as its base. The required fields (`id`, `title`, `doc_kind`, `created`, `schema_version`) are mandatory in all document frontmatter.

2. **Knowledge-carrying documents** (decisions, lessons, validated notes) add the `knowledge:` block from `knowledge-object.schema.yaml`. This block is optional — add it when the document represents durable knowledge that needs authority tracking, lifecycle management, or export control.

3. **Document-type schemas** (`decision-record.schema.yaml`, `lesson.schema.yaml`, `conversation-summary.schema.yaml`) extend frontmatter with type-specific fields. They do not redefine frontmatter fields — they add to them.

4. **Infrastructure schemas** (`memory-index.schema.yaml`, `module-config.schema.yaml`) are standalone. They define operational structure, not document content.

## Which doc_kinds require the `knowledge:` block?

| doc_kind | `knowledge:` block | Reason |
|---|---|---|
| `decision` | Recommended | Decisions are durable knowledge with authority lifecycle |
| `lesson` | Recommended | Lessons are durable knowledge with evidence anchors |
| `summary` | Optional | Summaries may or may not be promoted to durable knowledge |
| `spec` | Optional | Specs become knowledge when validated |
| `note` | Optional | Notes become knowledge only when promoted |
| `bug-report` | Not typical | Bug reports are incident records, not reusable knowledge |
| `review` | Not typical | Reviews are workflow artifacts |

## Validation Contract

- `metadata-enforce` will use these files as the source of truth for document checks
- Phase 9 adds automated validation coverage
- Until automated validation exists, these schema files are the normative contract for templates and durable docs
