# Governance Structure

> Normalized from clowder-ai ADR-012 first-principles map.
> Defines how rules, decisions, and lessons are organized and enforced.

## Three-Layer Governance

```
Layer 1: Axioms (P1-P5)       ← Immutable truths. Defined once. Never duplicated.
Layer 2: Worldview (W1-W8)     ← Shared beliefs. Shape operational rules.
Layer 3: Operational Rules     ← Concrete rules derived from axioms + worldview.
```

## Truth Sources

| What | Where | Notes |
|------|-------|-------|
| Rules | `refs/shared-rules.md` | Single source. All other files reference, don't redefine. |
| Decisions | `docs/decisions/ADR-XXX.md` | Architecture Decision Records with Why-First format. |
| Lessons | `docs/lessons/LL-XXX.md` | 7-slot template with 5 quality gates. |
| Features | `docs/features/FXXX-*.md` | Feature specs with acceptance criteria. |
| Discussions | `docs/discussions/` | Evidence layer — not the definition layer. |
| Index | Rebuildable artifact | Compiled from docs/. Source of truth is docs/, not the index. |

## Enforcement Layers

| Layer | Mechanism | When |
|-------|-----------|------|
| Prompt-level | Rules loaded into agent system prompts | Every session |
| Skill-level | `governance-review` skill checks work against principles | On explicit trigger |
| Gate-level | Quality gates block promotions without evidence | Before acceptance |
| Human-level | Escalation after 2 rounds of unresolved challenge | On deadlock |

## Key Invariants

1. **No rule duplication**: A rule defined in `shared-rules.md` is not redefined in any other file. Other files reference it by path or ID.
2. **Evidence before claim**: No assertion of completion, correctness, or fix without verifiable evidence produced in the current session.
3. **Fail-closed on uncertainty**: When uncertain whether to export, promote, or act → default to the safer option (don't export, don't promote, don't act).
4. **Progressive disclosure**: Knowledge is loaded based on authority and activation, not dumped all at once. Constitutional + always_on in system prompt; advisory + dormant in archive.
