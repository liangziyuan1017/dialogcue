---
name: writing-plans
description: >
  将 spec/需求拆分为可执行的分步实施计划。
  Use when: 有 spec 或需求，准备动手前需要拆分步骤。
  Not for: trivial 改动（≤5 行）、已有详细计划。
  Output: 分步实施计划（含 TDD 步骤和检查点）。
triggers:
  - "写计划"
  - "implementation plan"
  - "拆分步骤"
  - "F\\d+ plan"
  - "f\\d+ plan"
---

# Writing Plans

将 spec/需求拆分为分步实施计划。写清楚每步改哪些文件、代码、测试、怎么验证。

## What this skill does

1. Straight-Line Check: 确认每一步都在 A→B 直线上，无绕路
2. 拆分 bite-sized tasks（每步 2-5 分钟）
3. 输出结构化实施计划文档

## When to use

- 有 spec 或需求，准备动手前需要拆分步骤

## When NOT to use

- trivial 改动（≤5 行）
- 已有详细计划

## Execution

→ Read `workflows/writing-plans.md` for the detailed step-by-step process.

## Tests

N/A — reference-only module.

## Examples

- spec 确认后 → 写实施计划 → 加载 worktree 开始实现
