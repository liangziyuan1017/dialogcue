# agent-tool Path Conventions

> **Phase 10**: Defines where `agent-memory` reads and writes files when hosted inside `agent_tool`.

## Document Roots

| Purpose | Path (relative to `agent_tool` project root) | Notes |
|---|---|---|
| **Durable decisions** | `docs/decisions/` | ADR-XXX.md files |
| **Durable lessons** | `docs/lessons/` | LL-XXX.md files |
| **Durable summaries** | `docs/summaries/` | SUM-YYYYMMDD-HHMM-<slug>.md files |
| **Durable proposals** | `docs/proposals/` | MP-<timestamp>-<slug>.md files |

These paths are **configurable per host** via the adapter. The module assumes `docs/` as the default but the adapter can remap.

## Compiled Artifacts

| Purpose | Path (relative to `agent_tool` project root) |
|---|---|
| **Searchable index** | `src/.agent-memory/index.json` |
| **ID allocator state** | `src/.agent-memory/state/id-allocator.json` |
| **Index state** | `src/.agent-memory/state/index-state.json` |
| **Tombstones** | `src/.agent-memory/tombstones/` |
| **Lock files** | `src/.agent-memory/locks/` |

## Module Internal Paths

| Purpose | Path (relative to `agent_tool` project root) |
|---|---|
| **Module root** | `modules/agent-memory/` |
| **Router** | `modules/agent-memory/router.md` |
| **Rules** | `modules/agent-memory/rules.md` |
| **Working file** | `modules/agent-memory/working_file.md` |
| **Scripts root** | `modules/agent-memory/scripts/` |

## working_file.md Usage

During runtime, `modules/agent-memory/working_file.md` is the only writable file inside the module. It tracks:

- External runtime impact (files created, modified, or tombstoned in `docs/`)
- Pending reindex flags
- Active lock holders (for debugging)
- Last bootstrap timestamp

The working file is **not** durable memory. It is scratch space for the current session. It should be cleared or archived between sessions.

## Reindex Strategy

Default: **explicit reindex after each successful durable write.**

Controlled by `schemas/module-config.schema.yaml`:
```yaml
features:
  auto_index_on_change:
    default: true
```

When `auto_index_on_change: true`:
- After every `write-durable` → run `index-rebuild --scope incremental`
- After every `memory-prune` batch → run `index-rebuild --scope full`

When `auto_index_on_change: false`:
- Reindex only on explicit "rebuild index" triggers.

## Fallback Behavior

| Missing Service | Behavior |
|---|---|
| Embedding service unreachable | `memory-search` degrades to lexical-only; search still works |
| LLM summarization unavailable | `memory-summarize` skips L1 generation; returns "not eligible" |
| `.agent-memory/` directory missing | Created on first write; no manual setup needed |
| Lock acquisition timeout (30s) | Operation fails with clear error; no silent corruption |
