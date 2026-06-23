# Writing Plans — Execution Workflow

Step-by-step process for creating implementation plans.
Invoked by `skills/writing-plans/SKILL.md`.

## Scripts

N/A — reference-only module. All steps are process descriptions.

## Execution Order

### Straight-Line Check (A→B, No Detour)

在拆分步骤前，先确认方向：

1. **Pin the finish line**: 一句话 B 定义 + acceptance criteria + "what we're NOT building"
2. **Define terminal schema**: 最终形态的 interfaces/types/data structures
3. **Every step passes three questions**:
   - Will this step's output stay in the final system as-is? → Yes = on the line; No = detour
   - What can we demo/test after this step?
   - If we remove this step, what specific cost does it add to reaching B?
4. **Pure exploration = explicit Spike** (time-boxed, output is a decision/conclusion)

Steps are internal implementation rhythm, NOT delivery batches.

### Bite-Sized Task Granularity

每个 step 是一个动作（2-5 分钟）：
- "Write the failing test"
- "Run it to make sure it fails"
- "Implement the minimal code"
- "Run the tests and make sure they pass"
- "Commit"

### Plan Document Header

```markdown
# [Feature Name] Implementation Plan

**Feature:** F0xx — `docs/features/F0xx/xxx.md`
**Goal:** [One sentence — must match feat doc]
**Acceptance Criteria:** [从 feat doc 逐条抄过来]
**Architecture:** [2-3 sentences about approach]
**Tech Stack:** [Key technologies/libraries]
```

### Task Structure

```markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

**Step 1: Write the failing test**
**Step 2: Run test to verify it fails**
**Step 3: Write minimal implementation**
**Step 4: Run test to verify it passes**
**Step 5: Commit**
```

### 下一步

计划写完 → 加载 `worktree`（创建隔离开发环境）→ `tdd`（开始实现）。

## Tests

N/A — reference-only module.

## Examples

- Feature F042 spec 确认 → writing-plans → 产出 5 个 task 的计划 → worktree → tdd

### Document Sync Rule

After writing the implementation plan:
- Update `docs/features/Fxxx-*.md`:
  - Add `## Implementation Plan` section linking to `docs/features/Fxxx/implementation-plan.md`
  - Set `status: planned`
  - Update `updated:` timestamp

### Memory Hook: memory-search

Before proceeding, invoke the memory hook from `registry/capabilities.yaml`:
→ `memory_hooks.writing-plans.start: memory-search`
→ `modules/agent-memory/` → router → `memory-search`
→ Execute `workflows/memory-search.md`
→ Search for prior implementation plans, lessons, or decisions relevant to this feature. Reference any findings that influence the plan.

## Next Step

→ `worktree` — after the plan is written, create an isolated development environment.
