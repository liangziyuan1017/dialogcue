# Generic Adapter

Host-neutral integration contract for the agent-memory module.

See [integration-contract.md](integration-contract.md) for the minimum contract any host system must satisfy to adopt this module.

## Purpose

This directory defines what a host system MUST provide to use agent-memory, without assuming any specific host runtime, registry format, or trigger mechanism.

## Files

| File | Purpose |
|---|---|
| `integration-contract.md` | Minimum adapter contract: required capabilities, optional services, bootstrapping steps |
| `README.md` | This file |

## Relationship to agent-tool adapter

The `adapters/agent-tool/` directory is a concrete implementation of this contract for the `agent_tool` host system. Other hosts should follow the same contract pattern.
