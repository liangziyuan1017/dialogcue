# Generic Adapter — Integration Contract

This file defines the **minimum contract** any host system must satisfy to adopt the `agent-memory` module. It is host-neutral by design.

## Required Capabilities

A host must provide:

| Capability | Description |
|---|---|
| **Capability registry** | A way to register the `agent_memory` capability and route to its router |
| **Router dispatch** | Read `router.md` capability_map and dispatch to the correct skill |
| **Skill execution** | Read `SKILL.md` frontmatter, validate triggers, follow workflow pointer |
| **Workflow execution** | Read `workflow/*.md`, execute commands from `scripts/` in order |
| **File I/O** | Write durable docs to a configurable `docs/` root; read/write `.agent-memory/` artifacts |
| **Lock mechanism** | File-based lock support (O_CREAT\|O_EXCL), or equivalent atomic allocation |
| **Python runtime** | Python 3.10+ for script execution |

## Optional Services

| Service | Required? | Fallback |
|---|---|---|
| Embedding service | No | Degrades to lexical-only search |
| LLM summarization | No | L1 summaries skipped; "not eligible" returned |

## Adapter Contract

Every host adapter must define:

1. **Where durable docs live** — `docs/decisions/`, `docs/lessons/`, `docs/summaries/` (or mapped equivalents)
2. **Where compiled artifacts live** — `.agent-memory/` (index, state, locks, tombstones)
3. **Which triggers map to which skills** — host-specific trigger phrases
4. **Reindex strategy** — explicit (after each write) or debounced

## What the Adapter Must NOT Do

- Modify any file under `schemas/`, `templates/`, `refs/`, `scripts/`, `workflows/`, `skills/`, or `rules.md`
- Inject host-specific logic into scripts (use environment variables or config)
- Change module naming conventions
- Bypass the deterministic chain: registry → router → skill → workflow → scripts

## Bootstrapping a New Host Adapter

1. Copy `adapters/agent-tool/` as a template
2. Rewrite `capability-registration.md` for your host's registry format
3. Rewrite `trigger-mapping.yaml` with your host's trigger phrases
4. Rewrite `path-conventions.md` with your host's directory layout
5. Verify: core module files are untouched

