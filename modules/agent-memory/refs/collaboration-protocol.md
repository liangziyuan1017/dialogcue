# Collaboration Protocol — Why-First + Challenge

> Normalized from clowder-ai ADR-002 (Why-First Collaboration Protocol).
> Every handoff between agents follows this format.

## The Why-First Format

Every handoff, review request, plan change, or cross-agent communication must include:

| Element | Description | Required |
|---------|-------------|----------|
| **What** | The specific change, decision, or deliverable | Yes |
| **Why** | Constraints, goals, and risks that drove this choice | Yes |
| **Tradeoff** | Alternatives considered and why they were rejected | Yes |
| **Open Questions** | What is still uncertain? Who needs to answer? | If any |
| **Next Action** | What does the receiving agent do next? | Yes |

## When to Apply

- Task handoffs between agents
- Review requests
- Plan changes or scope adjustments
- Cross-agent status updates
- Any situation where one agent's output becomes another agent's input

## When NOT to Apply

- Simple status updates ("done, moving to next step")
- Trivial information passing that requires no decision
- Messages where the context is fully clear from the conversation flow

## The Challenge Protocol

When an agent believes a rule, decision, or instruction does not apply:

1. **Evidence**: Provide the code line, spec, ADR, lesson, or case that supports the challenge
2. **Applicability**: Explain why the rule does not apply to this specific situation
3. **Alternative**: Propose what should be done instead

**Rules**:
- Missing any of the three = invalid challenge. The other party can politely reject.
- After 2 rounds without convergence → escalate to human.
- This is a floor, not a ceiling. If the natural reasoning already covers equivalent information, no extra formatting is needed.

## Signed Commits

Every verifiable subtask gets a signed commit. The commit message identifies the responsible agent.

Format: `feat(scope): description [Agent]`

Example:
- `feat(memory): add hybrid search with RRF fusion [Architect]`
- `fix(index): handle hash collision on rebuild [Debugger]`

## Verification Environment

When handing off test results, service status, or verification claims, always include:
1. **Environment**: Where it was tested (local, sandbox, staging)
2. **Command**: The exact command that produced the output
3. **Evidence**: The actual output, not a summary of it
