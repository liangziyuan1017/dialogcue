<!--
  ROUTER FILE — Module-Level Routing Layer
  Purpose: Map capability IDs to their corresponding skill files.
  This file contains ROUTING INFORMATION ONLY.
  It must NOT contain implementation details, execution logic, or embedded behavior rules.
  The runtime reads this file to determine which skill to invoke for a given capability.
  If no entry matches the task, the agent falls back to its own operations.
-->

# agent-memory Router

## capability_flow
<!--
  SECTION PURPOSE: Shows how capabilities compose and depend on each other.
  The agent can use this to understand what must run before what.
  This is a dependency guide, not an execution order.
-->
```
Phase 1  (Initialize):  memory-bootstrap ──→ memory-index
                              ↓
Phase 2  (Create):       decision-record ──┐
                         lesson-capture ────┼──→ index-rebuild (incremental)
                         memory-summarize ──┘
                              ↓
Phase 3  (Maintain):     memory-prune ──────→ index-rebuild (full)
                              ↓
Phase 4  (Query):        memory-search (reads stable index)
---
Any time (Validate):     governance-review, metadata-enforce
```

## capability_map
<!--
  SECTION PURPOSE: Each entry maps a stable capability ID to the skill
  file that contains the routing logic. Routing table includes decision
  columns so the agent can resolve the correct skill without reading
  every SKILL.md. No implementation details here.
-->
| capability_id | skill_path | Description | Use When | Not For | Output | Triggers |
|---|---|---|---|---|---|---|
| `memory-search` | `skills/memory-search/SKILL.md` | Search durable project memory for prior decisions, lessons, summaries, and validated knowledge | Agent needs historical project context before acting; task asks what the project already decided, learned, or documented | Creating new durable knowledge; validating metadata compliance | Ranked memory results with source anchors | "search memory", "find decision", "recall", "what did we decide about" |
| `decision-record` | `skills/decision-record/SKILL.md` | Record or update a durable architecture or design decision in Why-First format | A project decision should become durable memory for future agents; future agents will need the reasoning behind a choice | Lessons from failures; metadata-only validation | A durable decision record with frontmatter and decision rationale | "record this decision", "create ADR", "architecture decision", "document this choice" |
| `lesson-capture` | `skills/lesson-capture/SKILL.md` | Capture a durable lesson learned from an error, repeated failure, or recovered mistake | A failure pattern should not be repeated by future agents; a repeated pitfall needs a documented guard | Recording planned design choices; generic note-taking | A durable lesson record with source anchors and prevention guidance | "lesson learned", "don't repeat this", "capture that mistake", "capture lesson" |
| `metadata-enforce` | `skills/metadata-enforce/SKILL.md` | Validate document frontmatter and metadata compliance across durable memory files | Durable memory documents need compliance checking; frontmatter drift or missing fields must be reported | Creating new decisions, lessons, or search queries | A metadata validation report with missing or invalid fields | "check metadata", "validate frontmatter", "are docs compliant", "frontmatter lint" |
| `memory-index` | `skills/memory-index/SKILL.md` | Build or rebuild the searchable memory index from durable project documents | Durable memory has changed and retrieval must be refreshed; an explicit rebuild is requested | Cold-starting a new repo; directly answering a recall question | An index rebuild report for durable memory artifacts | "rebuild index", "index docs", "reindex", "build index" |
| `memory-summarize` | `skills/memory-summarize/SKILL.md` | Generate durable conversation summaries from stable source material | A conversation has enough stable context to compact; durable summary memory is needed for future agents | Summarizing a single message; summarizing an existing summary (rules.md §7) | A durable summary segment with provenance | "summarize conversation", "generate thread summary", "conversation summary" |
| `governance-review` | `skills/governance-review/SKILL.md` | Review work against module principles, boundaries, and governance rules | Proposed work should be checked against durable memory policy and first principles; a change needs policy or principle review | Creating new rules or capturing new project knowledge | A governance review report with violations, cautions, or passes | "check against principles", "governance check", "is this aligned", "principle check" |
| `memory-bootstrap` | `skills/memory-bootstrap/SKILL.md` | Bootstrap durable memory for a new or external project from existing stable artifacts | A project has no memory index yet; agents need durable starting context for a repo they have not worked in before | Incremental index refreshes; routine search | A bootstrap summary plus initial durable memory setup state | "bootstrap memory", "cold start project", "expedition memory", "initialize memory" |
| `memory-prune` | `skills/memory-prune/SKILL.md` | Prune, merge, or deprecate stale durable memory without destructive deletion | Duplicate, stale, or invalidated knowledge should be compacted safely; a safe merge or deprecation review is needed | Deleting active knowledge; rewriting project history without audit | A prune report with non-destructive lifecycle actions | "prune memory", "reduce entropy", "clean up knowledge", "stale docs", "deprecate" |

## fallback_rule
<!--
  SECTION PURPOSE: Defines what happens when no capability in this module matches the task.
  The agent must stop using this module and fall back to its own operations.
-->
- If no capability above matches the task, do NOT read any other file in this module.
- Rely on the host runtime or another matching module.
- This module only handles memory, decisions, lessons, and governance.
