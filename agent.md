# Agent Runtime Guide

## Purpose
Implement a deterministic navigation architecture for the whole project.

The agent should only:
- navigate
- read
- execute
- validate
- return

The execution intelligence must live in project files, not inside the agent.

## Runtime Flow
1. Parse the task into a capability need.
1.5. **Skill Discovery**: Read `global_skills/README.md` manifest. For each sub-intention identified during task decomposition, check if any global skill's "Use When" matches and "Not For" does not match. If a skill matches, adopt its methodology for that sub-task. See "Skill Discovery" section below.
2. Read `registry/capabilities.yaml`.
3. Find the capability entry whose description matches the task.
4. Navigate to the module path listed in that entry.
5. Read the module's `router.md` to find the matching skill.
6. Read the matched skill file (`SKILL.md`) — it contains the decision logic and points to the execution workflow.
7. Read the referenced workflow file from `workflows/`.
8. Review the `Scripts` table in the workflow to understand which scripts are needed.
9. Execute the script commands listed in the workflow's `Execution Order`, in sequence.
10. Run the referenced tests only when validating the module (not on every invocation).
11. Return structured output.

## Capability Matching
The agent matches a task to a capability using keyword-trigger matching:

1. Parse the task into keywords.
2. Read `capabilities.yaml` and find candidate modules whose descriptions match the task.
3. For each candidate, read `router.md` to get the skill paths.
4. Read each skill's **YAML frontmatter** and compare task keywords against the `triggers` list.
5. Pick the skill with the most trigger matches.
6. If no triggers match, follow the router's `fallback_rule` and stop using the module.

The `triggers` list in each skill's frontmatter is the authoritative matching source.

### Trigger Pattern Matching
Some triggers contain patterns instead of literal strings:
- `F0xx` matches any feature number: F001, F002, ..., F099
- `F\d+` (regex) matches any F followed by digits: F1, F001, F1234
- `f\d+` matches lowercase variants: f001, f123

When comparing task tokens against triggers, apply pattern matching:
- A trigger containing `\d+` or `xx` is a pattern — match it as a regex, not a literal string.
- Case-insensitive matching: `f001` matches `F001`, `F\d+`, and `F0xx`.

## Command Execution
Workflow commands include the script to run. The agent must:

1. `cd` into the module's `scripts/` directory before running any command.
2. Run each command exactly as written, substituting placeholder values (e.g. `A`, `B`, `VALUE`) with actual inputs.
3. Evaluate the output of each step before proceeding to the next.
4. If a step returns an error or failure condition, stop and return the error — do not continue.

## Chain Execution
Some modules define a skill chain — a sequence of skills that must execute in order (e.g., development flow: feat-lifecycle → writing-plans → worktree → tdd → quality-gate → request-review → receive-review → merge-gate). The agent must NOT skip steps in the chain.

After completing each skill in a chain, the agent MUST:
1. Follow the skill's `## Next Step` pointer to the next skill.
2. Execute the `### Document Sync Rule` from the current workflow — update the feature doc (`docs/features/Fxxx-*.md`) with any changes made during this phase.
3. Do NOT proceed to the next skill until the doc is updated.

**No exceptions.** A stale feature doc is a bug. If the doc wasn't updated, the phase is not complete.

**How the agent follows a chain:**

1. The chain is documented in `router.md` (the `capability_map` section header or a `chain:` comment).
2. Each workflow file has a `## Next Step` section at the end that points to the next skill.
3. After completing one workflow, read the `## Next Step` pointer.
4. If `## Next Step` points to another skill → read that skill's `SKILL.md` → read its `workflow.md` → execute it.
5. Continue until `## Next Step` says "Complete" or no next step is defined.
6. **Never skip**: if the chain says A → B → C, the agent must execute A, then B, then C. Jumping from A directly to C (or directly to implementation) is a violation.

**Example** — when Human says "write a new feature":
- `feat-lifecycle` matches → execute Kickoff + Discussion + Design Gate
- Read `## Next Step`: `→ writing-plans`
- Execute `writing-plans`
- Read `## Next Step`: `→ worktree`
- ...continue through the full chain

**Lightweight path**: Trivial changes (typos, ≤5 line fixes) can skip the chain. The router's SOP path table defines when the full chain is required vs. lightweight.

## Pre-Action Memory Consultation

Before executing any module capability that creates or modifies project artifacts, the agent MUST consult durable project memory.

This is enforced by `global_rules/memory-first.mdc` (alwaysApply: true). The agent must not skip memory consultation even if the user does not explicitly request it.

The specific hook points are defined in `registry/capabilities.yaml` under each capability's `memory_hooks` field. Do not hardcode hook locations — always read the registry.

## Memory Hook Resolution

When a capability entry in `registry/capabilities.yaml` contains `memory_hooks`, the agent must resolve and execute hooks as follows:

1. After completing each skill in a chain, check `capabilities.yaml` for a `memory_hooks` entry matching `<skill_name>.<step>`.
2. If a hook exists:
   a. Navigate to `modules/agent-memory/`.
   b. Read `router.md` to find the hooked skill.
   c. Read the skill's `SKILL.md` → `workflow.md` → execute.
3. Hook output is informational — it does not change the chain's flow unless it returns a VIOLATION (e.g., governance-review).
4. If a hook returns VIOLATION → stop the chain and report the violation to Human. Do not proceed to the next chain step.
5. If a hook returns CAUTION → note in feature doc, proceed with Human awareness.
6. If a hook fails (script error, module missing) → log the failure and continue the chain. Hook failures must not block the primary workflow.

**Example** — after completing `feat-lifecycle` kickoff step:
- Read `capabilities.yaml` → find `memory_hooks.feat-lifecycle.kickoff: memory-search`
- Navigate to `modules/agent-memory/` → `router.md` → `skills/memory-search/SKILL.md`
- Execute `workflows/memory-search.md`
- If results include an accepted decision on the same topic → reference it in the feature doc and respect it
- Continue to next chain step (`writing-plans`)

## Skill Discovery

Before resolving a task through the registry, the agent must check whether a global skill's methodology should be adopted for any sub-task.

### When Skill Discovery Runs

Skill discovery runs at two points:
1. **Task decomposition** — when the agent breaks a task into sub-tasks, it checks each sub-intention against the global skills manifest.
2. **After module execution** — when a module workflow produces a result that matches a global skill's "Use When" (e.g., bug found during TDD → adopt debugging skill), the agent checks for applicable skills.

### How Intention Matching Works

For each sub-intention, the agent:
1. Reads `global_skills/router.md` (or `global_skills/README.md` manifest).
2. Compares the sub-intention against each skill's **Use When** column.
3. Checks that the sub-intention does NOT match the skill's **Not For** column.
4. If Use When matches AND Not For does not match → adopt the skill.
5. If multiple skills match → pick the most specific (narrowest Use When).

### What "Adopt" Means

Adopting a global skill means:
1. Read the skill's `SKILL.md` for its methodology and decision logic.
2. Apply the skill's process to the current sub-task.
3. The skill's methodology shapes HOW the agent works — it does not replace the module's execution pipeline.

Global skills are methodology tools, not executable pipelines. They do not have `workflows/` or `scripts/` directories. The agent applies the skill's process pattern to the task context.

### Skill Adoption vs. Module Execution

| Aspect | Module Skill | Global Skill |
|--------|-------------|-------------|
| Discovery | Trigger matching in registry | Intention matching in manifest |
| Resolution | registry → router → SKILL.md → workflow → scripts | manifest → SKILL.md (methodology only) |
| Execution | Deterministic script commands | Process pattern applied to task |
| Output | Structured data from scripts | Methodology-guided result |
| Side effects | Writes to docs/, .agent-memory/ | May produce documents, may guide next steps |

## Skill Hook Resolution

When a capability entry in `registry/capabilities.yaml` contains `skill_hooks`, the agent must resolve and adopt skills as follows:

1. At the declared hook point during execution, check `capabilities.yaml` for a `skill_hooks` entry matching `<skill_name>.<step>`.
2. If a hook exists:
   a. Navigate to `global_skills/`.
   b. Read `router.md` to find the hooked skill.
   c. Read the skill's `SKILL.md` and adopt its methodology.
3. Skill adoption is methodology-only — it shapes HOW the agent works at this point, it does not replace the module's execution pipeline.
4. If the skill's "Not For" matches the current context → skip the hook. The skill explicitly declares when it should NOT be used.
5. If a skill hook fails (SKILL.md missing, unreadable) → log and continue. Skill hooks must not block the primary workflow.

**Example** — during `tdd` when a bug is found:
- Read `capabilities.yaml` → find `skill_hooks.tdd.bug_found: debugging`
- Navigate to `global_skills/` → `router.md` → `quality/debugging/SKILL.md`
- Adopt the debugging methodology (4-phase pipeline: root cause → pattern analysis → hypothesis → fix)
- The agent now follows the debugging process instead of ad-hoc fixing
- After debugging completes, continue the TDD cycle

## Test Policy
- Tests verify that scripts produce deterministic, correct outputs.
- Tests run during module creation or validation, NOT during every capability invocation.
- The `required_tests` section in each workflow lists which tests cover that workflow's scripts.
- To run tests: `cd` into the module directory and run `python tests/test_<name>.py`.

## Registry Contract
The registry is for capability routing only.

Each capability entry should contain only:
- capability name
- short description
- module path

The registry must not contain implementation details.

## Module Contract
Each module owns workflow execution.

A module may define:
- skills/
- workflows/
- scripts/
- tests/
- rules.md
- router.md
- working_file.md

The agent should not infer missing execution behavior outside these files.

## Router Contract
`router.md` is the module-level routing layer. It maps capability descriptions to skill files.

It should define:
- `capability_map`: a table mapping capability descriptions → skill paths within `skills/`
- `fallback_rule`: what to do when no capability matches the task

The router contains routing information only. It must not contain implementation details.

## Skill Contract
`SKILL.md` files in `skills/` are the routable entry points.

Each skill should define in YAML frontmatter:
- `name`: unique skill identifier
- `description`: what the skill does, when to use, when NOT to use, expected output
- `triggers`: keywords the agent matches against task text

The Markdown body should contain:
- Decision logic (when to apply this skill vs. alternatives)
- Pointer to the execution workflow in `workflows/`
- Required tests and examples

Skills are lean (~150 lines). Heavy operational detail lives in `workflows/` and domain-specific knowledge in `refs/`.

## Workflow Contract
Workflow files in `workflows/` are the execution orchestrators. They are invoked by skills.

Each workflow should define:
- `Scripts`: table of scripts, their commands, and expected output format
- `Execution Order`: numbered steps with exact commands to run, plus success/failure conditions
- `Tests`: tests that verify this workflow's scripts
- `Examples`: reproducible input→output pairs

The workflow orchestrates only. It points directly to scripts — there is no intermediate skills layer.

## Script Contract
Scripts perform actual execution.

Scripts should be:
- tiny
- isolated
- deterministic
- reusable

Each script should document:
- purpose
- invoking workflow
- inputs
- outputs
- related tests

## Test Contract
Tests provide deterministic verification.

Tests should validate:
- expected outputs
- edge cases
- deterministic behavior

## Fallback Rule
If no registry capability fits the task, do not use any module.

If a chosen module is missing the skill, workflow, script, or test path needed to complete the task, stop using that module.

In either case, ignore modules and continue with normal agent operations.

## `working_file.md` Purpose
`working_file.md` is not just a progress log.

The module is immutable during runtime except for `working_file.md`.

`working_file.md` must not be used to track module-internal files such as:
- `router.md`
- `rules.md`
- `skills/`
- `workflows/`
- `scripts/`
- `tests/`
- `examples/`

It must only store runtime impact outside the module, including:
- which external `src/` entrypoint receives the input
- which external function invokes the module-related behavior
- where the output is stored outside the module
- which external files are affected by the task

If a task does not touch external files, `working_file.md` should state that explicitly.

## Structured Output
After execution, the agent should return structured output summarizing:
- `mode`: the capability that was invoked
- `capability`: the capability name
- `module`: the module that was used
- `validation_status`: whether inputs passed validation
- `result`: the final output from the scripts
- any errors or fallback conditions encountered
