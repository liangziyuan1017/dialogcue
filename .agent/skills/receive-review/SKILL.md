---
name: receive-review
description: >
  处理 Human 反馈：Red→Green 修复。
  Use when: 收到 Human review 结果、Human 提了 feedback、需要处理反馈。
  Not for: 发 review 请求（用 request-review）、自检（用 quality-gate）。
  Output: 逐项修复确认 + Human 放行。
triggers:
  - "review 结果"
  - "review 意见"
  - "reviewer 说"
  - "fix these"
  - "F\\d+ fix"
  - "f\\d+ fix"
---

# Receive Review

处理 reviewer 反馈的完整流程。核心原则：**技术正确性 > 社交舒适，验证后再实现，禁止表演性同意。**

## What this skill does

1. 分类反馈：愿景级 vs 代码级
2. VERIFY 三道门：Spec Gate → Mechanism Gate → Feature Gate
3. Red→Green 修复：P1 → P2 → P3 逐个修复
4. 技术论证 push back（当建议会破坏功能/违反 YAGNI 时）

## When to use

- 收到 review 结果、reviewer 提了 P1/P2、需要处理反馈

## When NOT to use

- 发 review 请求（用 request-review）
- 自检（用 quality-gate）

## Execution

→ Read `workflows/receive-review.md` for the detailed step-by-step process.

## Tests

N/A — reference-only module.

## Examples

- 收到 review 反馈 → 分类（愿景/代码） → VERIFY → P1→P2→P3 修复 → 回 reviewer 确认
