# agent-memory

An independent, reusable module that gives any agent system durable project memory — decisions, lessons learned, searchable knowledge, and cold-start bootstrap for new projects.

It does not assume a specific host. It works by keeping execution intelligence in files (router → skill → workflow → scripts), not in runtime improvisation.

---

## In One Paragraph

This module captures what a project has decided, what it has learned from mistakes, and what every agent working on it needs to know. Agents search this memory before acting. New agents bootstrap from it instead of starting cold. Knowledge is promoted from ephemeral to durable only with evidence. The module is portable: any host system that follows the router→skill→workflow→scripts chain can adopt it without changing its concepts.

---

## Included Scope (What This Module Does)

| Responsibility | Detail |
|---|---|
| **Decision records** | Create, update, search architecture and design decisions with Why-First format |
| **Lessons learned** | Capture lessons with root-cause analysis and executable guards (LL-XXX template, 7 slots, 5 quality gates) |
| **Memory search** | Hybrid retrieval: lexical (frontmatter parse) + optional semantic (embeddings) with RRF fusion |
| **Memory index** | Build/rebuild searchable index from project docs; hash-detect for incremental rebuild |
| **Conversation summaries** | LSM compaction: L0 real-time stitching → L1 periodic LLM summaries → append-only ledger |
| **Memory bootstrap** | Cold-start external projects: scan existing docs, build bootstrap summary, create index |
| **Memory pruning** | Knowledge lifecycle: detect stale, propose merge, validate entropy reduction |
| **Metadata enforcement** | Validate frontmatter compliance across all docs |
| **Governance review** | Check work against first principles (axioms + worldview + operational rules) |

## Excluded Scope (What This Module Does NOT Do)

| Non-Goal | Why It's Out |
|---|---|
| **Chat / conversation engine** | The module consumes summaries, not raw messages |
| **UI / dashboard** | Rendering is the host's responsibility |
| **Agent orchestration** | The host invokes skills; this module defines them |
| **Built-in database** | Abstracted behind `MemoryStore` interface; filesystem is default |
| **Runtime session management** | Sessions belong to the host; only durable knowledge enters this module |
| **Cross-project federation at runtime** | Cold-start and reflux are defined as workflows, not real-time services |
| **Authentication / authorization** | The host controls access |

## Deterministic Execution Chain

```text
registry/capabilities.yaml → router.md → skills/<name>/SKILL.md → workflows/<name>.md → scripts/<name>.py
```

- **Registry**: declares the module, its skills, and trigger keywords
- **Router**: capability map matching user intent to exactly one skill
- **Skill**: lean decision logic — when to use, when not to use, pointer to workflow
- **Workflow**: numbered execution steps, script references, document sync rules
- **Scripts**: tiny, deterministic, individually testable

## Source of Truth

- The source of truth is **human-readable documents** (`docs/decisions/*.md`, `docs/lessons/*.md`, `docs/features/*.md`)
- The search index is a **rebuildable artifact**, not a primary store
- Project memory is **durable**; agent/session memory is **ephemeral** until promoted
- New knowledge defaults to **low-authority** and is promoted only with evidence
- Compression (pruning, merging) is **non-destructive** — tombstones are preserved for 90 days

## Memory Classes

| Class | Purpose | Durability | Searchable | Promotion |
|---|---|---|---|---|
| Session memory | Scratch reasoning | Ephemeral | No | None |
| Conversation summary | Compact working context | Bounded durable | Optional | May become evidence |
| Project memory | Durable project knowledge | Durable | Yes | Native |
| Global methodology | Cross-project patterns | Durable | Yes | Review-gated |

## Module Structure

```text
agent-memory/
├── README.md                         ← This file
├── router.md                         ← Capability map
├── rules.md                          ← Invariants and constraints
├── working_file.md                   ← Runtime scratchpad (only writable file)
├── refs/                             ← Reference documents (de-cat-afied)
├── schemas/                          ← JSON/YAML schemas for all knowledge types
├── templates/                        ← Document templates
├── skills/                           ← 9 skills
├── workflows/                        ← 9 workflows
├── scripts/                          ← Deterministic scripts
├── adapters/                         ← Host system adapters
├── fixtures/                         ← Test fixtures
└── tests/                            ← Per-skill tests
```

### Structural Classification

The base architecture in `modules/readme.md` defines the execution chain: `registry → router → skills → workflows → scripts`. The additional directories in this module are classified as follows:

| Category | Directories | Role |
|---|---|---|
| **Execution chain** | `router.md`, `skills/`, `workflows/`, `scripts/` | Deterministic navigation and execution |
| **Supporting material** | `refs/`, `schemas/`, `templates/` | Read by skills/workflows at design time; not part of runtime chain |
| **Host integration** | `adapters/` | Read by host system at install time; not part of module core |
| **Verification** | `fixtures/`, `tests/` | Read by test runner; proves determinism |
| **Runtime state** | `working_file.md` | Only writable file during runtime; tracks external impact |
| **Module contract** | `README.md`, `rules.md` | Define module boundary and constraints |

No execution logic may reside in supporting material, host integration, or verification directories.

## Adoption

See `adapters/` for host-specific integration guides. To adopt this module in any host system, write an adapter following the contract in `adapters/generic/README.md`.

For the full integration plan, see `temp/INTEGRATION-PLAN-v3.md`.

