---
name: worktree
description: >
  创建 Git worktree 隔离开发环境。
  Use when: 开始任何代码修改、新功能开发、bug fix。
  Not for: 纯文档修改（≤5 行）、不涉及代码的讨论。
  Output: 隔离的 worktree + 正确的环境配置。
triggers:
  - "开始开发"
  - "新 worktree"
  - "开 worktree"
  - "F\\d+"
  - "f\\d+"
---

# Worktree

开始任何非 trivial 的功能开发前，必须拉 worktree 隔离，不要直接在 main 上改代码。

## What this skill does

1. Main 同步检查（双向同步）
2. 创建 git worktree + 分支
3. 安装依赖、配置环境
4. 验证基线测试通过

## When to use

- 开始任何代码修改、新功能开发、bug fix

## When NOT to use

- 纯文档修改（≤5 行）
- 不涉及代码的讨论

## Execution

→ Read `workflows/worktree.md` for the detailed step-by-step process.

## Tests

N/A — reference-only module.

## Examples

- writing-plans 完成 → 拉 worktree → 安装依赖 → 验证基线 → 开始 tdd
