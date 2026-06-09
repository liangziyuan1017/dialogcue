# agent-tool Capability Registration

> **Phase 10**: Defines how `agent-memory` capabilities are registered in `agent_tool`'s capability registry.

## Registry Entry

Add this entry to `registry/capabilities.yaml`:

```yaml
- capability: agent_memory
  module_path: modules/agent-memory/
  router: modules/agent-memory/router.md
  description: >
    Search, record, and manage durable project memory including decisions,
    lessons learned, conversation summaries, and governed knowledge.
    Supports cold-start memory bootstrap and non-destructive pruning.
  scope: project
  skills_count: 9
  key_triggers:
    - search memory
    - record decision
    - capture lesson
    - bootstrap memory
    - prune memory
```

## Capability Family

`agent_memory` is a **single capability family** registered as one top-level entry. The router inside the module dispatches to the 9 specific skills:

| Skill | Router Key | Primary Trigger |
|---|---|---|
| `memory-search` | Search durable project memory | "search memory" |
| `decision-record` | Record a durable architecture decision | "record this decision" |
| `lesson-capture` | Capture a durable lesson learned | "capture lesson" |
| `metadata-enforce` | Validate document frontmatter | "check metadata" |
| `memory-index` | Build or rebuild memory index | "rebuild index" |
| `memory-summarize` | Generate conversation summaries | "summarize conversation" |
| `governance-review` | Review against rules and principles | "governance review" |
| `memory-bootstrap` | Bootstrap memory for a project | "bootstrap memory" |
| `memory-prune` | Prune stale memory non-destructively | "prune memory" |

## Registration Rules

- The registry entry must NOT contain implementation details, workflow steps, or script references.
- The registry entry is routing-only: capability name → module path → router.
- The `key_triggers` field helps the runtime match user intent to capabilities but is advisory — the router determines the actual dispatch.
- If `agent_memory` is removed from the registry, the module remains intact and could be registered by any other host.
