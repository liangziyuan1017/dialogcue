<!--
  ROUTER FILE — Module-Level Routing Layer
  Purpose: The agent reads this table to match tasks to skills.
  Match against Description, Use When, and Triggers columns.
  Read the matched SKILL.md, then follow its pointer to workflow.md.
  If no entry matches, stop using this module.
-->

# clowder-dev Router — Development Flow Chain

```
feat-lifecycle → writing-plans → worktree → tdd → quality-gate → request-review → receive-review → merge-gate
```

## capability_map

| Skill | Path | Description | Use When | Not For | Output | Triggers |
|-------|------|-------------|----------|---------|--------|----------|
| **feat-lifecycle** | `skills/feat-lifecycle/SKILL.md` | Feature 立项、讨论、完成的全生命周期管理 | 开个新功能、new feature、F0xx、F001、F002、F003、立项、feature 完成、验收通过、讨论新功能需求。 | 代码实现、review、merge（那些有专门的 skill）。 | Feature 聚合文件 + BACKLOG 索引 + 真相源同步。 | 开个新功能, new feature, F0xx, F001, F002, F003, F004, F005, F\d+, f\d+, 立项, feature 完成, F0xx done, F\d+ done, f\d+ done, 验收通过, 讨论新功能需求 |
| **writing-plans** | `skills/writing-plans/SKILL.md` | 将 spec/需求拆分为可执行的分步实施计划 | 有 spec 或需求，准备动手前需要拆分步骤。 | trivial 改动（≤5 行）、已有详细计划。 | 分步实施计划（含 TDD 步骤和检查点）。 | 写计划, implementation plan, 拆分步骤, F\d+ plan, f\d+ plan |
| **worktree** | `skills/worktree/SKILL.md` | 创建 Git worktree 隔离开发环境 | 开始任何代码修改、新功能开发、bug fix。 | 纯文档修改（≤5 行）、不涉及代码的讨论。 | 隔离的 worktree + 正确的环境配置。 | 开始开发, 新 worktree, 开 worktree, F\d+, f\d+ |
| **tdd** | `skills/tdd/SKILL.md` | Red-Green-Refactor 测试驱动开发纪律 | 写新功能代码、修 bug、任何实现工作。 | 纯文档、纯调研、已有充分测试的 trivial 改动。 | 失败测试 → 最小实现 → 重构，全程有测试保护。 | 写代码, test first, TDD, 红绿重构, F\d+, f\d+ |
| **quality-gate** | `skills/quality-gate/SKILL.md` | 开发完成后的自检门禁：愿景对照 + spec 合规 + 验证 | 开发完了准备提 review、声称完成了、准备交付。 | 收到 review 反馈（用 receive-review）、merge（用 merge-gate）。 | Spec 合规报告（含愿景覆盖度）。 | 开发完了, 准备 review, 自检, 声称完成, F\d+ done, f\d+ done, F\d+ complete, f\d+ complete |
| **request-review** | `skills/request-review/SKILL.md` | 向 Human 提交 review 请求 | 自检通过后准备请 Human review。 | 收到 review 结果（用 receive-review）、自检（用 quality-gate）。 | Review 请求信。 | 请 review, 帮我看看, request review, F\d+ review, f\d+ review |
| **receive-review** | `skills/receive-review/SKILL.md` | 处理 Human 反馈：Red→Green 修复 | 收到 Human review 结果、Human 提了 feedback、需要处理反馈。 | 发 review 请求（用 request-review）、自检（用 quality-gate）。 | 逐项修复确认 + Human 放行。 | review 结果, review 意见, reviewer 说, fix these, F\d+ fix, f\d+ fix |
| **merge-gate** | `skills/merge-gate/SKILL.md` | 合入 main 的完整流程：门禁检查 → PR → review → squash merge → 清理 | reviewer 放行后准备合入、开 PR、准备 merge。 | 开发中、review 未通过、自检未完成。 | PR merged + worktree cleaned。 | 合入 main, merge, 准备合入, 开 PR, F\d+ merge, f\d+ merge |

## fallback_rule

- If no capability above matches the task, do NOT read any other file in this module.
- Rely on the agent itself to perform the task on `src/`.
