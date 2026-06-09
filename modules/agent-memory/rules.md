<!--
  RULES FILE — Module-Specific Constraints
  Purpose: Define module-wide constraints and invariants.
  Phase 3 status: All invariants, boundaries, and policies are defined. No workflow steps in this file.
-->

# agent-memory Rules

## 1. Module Invariants (Always True)

- **Host-agnostic core**: The module must work for any host system that follows the router→skill→workflow→scripts chain. No host-specific logic in core files.
- **Deterministic navigation**: registry → router → skill → workflow → scripts. Every step is inspectable. No hidden dispatch.
- **Files are execution intelligence**: Workflow steps, decision logic, and constraints live in files. The agent reads and executes — it does not improvise.
- **Single writable file**: During runtime, only `working_file.md` is writable inside this module. All durable output goes to the host project's `docs/`.
- **Source of truth is documents**: `docs/` files are the primary store. The index is a rebuildable artifact. If they disagree, documents win.

Mechanical enforcement: `schemas/frontmatter.schema.yaml` defines `doc_kind` and `status` enums that constrain document types. `schemas/module-config.schema.yaml` → `features.auto_index_on_change` controls index rebuild behavior.

## 2. Memory Boundaries

### 2.1 What enters project memory
- ADRs and decision records with frontmatter
- Lessons learned with source anchors (at least 1, recommended 2)
- Validated feature or architecture facts
- Project summaries generated from stable sources
- Conversation summaries that passed a promotion gate

### 2.2 What does NOT enter automatically
- Raw chat transcripts
- Speculative ideas without evidence
- Unfinished disagreements
- Tool execution logs
- Private project details marked non-exportable

### 2.3 Promotion gate
Conversation content becomes durable only when converted to one of:
- `decision` (ADR)
- `lesson` (LL-XXX)
- `project-summary`
- `validated-note`

Until promoted, it remains ephemeral session memory.

## 3. Knowledge Authority Model

Knowledge has three orthogonal axes inside the `knowledge:` block:

| Axis | Values | Meaning |
|---|---|---|
| `authority` | `observed` → `candidate` → `validated` → `constitutional` | How trusted is this? |
| `activation` | `query` → `scoped` → `always_on` → `backstop` | When is it loaded? |
| `status` | `active` → `review` → `invalidated` → `archived` | Is it current? |

Rules:
- New knowledge defaults to `observed + query + active`
- Only human-reviewed flow can create `constitutional` or `always_on`
- `backstop` = preserved but not prominent in default search
- `invalidated` entries retain tombstones for 90 days
- Superseded entries point to their replacement via `replaced_by`

Mechanical enforcement: `schemas/knowledge-object.schema.yaml` defines all three axes with enums and defaults. Changing a default there changes the behavior described here.

### 3.1 Document status vs. knowledge status

The module uses two separate status layers:

- **Document frontmatter `status`** tracks document workflow state:
  `draft | review | accepted | deprecated | superseded | archived`
- **`knowledge.status`** tracks lifecycle state of durable knowledge:
  `active | review | invalidated | archived`

Rules:
- Do not treat document `status` and `knowledge.status` as interchangeable.
- `superseded` is a document-level state; it is expressed in knowledge metadata through `replaced_by`, not as a `knowledge.status` value.
- Validators and workflows must read the correct layer for the question they are answering.

## 4. Write and Concurrency Rules

- **Append-first**: All writes are append operations. No in-place mutation without audit.
- **Optimistic concurrency**: Updates check `updated` timestamp + content hash. Conflicts are reported, not silently overwritten.
- **Tombstone, never hard delete**: Deletes are soft tombstones with reason + audit log. Physical deletion only after 90-day retention.
- **Serialized index rebuilds**: Index rebuilds are serialized per project. Two rebuilds cannot run concurrently.

Mechanical enforcement: `schemas/module-config.schema.yaml` → `features.tombstone_retention_days: 90`. `schemas/memory-index.schema.yaml` → `content_hash` enables change detection for optimistic concurrency.

## 5. Privacy and Export Rules

- Every knowledge entry declares `exportability`: `private`, `project_only`, or `generalized`
- `contains_sensitive_data: true` prevents auto-export to global methodology layer
- Cross-project reflux only promotes `generalized` entries
- Privacy violations are fail-closed: uncertain → do not export

Mechanical enforcement: `schemas/knowledge-object.schema.yaml` → `exportability` enum with `default: project_only` and `contains_sensitive_data: boolean`.

## 6. Compression Rules (Non-Destructive)

- Pruning a document creates a tombstone, not a deletion
- Merging documents preserves `source_ids` referencing the originals
- Documents marked `deprecated` or `superseded` remain searchable as historical records
- Durable knowledge that is no longer current should move to `knowledge.status: invalidated` or `knowledge.status: archived`, depending on lifecycle intent
- Stale detection runs on `review_cycle_days` (default: 90)
- Entropy reduction must be validated before execution

Mechanical enforcement: `schemas/knowledge-object.schema.yaml` → `review_cycle_days: default: 90`, `stale_after_days: default: 90`. `schemas/frontmatter.schema.yaml` → `status_enum` includes `deprecated` and `superseded`.

## 7. No-Summary-of-Summary Rule

- **A summary must never be the input to another summary.**
- Summaries are generated from original source material only (messages, documents).
- Re-summarizing a summary compounds drift — each generation loses fidelity.
- If a summary is outdated, discard it and generate a fresh summary from the original source material.
- The append-only `summary_segments` ledger preserves all historical summaries. New summaries append; they do not overwrite or re-summarize old ones.

Mechanical enforcement: `schemas/conversation-summary.schema.yaml` → `is_summary_of_summary: const: false`.

## 8. Schema Versioning

- All documents declare `schema_version` in frontmatter
- Migration scripts are idempotent and versioned
- Breaking schema changes require a migration plan before implementation
- Old schemas remain readable for one major version after deprecation

Mechanical enforcement: `schemas/frontmatter.schema.yaml` → `schema_version` is a required field.

## 9. Working File Tracking Rules

`working_file.md` is the only writable file inside this module during runtime. It is limited to:

**Allowed content:**
- Current phase and step in the execution chain (e.g., "Phase 3: Step 4 of memory-bootstrap workflow")
- References to external durable output paths (e.g., "Wrote ADR-025 to docs/decisions/025-database-choice.md")
- Temporary tracking state: current search query, current ADR ID, current lesson ID
- Blockers and next actions (e.g., "Blocked: waiting for human review of ADR-025")
- Error logs with timestamps and recovery actions

**Not allowed:**
- Durable knowledge content (that belongs in `docs/` files)
- Full conversation transcripts
- Agent reasoning or internal monologue
- Any content that should survive a module reset
- Workflow steps copied verbatim (reference them by path, don't duplicate)

**Host write targets:**

Durable output from this module is written to the host project's `docs/` directory:
- `docs/decisions/` — Architecture Decision Records (ADR-XXX)
- `docs/lessons/` — Lessons learned (LL-XXX)
- `docs/summaries/` — Conversation and project summaries
- `docs/features/` — Feature specifications (FXXX)
- `.agent-memory/` — Compiled index and adapter-owned state (rebuildable artifact)

The module never writes to `src/`, `scripts/`, or any other host directory.

**Lifetime:**
- `working_file.md` is ephemeral. It can be cleared between sessions.
- The only persistent record of execution is the durable output in the host project's `docs/`.
- After a phase completes, the agent should summarize what was done in durable output, then clear the working file.
