# TDD — Execution Workflow

Red-Green-Refactor cycle for test-driven development.
Invoked by `skills/tdd/SKILL.md`.

## Scripts

N/A — reference-only module. All steps are process descriptions.

## Execution Order

### Red-Green-Refactor 循环

```
RED  → 写一个会失败的测试
       ↓ 必须亲眼看到它失败（失败原因要对，不是 typo）
GREEN → 写最少代码让测试通过
       ↓ 必须亲眼看到它通过（其他测试也要绿）
REFACTOR → 消除重复、改善命名
       ↓ 保持绿灯，不添加行为
重复 →
```

**关键决策点**：
- RED 阶段测试立即通过？→ 你在测已有行为，修测试
- RED 阶段报错而非失败？→ 修错误直到"正确地失败"
- GREEN 阶段其他测试挂了？→ 立即修，不要继续
- REFACTOR 后测试变红？→ 撤销 refactor，重来

### 为什么顺序绝对不能反？

| 异议 | 真相 |
|------|------|
| "写完再补测试，也能验证" | 测试写在实现后会立即通过——你永远不知道它是否真的在测你要的东西 |
| "我手工测了所有 case" | 手工测试没有记录、不能重跑、下次改动时你会忘了测什么 |
| "删掉 X 小时的工作太浪费" | 沉没成本谬误。留着无法信任的代码才是浪费 |
| "TDD 是教条，务实应该灵活" | TDD 本身就是务实的——它比事后调试快，能防止回归 |

Tests-after 回答"这段代码做了什么"；tests-first 回答"这段代码应该做什么"。两者不等价。

### Bug Fix 模式

Bug 修复和新功能一样，必须先写失败测试。

1. 写一个复现 bug 的测试（此时必须红）
2. 确认测试以"预期的理由"失败
3. 修复代码
4. 确认测试通过
5. 确认无回归

**永远不要在没有测试的情况下修 bug。**

### 好测试的标准

- **一个行为**：名字里有"and"？拆分
- **名字描述行为**：`rejects empty email` 好于 `test1`
- **测真实代码**：避免只测 mock

### 口令：立即停止的 Red Flags

听到自己说以下任何一句 → 删掉代码，从测试重新开始：
- "应该能过"、"大概没问题"、"先快速实现一下"
- "测试我写完功能再补"、"这个太简单了不用测"

## Tests

N/A — reference-only module.

## Examples

- RED: `def test_add_positive(): assert add(2, 3) == 5` → FAIL (add not defined)
- GREEN: `def add(a, b): return a + b` → PASS
- REFACTOR: add docstring, type hints → still PASS

### Document Sync Rule

After each TDD cycle (RED→GREEN→REFACTOR):
- Update `docs/features/Fxxx-*.md`:
  - Mark completed AC items with ✅ as their tests pass
  - Add new files to the Files table
  - Update `updated:` timestamp when a task is complete

**Rule**: If the feature doc's AC status doesn't match the test results, the doc is lying. Fix it before proceeding.

### Memory Hook: lesson-capture

If any bugs were found and fixed during this TDD cycle, invoke the memory hook from `registry/capabilities.yaml`:
→ `memory_hooks.tdd.bug_fix: lesson-capture`
→ `modules/agent-memory/` → router → `lesson-capture`
→ Execute `workflows/lesson-capture.md`
→ Capture any lessons learned from bugs discovered — pitfall, root cause, trigger, fix, and guard.

## Next Step

→ `quality-gate` — after implementation is complete, run the self-check gate before review.
