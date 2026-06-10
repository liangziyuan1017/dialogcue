# Project Guidelines

## Behavioral Rules

### 1. Think Before Coding
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First
- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

### 3. Surgical Changes
- Touch only what you must. Clean up only your own mess.
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.
- Remove imports/variables/functions that YOUR changes made unused.
- Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution
- Transform tasks into verifiable goals.
- For multi-step tasks, state a brief plan with verification checkpoints.
- Strong success criteria let you loop independently.

## Memory-First Rule

Before making design/architecture decisions, the agent MUST consult durable project memory. The specific hook points are defined in `registry/capabilities.yaml` under `clowder_dev_workflows.memory_hooks`.

1. If a prior decision exists on the same topic and is `status: accepted`, respect it — do not re-decide without explicit Human override.
2. If a prior lesson exists for the same pitfall, follow its guard — do not repeat the mistake.
3. After making a new decision that affects future work, persist it via the decision-record mechanism.
4. After encountering and recovering from a failure, persist the lesson.

## Architecture

See `AGENTS.md` in the project root for the agent runtime guide — it defines the deterministic navigation architecture using `registry/capabilities.yaml` → modules → skills → workflows → scripts.

See `modules/module_architecture.md` for the full module design.

Key project directories:
- `registry/capabilities.yaml` — Capability routing
- `modules/` — Execution modules with skills, workflows, scripts
- `global_skills/` — Cross-cutting methodology tools
- `data/` — Data processing pipeline scripts
