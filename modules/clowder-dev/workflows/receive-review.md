# Receive Review — Execution Workflow

Step-by-step process for handling review feedback.
Invoked by `skills/receive-review/SKILL.md`.

## Scripts

N/A — reference-only module. All steps are process descriptions.

## Execution Order

### 两类反馈，处理方式不同

| 类型 | 特征 | 处理 |
|------|------|------|
| **代码级** | bug / edge case / 性能 / 命名 | Red→Green 修复流程 |
| **愿景级** | "这不是用户要的" / "缺了多项目管理" / "UI 不可用" | STOP → 回读原始需求 → 升级确认 |

愿景级反馈不能用代码 patch 修补设计问题。先对照原话验证 reviewer 说得对吗；如确实偏离，升级确认偏差范围，再重新设计。

### 流程

```
WHEN 收到 review 反馈:

1. READ  — 完整读完，不要边读边反应
2. CLASSIFY — 区分愿景级 vs 代码级；按 P1/P2/P3 分优先级
3. CLARIFY — 有不清晰的问题先全部问清，再动手
4. VERIFY — reviewer 说的问题真的存在吗？（过三道门）
5. FIX — 通过验证的问题 Red→Green 逐个修复
6. CONFIRM — 修完回给 reviewer 确认，不能自判"改对了"
```

### VERIFY 三道门（少一道不准照改）

1. **Spec Gate** — 这条意见和现有 AC/需求冲突吗？
   - 冲突 → pushback，附 AC 原文
   - 不冲突 → 进下一道
2. **Mechanism Gate** — reviewer 说"这不行"的证据是什么？
   - 有失败用例 / 真实平台限制 → 进下一道
   - 只是"不优雅"/"理论上不安全"但拿不出失败路径 → 当假设处理，pushback 要求证据
3. **Feature Gate** — 按建议改完后，核心用户路径还活着吗？
   - 改完跑一遍最关键的用户路径
   - 功能死了 → 回滚，review 建议作废

### Red→Green 修复流程

对每个 P1/P2 问题，逐个修复：

修复顺序：P1（blocking）→ P2（必须修）→ P3（讨论后当场修或放下）

### 禁止的响应（表演性同意）

```
❌ "You're absolutely right!"    ❌ "Great point!"
❌ "Excellent feedback!"         ❌ "Thanks for catching that!"
❌ "让我现在就改"（验证之前）
```

行动说明一切——直接修复，代码本身证明你听到了反馈。

### Push Back 标准

当以下情况时必须 push back，用技术论证：
- 建议会破坏现有功能
- Reviewer 缺少完整上下文
- 违反 YAGNI（过度设计）
- 与架构决策/用户要求冲突

Review 有零分歧 = 走过场。真正的 review 需要技术争论。

## Tests

N/A — reference-only module.

## Examples

- P1: 空状态未处理 → VERIFY 三道门通过 → Red→Green 修复 → reviewer 确认放行
- 愿景级: "UI 不可用" → STOP → 回读原始需求 → 升级确认 → 重新设计

### Document Sync Rule

After processing review feedback:
- Update `docs/features/Fxxx-*.md`:
  - Add `## Review Notes` section with feedback summary and resolutions
  - Update AC status if any items were affected by review changes
  - Update `updated:` timestamp

**Rule**: If Human gave feedback that changed the feature, the doc must reflect it. Stale docs = future confusion.

### Memory Hook: lesson-capture

After completing fixes, invoke the memory hook from `registry/capabilities.yaml`:
→ `memory_hooks.receive-review.fix: lesson-capture`
→ `modules/agent-memory/` → router → `lesson-capture`
→ Execute `workflows/lesson-capture.md`
→ Capture the lesson from this review fix — what was the feedback, what was the root cause, what guard prevents recurrence.

## Next Step

→ `merge-gate` — after Human approves all changes **AND the feature doc is updated with review notes**.

**Gate**: Before proceeding, confirm `docs/features/Fxxx-*.md` has a `## Review Notes` section with this review's feedback and resolutions.
