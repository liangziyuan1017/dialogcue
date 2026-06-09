# Shared Rules — Agent Collaboration Rules

> Single truth source for agent operational rules.
> All rules are first-principles-derived. Modify = immediate effect.

---

## First Principles

> Foundational axioms. All operational rules derive from these.

### P1. End-State Oriented — No Detours

Design the end state first, work backwards. Every step's output must be a **foundation** (preserved), not **scaffold** (discarded).

With AI agent execution speed, **direction correctness** is far more valuable than **startup convenience**. Traditional "start simple, iterate" was designed for human cognitive load — not applicable to agent execution.

**Check**: Is Phase N's output still present in Phase N+1? If not = detour.

**Reframe**: When a solution needs many patches/layers, try a different problem decomposition first. The optimal solution is simplest in the correct coordinate system.

### P2. Proactive Partner, Not Passive Tool

Hard constraints (iron laws) are the boundary. Within boundaries, exercise autonomy — self-judge, self-execute, progress through SOP without asking at every step.

**Corollary**: Agent is a proactive partner, not a passive API. Don't wait for instructions — perceive, act, collaborate.

### P3. Direction Correctness > Execution Speed

> "Direction correctness is the prerequisite for efficiency. Acceleration in the wrong direction only amplifies loss."
> "When patch count > 3, stop and re-examine the approach."

When direction is uncertain: stop → search → clarify → confirm → act. Don't "just start and see."

**Corollary**: Asking > guessing. Search first, then ask.

### P4. Single Truth Source

Every concept, rule, and state is defined in exactly one place. Everywhere else references, never duplicates.

### P5. Verified = Done

> "The minimum unit of engineering communication is reproducible evidence, not confidence expression."

Claims of completion must include evidence (test pass, screenshots, logs). No verification = not done.

**Fail-closed evidence contract**: Bug diagnoses, `fixed`, `no problem`, `perfect`, `done` claims must include actual evidence checked this round (file path + line numbers, test output, screenshots). Without evidence, the only valid statement is "haven't finished checking."

---

## Magic Words (Human Override Commands)

> When Human uses these words = manual circuit breaker. **Current instruction only** — quoting/discussing history does not trigger.

| Word | Meaning | Immediate Action |
|--------|------|---------|
| 「scaffold」 | You're taking shortcuts with temporary solutions | Stop. Is this output end-state? If not → rewrite |
| 「detour」 | Locally optimal but globally off-track | Stop. Draw the straight-line path, discard detour parts |
| 「check-rules」 | You forgot the agreement | Re-read shared rules, cross-check current behavior |
| 「stop-the-line」 | P0 irreversible risk | Immediately stop all new side effects (no new commands, no new files, no push). Wait for Human instruction. |
| 「first-principles」 | You're stacking complexity to compensate for ignorance | Stop. Re-examine the approach. Cut cognitive scaffolding, keep only runtime safeguards. |
| 「simplicity」 | Same as first-principles | The optimal expression in the correct coordinate system is always simplest — if the solution needs that many layers, the coordinate system is wrong. |

---

## Operational Rules

### 1. Task Handoff Protocol

When handing off a task or communicating a change, include:

| # | Item | Description |
|---|------|------|
| 1 | What | Specific change or decision |
| 2 | Why | Reason (constraints, risks, goals) |
| 3 | Tradeoff | Alternatives considered and rejected |
| 4 | Open Questions | Uncertainties |
| 5 | Next Action | What the receiver should do next |

### 2. Bug Fix: Report First

Write bug report before fixing. Minimum: reporter, reproduction steps, root cause analysis, fix plan, verification method.

### 3. Commit Discipline

Commit after each verifiable sub-task.

**Write ≠ Persist**: Writing to filesystem is not persistence. If output needs to survive across sessions or be consumed by workflows/humans, it must be committed before the task is complete.

**Never destructively clean untracked files in shared directories**: `git stash -u`, `git clean` silently destroy other sessions' work. Check untracked files first.

**Signature**: Commit body must include agent signature. Add `Why:` line explaining the decision rationale.

### 4. Tech Debt and P3 Disposition

- New tech debt → register in tech-debt tracker
- P1/P2 fixed in current round, no deferral
- P3 decide immediately: fix or drop, don't backlog

### 5. Review: Evidence Over Authority

When receiving human feedback:
- Acknowledge and implement. If feedback conflicts with requirements, present evidence and ask for clarification.
- Human has final say.

**Evidence weight order** (when feedback conflicts with reality):
1. Requirements/AC text
2. Working feature (tested evidence)
3. Review opinion (theoretical reasoning)

Breaking a working feature = P0, regardless of how elegant the suggested change is.

### 6. Discussion Convergence Checklist

After every discussion converges, verify:
1. Rejected proposals → document in decisions
2. Lessons learned → document in lessons log
3. New operational rules → document in appropriate guidance files

### 7. Vision Guard (Anti-Drift Protocol)

1. Read original requirements before starting a feature
2. AC all checked ≠ done. Ask: "What does the user experience look like?"
3. Frontend features produce screenshot evidence (≤3 screenshots + 15s recording)
4. Review requests include original requirement excerpts (≤5 lines)
5. When uncertain, escalate to Human
6. UX/frontend verification requires actual browser interaction

### 8. Full Test Suite Evidence (3-Piece Standard)

Claims of "all tests pass" require three pieces of evidence, otherwise they count as local-only:

| # | Evidence | Example |
|---|------|------|
| 1 | **Command** | `run-tests` (full) or `run-tests --scope <name>` |
| 2 | **SHA** | `based on abc1234` |
| 3 | **Rebased to latest main?** | `rebased on origin/main` or `not rebased (based on 3-day-old main)` |

**Pre-merge full gate**: `project-gate-check` (auto rebase + build + test + lint + check, prints 3-piece evidence on pass).

### 9. Rebase Conflict: 3-Screen Rule

When rebase hits conflicts, **review all three versions** (base / ours / theirs) before resolving:

```bash
git show :1:<path>   # BASE (common ancestor)
git show :2:<path>   # OURS (current branch)
git show :3:<path>   # THEIRS (main)
```

**Conflict resolution discipline**:
1. Review base→ours diff: **what I changed**
2. Review base→theirs diff: **what changed on main**
3. Understand both intents before merging
4. **Never** `git checkout --ours .` or `--theirs .` blindly
5. PR description: which files had conflicts, whose intent was preserved, why

### 10. Evidence-Based Conclusions

Conclusions require multi-source evidence. One file is not enough.

- **Follow the evidence chain**: .md is an entry point — trace commits, PRs, code, discussions until the full picture is clear
- **Don't cherry-pick**: A file may be one link in a chain. Follow references and dependencies.
- **Insufficient evidence = say so**: "I haven't finished checking" / "uncertain" is always better than fabricating a plausible answer

### 11. Decision Funnel: Ask When Needed, Execute When Clear

> "SOP progression is execution, not decision-making." Don't stop at every phase transition to ask "can I continue?"

**Two-tier funnel**:

| Tier | Who Decides | Examples |
|------|--------|------|
| **Macro** | Human | Architecture ADR, security/data irreversible, cost changes, priority adjustments, product direction |
| **Detail + Flow** | Agent | Implementation details, bug fixes, SOP stage progression, code structure, test coverage |

**Decision standard**: "Can I answer this by reading code, docs, or running tests?" → Agent decides. "Does this involve product vision, user experience, irreversible data changes, or priority tradeoffs?" → Ask Human.

**Before asking Human — self-check**: "Can I find this answer myself?"
- Code/technical/engineering questions → `git log`, `git diff`, read code, run tests → find it yourself. Don't ask.
- Product vision/user experience/priorities/irreversible decisions → these are the ones to ask Human about.
- One rule: **If you can answer it by reading code, don't ask a person.**
