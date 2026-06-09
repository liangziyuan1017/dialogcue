<!--
  WORKING FILE — Runtime Impact Tracker
  Purpose: The ONLY writable file inside this module during runtime.
  Tracks external impact of agent-memory capabilities on the host project.
  Phase 12 status: Module complete. All 9 capabilities are operational.
-->

# agent-memory Working File

## external_related_files

Durable documents written to host project:
- `docs/decisions/ADR-001-pre-decision-memory-check.md` — Architecture Decision Records
- `docs/lessons/LL-XXX.md` — Lessons Learned
- `docs/summaries/SUM-YYYYMMDD-HHMM-<slug>.md` — Conversation Summaries
- `docs/proposals/MP-<timestamp>-<slug>.md` — Proposals

Compiled artifacts:
- `.agent-memory/index.json` — Searchable memory index
- `.agent-memory/state/id-allocator.json` — ID allocation state
- `.agent-memory/state/index-state.json` — Index rebuild state
- `.agent-memory/tombstones/` — Tombstone records (90-day retention)
- `.agent-memory/locks/` — Concurrency lock files

## src_entrypoints

Host-owned entrypoints that invoke agent-memory capabilities:
- Host runtime reads `registry/capabilities.yaml` to discover this module
- Host runtime dispatches to capabilities via the module's router

## src_invocation_functions

Capability invocation chain (host-owned, adapter-defined):
1. `agent_memory` capability registered in host registry
2. Host reads `modules/agent-memory/router.md` → finds matching skill
3. Host reads `skills/<name>/SKILL.md` → confirms decision, gets workflow pointer
4. Host reads `workflows/<name>.md` → executes commands from `scripts/`

## src_output_targets

Output from each capability:
- **memory-search**: stdout (ranked results), no file writes
- **decision-record**: writes to `docs/decisions/`, triggers reindex
- **lesson-capture**: writes to `docs/lessons/`, triggers reindex
- **metadata-enforce**: stdout (compliance report), no file writes
- **memory-index**: writes to `.agent-memory/index.json`
- **memory-summarize**: writes to `docs/summaries/`, triggers reindex
- **governance-review**: stdout (review report), no file writes
- **memory-bootstrap**: writes to `.agent-memory/index.json` (initial)
- **memory-prune**: writes tombstones to `.agent-memory/tombstones/`, triggers full reindex
- Durable output targets will be recorded when document-writing workflows exist.

## src_affected_files

- `docs/decisions/ADR-001-pre-decision-memory-check.md` — created

## file_policy

- `working_file.md`: writable during runtime
- all other module files: read-only during runtime

## progress_notes

- **2025-07-17**: Human requested automatic pre-decision memory checking. Created ADR-001 documenting the commitment. From now on, Architect will search memory before any significant decision and summarize relevant findings.
