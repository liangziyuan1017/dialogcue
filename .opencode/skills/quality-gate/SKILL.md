---
name: quality-gate
description: >
  开发完成后的自检门禁：愿景对照 + spec 合规 + 验证。
  Use when: 开发完了准备提 review、声称完成了、准备交付。
  Not for: 收到 review 反馈（用 receive-review）、merge（用 merge-gate）。
  Output: Spec 合规报告（含愿景覆盖度）。
triggers:
  - "开发完了"
  - "准备 review"
  - "自检"
  - "声称完成"
  - "F\\d+ done"
  - "f\\d+ done"
  - "F\\d+ complete"
  - "f\\d+ complete"
---

# Quality Gate

开发完成到提 review 之间的双重关卡：对照 spec 自检 + 用真实命令输出证明你的声明。

**铁律：`NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE`**

## What this skill does

1. Vision Check: 回读原始需求，对照愿景
2. Spec Compliance: 逐项验收 AC + 功能点 + 边界条件
3. Runtime Guard: 前端证据采集前保护运行态
4. Pen Check: 自动化设计稿对照
5. Run Verification: 真实运行测试/lint/build
6. Report: 输出合规报告 + 证据

## When to use

- 开发完了准备提 review
- 声称完成了、准备交付

## When NOT to use

- 收到 review 反馈（用 receive-review）
- Merge（用 merge-gate）

## Execution

→ Read `workflows/quality-gate.md` for the detailed step-by-step process.

## Tests

N/A — reference-only module.

## Examples

- tdd 完成 → quality-gate → 愿景对照 → spec 逐项 → 测试/lint/build → 报告 → request-review
