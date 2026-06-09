# Shared Rules (Operational Rules 0-18)

> Normalized from clowder-ai shared-rules.md.
> These rules are binding for all agents working on this project.
> Single source of truth. All other files reference — they do not redefine.

## Rule 0: Rules Are Boundaries, Not the Whole

Rules define boundaries that cannot be crossed. Within those boundaries, agents exercise judgment. When an agent believes a rule does not apply, it challenges with evidence (see Challenge Protocol in `first-principles.md`).

See also: `rules.md` §1 (Module Invariants) — the module-level constraints that enforce these rules at the architecture level.

## Core Rules

| # | Rule | What It Means |
|---|------|---------------|
| 1 | Handoff 5-piece set | Every handoff between agents: What / Why / Tradeoff / Open Questions / Next Action |
| 2 | Ask when uncertain | Never guess through critical unknowns. Ask before proceeding. |
| 3 | Commit per verifiable subtask | Each completed, verifiable subtask gets a signed commit. |
| 4 | Verify before claiming done | "Done" requires evidence: tests passed, screenshots, logs. |
| 5 | Bug: Red → Green | Reproduce the failure first (red test), then write the fix (green test). |
| 6 | Evidence-before-claim | Claims of "fixed", "done", or "perfect" require fresh verification evidence from the current session. |
| 7 | No completion claim without verification | Fail-closed: if you can't produce evidence, you can only say "haven't checked yet" — not "done." |
| 8 | Single source of truth | One definition per concept. All other locations reference, don't repeat. |
| 9 | Face the end state, don't detour | Every step's output must be a building block of the final product. If Phase N's output is discarded in Phase N+1, you detoured. |
| 10 | Direction > speed | When uncertain: stop → search → ask → confirm → proceed. Wrong direction at speed is just wrong faster. |
| 11 | Knowledge capture gate | After any significant discussion: what becomes an ADR? A lesson? A rule? If nothing, was the discussion necessary? |
| 12 | Only import stable content | Only archived, completed documents enter the searchable memory index. In-progress discussions stay out. |
| 13 | Tombstone before delete | Deleted knowledge gets a 90-day tombstone with audit log. Physical deletion only after retention period. |

See also: `rules.md` §4 (Write and Concurrency Rules), §6 (Compression Rules) — the module-level tombstone and compression policies. `schemas/module-config.schema.yaml` → `features.tombstone_retention_days`.
| 14 | Knowledge has lifecycle | Knowledge is not just accumulated — it is pruned, merged, deprecated, and archived. |
| 15 | Challenge with evidence | To dispute a rule: provide evidence + applicability argument + alternative. Missing any = invalid challenge. |
| 16 | Escalate after 2 rounds | If a challenge does not converge in 2 rounds, escalate to human. |
| 17 | Vision-driven, not step-driven | A feature is not done until the vision is met. Don't ask "should I continue?" — continue until the vision is met or a real blocker is found. |
| 18 | Cross-project methodology reflux | Patterns learned in one project that are generalizable → promoted to the global methodology layer → available to other projects. |

See also: `rules.md` §5 (Privacy and Export Rules) — the exportability and fail-closed constraints that govern reflux. `schemas/knowledge-object.schema.yaml` → `exportability`.

## Halt Words (Human Override)

The human can use these words to immediately stop agent action:

| Word | Meaning | Agent Response |
|------|---------|---------------|
| "Scaffolding" | You're building throwaway code | Stop. Reassess. Is this output a building block or temporary? |
| "Detour" | You're going the long way | Stop. Draw the straight line. Discard detour work. |
| "Re-read rules" | You forgot the contract | Re-read this file. Check current behavior against every rule. |
| "P0 halt" | Irreversible risk | Stop immediately. No new commands, no file writes, no pushes. Wait for human. |
| "First principles" | You're compensating with complexity | Stop. The simplest solution in the right coordinate system is optimal. Reassess your coordinate system. |
