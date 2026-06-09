# Standard Operating Procedures

> Normalized from clowder-ai SOP.md.
> Vision-driven development workflow for multi-agent projects.

## Core Principle: Vision-Driven

Development is **vision-driven**, not step-driven. Once the human confirms a feature's vision:

See also: `first-principles.md` P1 (Face the end state), P3 (Direction > speed), `governance-structure.md` (vision ownership).

- **Vision not met = not done.** Continue until the vision is achieved. Don't stop to ask "should I continue?"
- **The only valid stop reason**: A genuinely unsolvable blocker is discovered (technical limitation, external dependency unavailable). Escalate to human.
- **SOP steps auto-advance.** The full chain runs to closure without asking for permission at each step.

## The 5-Step Flow

```
Design Gate → Worktree → Quality Gate → Review Cycle → Merge Gate → Vision Guard
```

### 0. Design Gate
- UX decisions → confirmed by human
- Architecture decisions → confirmed by agent team
- Cross-cutting concerns → both sides confirm

### 1. Worktree
- Isolate development in a separate workspace
- Never modify `main` directly for non-trivial changes
- Exception: documentation-only changes (≤ 5 lines)

### 2. Quality Gate
- Self-check before requesting review
- Vision alignment: does this match the spec?
- Test evidence: all tests pass with fresh output
- Spec compliance: every acceptance criterion addressed

### 3. Review Cycle
- Submit for agent peer review
- Red → Green: every issue found gets fixed, not debated
- P1/P2 issues cleared in the current round

### 4. Merge Gate
- All reviews passed
- Tests green on the worktree
- Squash merge to main
- Clean up the worktree

### 5. Vision Guard
- A non-author agent verifies the merged result
- Vision three questions:
  1. Does this deliver what was promised?
  2. Are the acceptance criteria all met with evidence?
  3. Would the human recognize this as their vision?
- Pass → close feature. Fail → kick back to development.

## Large Feature Checkpoint (3+ Phases)

For large features spanning multiple phases, after each phase merge:
1. **Show results**: What was built this phase (key changes, demo)
2. **Vision progress**: Which acceptance criteria are done, which remain
3. **Next direction**: What's planned for the next phase, any new discoveries
4. **Direction confirm**: "Is the direction correct? Any adjustments needed?"

This is NOT "should I continue?" — it's "is the direction right?"

## Small Features (1-2 Phases)

No checkpoint needed. Run the full chain to completion → vision guard → close.

## Halt Protocol

The human can halt agent action at any time using halt words (see `shared-rules.md`). Agents must:
1. Stop immediately
2. Preserve current state
3. Wait for human instruction

## Verification Rules

- Every "done" claim requires evidence produced in the current session
- Test output, screenshots, and logs are the minimum acceptable evidence
- "It should work" = "haven't checked yet"
- Fail-closed: uncertain → not done
