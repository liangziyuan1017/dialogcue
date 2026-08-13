---
name: request-review
description: >
  向 Human 提交 review 请求。
  Use when: 自检通过后准备请 Human review。
  Not for: 收到 review 结果（用 receive-review）、自检（用 quality-gate）。
  Output: Review 请求信。
triggers:
  - "请 review"
  - "帮我看看"
  - "request review"
  - "F\\d+ review"
  - "f\\d+ review"
---

# Request Review

把改动送到 reviewer 眼前，让 reviewer 花时间在重点上——不是基础检查上。

## What this skill does

1. 确认前置条件：quality-gate 通过 + 测试全绿 + 原始需求可引用
2. 匹配 reviewer
3. 用模板写 review 请求
4. 发送请求

## When to use

- 自检通过后准备请其他人 review

## When NOT to use

- 收到 review 结果（用 receive-review）
- 自检（用 quality-gate）

## Execution

→ Read `workflows/request-review.md` for the detailed step-by-step process.

## Tests

N/A — reference-only module.

## Examples

- quality-gate 通过 → request-review → 匹配 reviewer → 发送请求 → 等待 receive-review
