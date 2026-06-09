# Anti-Drift Protocol

> Normalized from clowder-ai F046 (Anti-Drift Protocol).
> Prevents agents from drifting away from the project's vision and standards.

## The Drift Problem

Agents working autonomously can drift:
- Feature implementation diverges from the original vision
- Code style shifts as different agents touch the same files
- Decisions made in isolation contradict earlier architectural choices
- "It works" replaces "it matches the spec"

## Three Anti-Drift Gates

### Gate 1: Vision Alignment
Before starting work on a feature:
- Re-read the feature spec (`docs/features/FXXX-*.md`)
- Confirm understanding of the acceptance criteria
- If the spec is unclear or missing → ask before proceeding

### Gate 2: Decision Consistency
Before making a design choice:
- Search memory for existing decisions in the same domain
- If a prior decision conflicts → challenge it with evidence, don't silently override
- Record new decisions with Why-First format and link to related ADRs

### Gate 3: Implementation Fidelity
After completing work:
- Verify every acceptance criterion is met with evidence
- Run the `governance-review` skill to check against first principles
- Update the feature doc with current status

See also: `first-principles.md` P5 (Verifiable = done), `shared-rules.md` Rule 6 (Evidence-before-claim).

## Cold-Start Verification

When verifying a deliverable, use a "cold" perspective:
- Read the output as if you've never seen the project before
- Can you understand what was built and why?
- Are the design decisions visible and traceable?
- Would another agent be able to pick up this work without asking the human?

## Drift Detection Signals

| Signal | What It Means | Response |
|--------|---------------|----------|
| Feature doc hasn't been updated in 3+ sessions | Agents are building without tracking | Pause. Update the doc. |
| Same bug appears twice | The lesson wasn't captured | Capture LL-XXX with executable guard. |
| Agent asks "should I continue?" | Vision is unclear or agent is unsure of direction | Re-read the vision. Clarify with human if needed. |
| Work output doesn't reference any ADR | Decisions are being made in isolation | Search memory. Link to existing decisions or create new ones. |
