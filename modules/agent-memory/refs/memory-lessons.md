# Operational Lessons — Single Bank, Tombstone GC, Fail-Closed Defaults

> Normalized from clowder-ai ADR-005 (Hindsight Integration Decisions).
> Critical operational patterns extracted from the Hindsight memory system experience.

## Single Bank Strategy

- **One memory bank per project** — not per-agent.
- All agents share the same memory. No knowledge silos.
- Filtering is done via tags and metadata, not by creating separate banks.
- This prevents the "agent A made a decision that agent B cannot understand" problem.

## Tombstone Garbage Collection

- **Delete = soft tombstone**, never physical erase.
- **90-day retention** before physical deletion.
- Audit log records: `document_id`, original tags, deletion reason, deletion timestamp.
- **Purpose**: Prevents old syncs from re-importing deleted content. Git history is the ultimate backup.

## Fail-Closed Defaults

- Only **archived, stable** content enters the searchable memory index.
- In-progress discussions, drafts, and speculative content stay out by default.
- Discussion documents can opt in with an explicit `indexable: true` flag — but this is reserved, not active by default.
- **Rule**: When uncertain whether content should be indexed → do not index. Fail closed.

## Evidence-First Culture

- **"Check memory first"** as a prompt constraint for agents.
- Before answering a question about project history, decisions, or patterns → search memory.
- **Audit**: Track whether agents searched memory before answering.
- After 2 weeks: if memory search hit rate < 50%, escalate to forced pre-answer search.

## Knowledge Capture Gate

After significant discussions, run the "precipitation check":
1. Should any conclusion become an ADR? → `decision-record` skill
2. Should any mistake become a lesson? → `lesson-capture` skill
3. Should any pattern become a rule? → Update `shared-rules.md`
4. If none of the above — was the discussion necessary?

## Import Strategy

| Content Type | Import Rule |
|-------------|-------------|
| Completed ADRs (`status: accepted`) | Import immediately |
| Completed phases | Import after phase close |
| Lessons (`status: validated`) | Import after passing all 5 quality gates |
| Discussions | Do NOT import (evidence layer only) |
| Draft documents | Do NOT import |

## Key Lesson

> "Your architecture decision, if it's only your memory, means other agents cannot judge whether it's a bug or a feature."

All decisions that affect how agents work together must be shared, searchable, and traceable.
