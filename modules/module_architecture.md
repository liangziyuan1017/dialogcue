# overview
Design Goal

The system is designed around plug-and-play modules that provide:

* deterministic execution
* reusable workflows
* isolated domain ownership
* portable capability packages
* minimal runtime intelligence
* consistent behavior across projects

Each module acts as a self-contained capability unit that can be mounted into different projects without rewriting orchestration logic.

# module design
The module architecture aims to make agent execution predictable by turning module behavior into an explicit file-based structure. Each layer contains only enough information to route to the next layer. The agent should not invent behavior at runtime — it follows a fixed structure where:
- **Registry** → routes capability name to module path (routing only), if no appropriate capabilities to use, just rely on agent itself to perform task on src/, do not read anything from module/
- **Router** → routes capability to skill within the module (routing only), if the specific module does not match the task, rely on agent itself to perform task on src/, do not read anything from module/
- **Skill** → routable entry point with YAML frontmatter (name, description, triggers) + decision logic — lean (~150 lines), points to workflow
- **Workflow** → step-by-step execution orchestrator with exact commands — no frontmatter, invoked by skills
- **Scripts** → perform actual deterministic execution (tiny, isolated, reusable)
- **Tests** → verify deterministic outputs, edge cases, and expected behavior
- **working_file.md** → tracks external runtime impact (only writable file during runtime)

The runtime should only navigate. The files themselves contain the execution intelligence.

# project architecture
```
/global_rules        # Global constraints applicable across all modules (e.g. karpathy-guidelines.mdc)
/global_skills       # Global skills not tied to a single module; can be referenced by any workflow
/modules             # All capability modules live here
    /module_a        # Each module groups skills, workflows, scripts, tests, rules, router, and working_file
        /skills            # Routable SKILL.md files — YAML frontmatter + decision logic, point to workflows
        /scripts           # Tiny, isolated, deterministic .py files; each invoked as a whole during workflow
            /common_utilities  # Shared utilities importable by scripts
        /workflows         # Execution orchestrators — step-by-step commands, no frontmatter, invoked by skills
        /tests             # Tests verifying deterministic outputs, edge cases, and expected behavior
        - rules.md         # Module-specific constraints (e.g. finite numbers only, no external APIs)
        - router.md        # Module-level routing: maps capability names → skills (routing info only)
        - working_file.md  # Only writable file during runtime; tracks external runtime impact
    /module_b
/registry
    - capabilities.yaml   # Capability registry: name, short description, module path (routing only)
/src                 # Runtime source code — entrypoints, invocation functions, output targets
- agent.md            # Agent Runtime Guide: the deterministic navigation contract
- capabilities_creator.md  # Standard for creating deterministic, reusable capabilities
- pyproject.toml      # Python project config: build system, metadata, dependencies
```

# responsibilities

path: /global_rules/
- Contains global constraints and guidelines that apply across all modules. These rules are read during runtime to enforce consistent behavior project-wide. Currently holds `karpathy-guidelines.mdc`.

path: /global_skills/
- Optional directory for shared logic across modules. Workflows may reference global skills as additional extension points beyond module-local skills and refs.

path: /modules/
- goal: modules are independent, re-usable packages that serve a domain of functionalities. Each module owns workflow execution and groups everything required for one capability domain. The agent should not infer missing execution behavior outside module files.
    
path: /modules/module_a/
- Each module directory is a self-contained capability package. It contains: skills/ (routing + decision logic), workflows/ (execution), scripts/ (execution), tests/ (verification), rules.md (constraints), router.md (module-level routing), and working_file.md (external impact tracking). The module is immutable during runtime except for working_file.md.

path: /modules/module_a/scripts/
- contains the .py file defined by workflow, each file is to be invoked as a whole during the workflow, common utilities can be imported into the .py file. Scripts should be tiny, isolated, deterministic, and reusable code functions or classes, with function description in google style highlighting its purpose, inputs and outputs. 
        
path: /modules/module_a/scripts/common_utilities/
- common utilities can be imported by scripts. Shared helper functions that are used across multiple scripts within the same module.

path: /modules/module_a/skills/
- Contains routable skill files: one subdirectory per public capability, each with a `SKILL.md`. Skills have YAML frontmatter (`name`, `description`, `triggers`) for agent matching, and a Markdown body with decision logic, invocation pointers to `workflows/`, tests, and examples. Skills are lean (~150 lines); heavy operational detail lives in workflows and optional `refs/`.

path: /modules/module_a/workflows/
- each workflow file contains step-by-step execution instructions with exact commands. Workflows are invoked by skills — they do NOT have YAML frontmatter. They define: `Scripts` (commands + output format), `Execution Order` (numbered steps with success/failure conditions), `Tests`, and `Examples`. They point directly to scripts. They must not absorb routing logic or decision logic.

path: /modules/module_a/tests/
- Contains test files that verify scripts produce deterministic expected outputs, handle edge cases (e.g. NaN, Infinity, non-numeric inputs), and maintain deterministic behavior. Tests are run as part of the workflow validation step. A capability is not complete without explicit verification of deterministic behavior.

path: modules/module_a/rules.md
- Defines module-specific constraints and rules that govern execution within that module. Examples: inputs must be finite numbers, arithmetic must be deterministic, do not modify floating-point behavior, do not call external APIs, return structured JSON only. Rules are read during runtime to enforce these constraints.

path: /modules/module_a/router.md
- The module-level routing layer. Maps elaborated capability descriptions to skill paths within `skills/`. Contains routing information only — capability description → skill path. Must not contain implementation details, execution logic, or embedded behavior rules. The runtime reads the router to determine which skill to invoke for a given capability.

path: /modules/module_a/working_file.md
- The only writable file inside the module during runtime. Tracks external runtime impact: which external src/ entrypoint receives the input, which external function invokes the module-related behavior, where the output is stored outside the module, and which external files are affected by the task. Must not track module-internal files (router.md, rules.md, workflows/, scripts/, tests/). If a task does not touch external files, state that explicitly.

path: /registry/
- Contains the capability registry (`capabilities.yaml`). The registry is for routing only. It maps capability names to module paths. Each entry contains only: capability name, short description, and module path. Must not contain implementation details, execution logic, or embedded behavior rules. Duplicate or ambiguous mappings are not allowed.

path: /registry/capabilities.yaml
- The capability registry is for routing only.
- Each capability entry in `registry/capabilities.yaml` should contain only:
    - capability name
    - short description
    - module path
- The registry must not contain implementation details, execution logic, or embedded behavior rules.
- Each capability must resolve to exactly one module path. Duplicate or ambiguous capability mappings are not allowed.

path: /src/
- Contains the actual runtime source code that invokes module capabilities. Modules are immutable during runtime; only src/ files may be modified. This is where external entrypoints (e.g. `input_entry.py`), invocation functions (e.g. `math_service.py`), and output targets (e.g. `result_store.py`) live. The runtime flow is: `input_entry.py` → `math_service.py` → `result_store.py`.

path: /agent.md
- The Agent Runtime Guide. Defines the deterministic navigation architecture: the agent should only navigate, read, execute, validate, and return. The execution intelligence must live in project files, not inside the agent. Defines contracts for: Runtime Flow (parse task → read registry → navigate to module → read router.md → match skill → read SKILL.md → read workflow → review Scripts table → execute commands → return output), Capability Matching (keyword-trigger matching via skill YAML frontmatter), Command Execution (cd to scripts/, run commands, evaluate output), Test Policy (tests run during module validation, not every invocation), Registry Contract (routing only), Module Contract (skills/, workflows/, scripts/, tests/, rules.md, router.md, working_file.md), Router Contract (capability_map table → skills, fallback_rule), Skill Contract (YAML frontmatter + decision logic), Workflow Contract (Scripts, Execution Order with exact commands), Script Contract (tiny, isolated, deterministic, reusable), Test Contract (deterministic verification), and Fallback Rule (stop using module if no capability matches).

path: /capabilities_creator.md
- Define the standard for creating deterministic, reusable capabilities within the module architecture.
- The primary execution chain during runtime is: `agent.md` → `registry/capabilities.yaml` → `modules/module_xxx/router.md` → `modules/module_xxx/skills/yyy/SKILL.md` → `modules/module_xxx/workflows/yyy.md` → `modules/module_xxx/scripts/script_zz.py`
- routing information only: capabilities.yaml, router.md
- skills: YAML frontmatter + decision logic, point to workflows
- execution workflow: workflows/ (no frontmatter, invoked by skills)
- actual code functions: scripts/
- actual code test: tests/
- Required module structure: skills/, workflows/, scripts/, tests/, rules.md, router.md, working_file.md
- Completion criteria: unique registry resolution, deterministic execution, correct skill→workflow→script references, write-boundary enforcement, explicit success/failure behavior

path: /pyproject.toml
- Python project configuration file. Defines: build system requirements (setuptools>=68, wheel), project metadata (name: agent_tool, version: 0.1.0), Python version constraints (>=3.14, <3.15), and project dependencies. Includes a reserved [tool] section for future tool-specific settings.


