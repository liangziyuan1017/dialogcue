---
name: merge-gate
description: >
  合入 main 的完整流程：门禁检查 → PR → review → squash merge → 清理。
  Use when: reviewer 放行后准备合入、开 PR、准备 merge。
  Not for: 开发中、review 未通过、自检未完成。
  Output: PR merged + worktree cleaned。
triggers:
  - "合入 main"
  - "merge"
  - "准备合入"
  - "开 PR"
  - "F\\d+ merge"
  - "f\\d+ merge"
---

# Merge Gate

合入 main 的完整流程：门禁检查 → PR → review → squash merge → 清理。

## What this skill does

1. 门禁检查：5 硬条件全部满足才能开 PR
2. 开 PR + 触发 review
3. 等待 review 通过
4. Squash merge
5. 清理 worktree

## When to use

- reviewer 放行后准备合入、开 PR、准备 merge

## When NOT to use

- 开发中、review 未通过、自检未完成

## Execution

→ Read `workflows/merge-gate.md` for the detailed step-by-step process.

## Tests

N/A — reference-only module.

## Examples

- receive-review 放行 → merge-gate: 门禁检查 → 开 PR → review → squash merge → 清理 worktree
