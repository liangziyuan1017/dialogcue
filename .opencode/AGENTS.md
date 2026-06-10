# MANDATORY FEATURE ROUTING — NO EXCEPTIONS

NEVER implement, fix, or write code for a feature (F\d+, f\d+) directly.
NEVER skip the routing pipeline, regardless of how simple the task seems.

When the user mentions any feature ID (e.g. F001, f001, F002), you MUST follow this exact sequence BEFORE writing any code:

1. **Read the feature doc**: Find and read `modules/dev-ui/refs/<ID>-*.md` to get the current `status` field.
2. **Read the registry**: Read `registry/capabilities.yaml` → find `clowder_dev_workflows`.
3. **Read the router**: Read `modules/clowder-dev/router.md` → match the skill whose triggers fit the current status + user intent.
4. **Execute that skill's workflow ONLY**: Read the matched `SKILL.md` → read its `workflow.md` → execute. Do NOT skip to implementation.

### Status-to-Skill Routing Table

| Feature `status` | User says "fix" / "review" | User says "new" / "start" | User says "done" / "complete" | User says "merge" |
|---|---|---|---|---|
| `draft` | feat-lifecycle | feat-lifecycle | — | — |
| `planned` | writing-plans | writing-plans | — | — |
| `developing` | tdd | worktree | quality-gate | — |
| `review` | **receive-review** | — | — | — |
| `approved` | — | — | — | merge-gate |
| `merged` | — | — | — | — |

**If status is `review` and user says "fix" → you MUST use `receive-review` workflow. NEVER implement the fix directly.**

If the feature doc is missing or status is unclear, ask the user before proceeding.

### Hook Enforcement — MANDATORY, NOT OPTIONAL

After EVERY chain step that has a `memory_hooks` entry in `registry/capabilities.yaml`:

1. Read the registry → find the hook for `<current_skill>.<current_step>`
2. Execute the hooked skill's workflow immediately — do NOT defer
3. Run `python3 scripts/hook_check.py --step <skill>.<step> --feature Fxxx`
4. If hook_check returns exit code 1 → **STOP**. Do not proceed to next chain step.

**Pre-commit enforcement:** A git pre-commit hook blocks commits if a feature is `in-progress`, `review`, or `complete` but has no ADR in `docs/decisions/`. This is a hard gate — not a warning.

---
# Memory-First Rule

Before making design/architecture decisions, the agent MUST consult durable
project memory. The specific hook points are defined in
`registry/capabilities.yaml` under `clowder_dev_workflows.memory_hooks`.
Do not hardcode memory consultation points in this rule — always read the
registry for the authoritative hook list.

## Rules

1. If a prior decision exists on the same topic and is `status: accepted`,
   respect it — do not re-decide without explicit Human override.
2. If a prior lesson exists for the same pitfall, follow its guard — do not
   repeat the mistake.
3. After making a new decision that affects future work, invoke
   `decision-record` to persist it.
4. After encountering and recovering from a failure, invoke `lesson-capture`
   to persist the lesson.
5. This rule does NOT replace explicit triggers — it adds mandatory
   consultation before action.

---

# Karpathy Behavioral Guidelines

These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## Code Standards
- File size: 200 lines warning / 350 hard limit
- No `any` types
- Biome: `pnpm check` / `pnpm check:fix`
- Types: `pnpm lint`

---

# Runtime

For all task routing, capability matching, chain execution, memory hooks, skill discovery, and contracts — read and follow `agent.md`. That file is the authoritative runtime specification. Do not duplicate its contents here.
