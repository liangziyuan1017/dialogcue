---
name: tdd
description: >
  Red-Green-Refactor 测试驱动开发纪律。
  Use when: 写新功能代码、修 bug、任何实现工作。
  Not for: 纯文档、纯调研、已有充分测试的 trivial 改动。
  Output: 失败测试 → 最小实现 → 重构，全程有测试保护。
triggers:
  - "写代码"
  - "test first"
  - "TDD"
  - "红绿重构"
  - "F\\d+"
  - "f\\d+"
---

# TDD（测试驱动开发）

先写测试。看它失败。写最少代码通过。

**铁律：没有失败的测试，就没有实现代码。**

## What this skill does

1. Red: 写一个会失败的测试，亲眼看到它失败
2. Green: 写最少代码让测试通过，亲眼看到它通过
3. Refactor: 消除重复、改善命名，保持绿灯

## When to use

- 写新功能代码、修 bug、任何实现工作

## When NOT to use

- 纯文档、纯调研
- 已有充分测试的 trivial 改动

## Execution

→ Read `workflows/tdd.md` for the detailed Red-Green-Refactor cycle.

## Tests

N/A — reference-only module.

## Examples

- 新功能 → RED: 写失败测试 → GREEN: 最小实现 → REFACTOR: 改善结构
- Bug fix → 先写复现测试（必须红）→ 修复 → 确认通过 + 无回归
