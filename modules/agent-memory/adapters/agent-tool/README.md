# agent-tool Adapter

Host-specific integration files for mounting `agent-memory` into `agent_tool`.

## Files

| File | Purpose |
|---|---|
| `capability-registration.md` | Registry entry shape and registration rules |
| `trigger-mapping.yaml` | User intent → skill trigger phrases (9 skills) |
| `path-conventions.md` | Document roots, index paths, working file usage |

## Design Principle

The adapter is a **boundary layer**. It translates between the host (`agent_tool`) and the module (`agent-memory`). The module core must not know about the adapter. Removing `adapters/agent-tool/` should leave the module fully intact and usable by any other host that writes its own adapter.

## Adapter Responsibilities

1. **Register** the `agent_memory` capability in `agent_tool`'s registry
2. **Map** user trigger phrases to module skills (trigger-mapping.yaml)
3. **Define** where docs, indexes, and locks live (path-conventions.md)
4. **Do NOT** inject host logic into module scripts, workflows, schemas, or rules

