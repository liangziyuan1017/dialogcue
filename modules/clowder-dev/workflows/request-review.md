# Request Review — Execution Workflow

Step-by-step process for requesting code review.
Invoked by `skills/request-review/SKILL.md`.

## Scripts

N/A — reference-only module. All steps are process descriptions.

## Execution Order

### 前置条件（全部满足才能发请求）

| 条件 | 检查方式 | 未满足时 |
|------|----------|----------|
| quality-gate 通过 | 有本轮 gate report | BLOCKED — 先跑 quality-gate |
| 测试全绿 | 附测试命令输出 | BLOCKED — 修到绿灯再发 |
| 原始需求可引用 | Discussion 文档路径 + ≤5 行摘录 | BLOCKED — reviewer 有权拒绝审查 |
| 前端改动已实测 | 浏览器截图证据 | BLOCKED — 涉及前端必须真实验证 |
| 根目录工件闸门通过 | 无根目录媒体/设计工件 | BLOCKED — 先归档/清理再发 |

### 流程

```
BEFORE 发 review 请求:

1. 确认 quality-gate 已通过（拿到本轮 gate report）
2. 确认测试全绿（附这次真实运行的输出）
3. 找到原始 Discussion 文档路径 + 摘录 ≤5 行原话
4. 检查 worktree 工具落点（git status 干净）
5. 检查根目录工件闸门
6. 匹配 reviewer
7. 用模板写 review 请求
8. 发送
```

### Reviewer 匹配规则

从项目配置动态匹配。优先级：
1. 跨 team/family
2. peer-reviewer 角色标记
3. 当前可用（无正在进行的 review 任务）

### Review 请求模板

使用 `refs/review-request-template.md` 模板。

关键字段：
- **Original Requirements**: 必填，≤5 行原话 + 来源文档路径
- **Open Questions**: 标注 review 重点
- **自检证据**: 附 quality-gate report 摘要 + 测试命令输出

### Block 场景

没有 quality-gate 报告 → BLOCKED
测试不绿 → BLOCKED
原始需求不可引用 → BLOCKED

## Tests

N/A — reference-only module.

## Examples

- quality-gate 通过 → 匹配 reviewer → 发送 review 请求 → reviewer 开始 receive-review

### Document Sync Rule

After submitting for review:
- Update `docs/features/Fxxx-*.md`:
  - Set `status: review` if not already set
  - Record the review submission (date, reviewer, what was submitted)

## Next Step

→ `receive-review` — after submitting for review, process the Human's feedback.
