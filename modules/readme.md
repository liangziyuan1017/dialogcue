# Deterministic Navigation Architecture

This architecture builds a deterministic module system where each layer contains only enough information to route to the next. Execution intelligence lives in files, not inside the runtime.

## Execution Chain

```
registry/capabilities.yaml  →  router.md  →  skills/<name>/SKILL.md  →  workflows/<name>.md  →  scripts/<name>.py
```

| Layer | Role |
|---|---|
| **Registry** | Routes capability name → module path (routing only) |
| **Router** | Routes capability → skill within the module (routing only) |
| **Skill** | YAML frontmatter + decision logic, points to workflow |
| **Workflow** | Step-by-step execution with exact commands, no frontmatter |
| **Scripts** | Tiny, isolated, deterministic Python functions |
| **Tests** | Verify outputs, edge cases, determinism |
| **working_file.md** | Only writable file; tracks external runtime impact |

## Runtime Flow

```
1. Parse task into capability need
2. Read registry/capabilities.yaml → find matching module
3. Read module/router.md → find matching skill
4. Read skills/<name>/SKILL.md → confirm decision, get workflow pointer
5. Read workflows/<name>.md → execution steps with exact commands
6. cd modules/<name>/scripts/ && run commands in order
7. Return structured output
```

## Module Structure

```
modules/<module-name>/
├── skills/<capability>/SKILL.md   # YAML frontmatter + decision logic
├── workflows/<capability>.md      # Execution steps, no frontmatter
├── scripts/<script>.py            # One deterministic function per file
│   └── common_utilities/          # (optional) shared helpers
├── tests/test_<script>.py         # One test file per script
├── rules.md                       # Module constraints
├── router.md                      # capability_map → skills
└── working_file.md                # External impact tracker (only writable)
```

The runtime should only navigate. The files themselves contain the execution intelligence.

## Layer Responsibilities

### Registry

Purpose: capability routing only.

It should contain:
- capability name
- short description
- module path

It must not contain implementation details.

### Module

Purpose: capability packaging and boundary ownership.

It should contain:
- workflows
- module-related specific skills
- module-related specific rules
- scripts
- tests
- working files

It should group everything required for one capability domain and keep related assets cohesive in one place. It must not become a second workflow or a place for runtime decision logic.

### `workflow.md`

Purpose: step-by-step execution orchestrator.

It should contain:
- `Scripts` table: script path, exact command, output format
- `Execution Order`: numbered steps with exact commands and success/failure conditions
- `Tests` table: test name, path, what it verifies
- `Examples`: reproducible input → output pairs

Workflows are invoked by skills — they do NOT have YAML frontmatter. They point directly to scripts.
They must not absorb routing logic or decision logic. They define execution only.

### `working_file.md`

Purpose: external runtime impact tracking.

The only writable file during runtime. It must track impact outside the module:
- which external `src/` entrypoint receives the input
- which external function invokes the module-related behavior
- where the output is stored outside the module
- which external files are affected by the task

It must not track module-internal files (`router.md`, `rules.md`, `skills/`, `workflows/`, `scripts/`, `tests/`).
If a task does not touch external files, state that explicitly.

### Skills

Purpose: routable entry points with decision logic.

They should contain:
- YAML frontmatter (`name`, `description`, `triggers`) for agent matching
- decision logic (when to apply this skill vs. alternatives)
- pointer to the execution workflow in `workflows/`

Skills are lean (~150 lines). Heavy operational detail lives in workflows and optional `refs/`.
They should not own workflow sequencing or act as general module indexes.

### Scripts

Purpose: actual execution.

They should contain:
- small deterministic units of execution
- clear inputs and outputs
- reusable behavior
- comments that explain purpose, invoker, and related tests

Scripts should stay tiny, isolated, deterministic, and reusable.
They should execute logic only and should not carry orchestration, routing, or policy selection concerns.

### Tests

Purpose: deterministic verification.

They should contain checks for:
- expected outputs
- edge cases
- deterministic behavior

Tests should verify observable behavior only. They confirm repeatable outcomes without redefining workflow or implementation instructions.

## Important Philosophy

The intelligence lives in:

`workflow -> skills -> scripts`

It does not live inside the agent.

The agent should only:
- navigate
- read
- execute
- validate
- return

## Benefits

This architecture is:
- deterministic
- portable
- inspectable
- reproducible
- composable
- exportable
- MCP-compatible
- agent-friendly
- low-token
- easy to debug

Most importantly, every file teaches future file creation.

## Reference Structure

```text
registry/
  capabilities.yaml
modules/
  basic-math/
    skills/
      add-numbers/
        SKILL.md
    workflows/
      add-numbers.md
    scripts/
      add.py
      validate_number.py
      common_utilities/
    tests/
      test_add.py
      test_validate_number.py
    rules.md
    router.md
    working_file.md
src/
  input_entry.py
  math_service.py
  result_store.py
```
