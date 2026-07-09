---
name: feat-lifecycle
description: >
  Feature 立项、讨论、完成的全生命周期管理。
  Use when: 开个新功能、new feature、F0xx、立项、feature 完成、验收通过、讨论新功能需求。
  Not for: 代码实现、review、merge（那些有专门的 skill）。
  Output: Feature 聚合文件 + BACKLOG 索引 + 真相源同步。
triggers:
  - "开个新功能"
  - "new feature"
  - "F0xx"
  - "F001"
  - "F002"
  - "F003"
  - "F004"
  - "F005"
  - "F\\d+"
  - "f\\d+"
  - "立项"
  - "feature 完成"
  - "F0xx done"
  - "F\\d+ done"
  - "f\\d+ done"
  - "验收通过"
  - "讨论新功能需求"
---

# Feature Lifecycle

管理 Feature 从诞生到收尾：立项建追溯链、讨论沉淀决策、完成闭环同步。

## What this skill does

1. Kickoff: 分配 F 编号、创建聚合文件、更新 ROADMAP、关联文档、commit
2. Discussion: 采访式或开放讨论，沉淀决策
3. Design Gate: UX 确认、架构确认、元审美自检
4. Completion: 愿景对照、交付物核实、self-verification + human confirmation

## When to use

- 开新功能、立项、讨论新功能需求
- Feature 完成、验收通过

## When NOT to use

- 代码实现（用 tdd）
- Review（用 request-review/receive-review）
- Merge（用 merge-gate）

## Execution

→ Read `workflows/feat-lifecycle.md` for the detailed step-by-step process.

## Tests

N/A — reference-only module.

## Examples

- Human说"开个新功能" → 走 Kickoff 流程，分配 F 编号
- 讨论结束 → 落盘讨论文档 + 更新 ROADMAP
- AC 全打勾 + PR 合入 → 走 Completion 流程，愿景对照 + human confirmation
