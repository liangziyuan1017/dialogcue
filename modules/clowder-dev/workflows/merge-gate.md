# Merge Gate — Execution Workflow

Step-by-step process for merging into main.
Invoked by `skills/merge-gate/SKILL.md`.

## Scripts

N/A — reference-only module. All steps are process descriptions.

## Execution Order

### 门禁 5 硬条件（全部满足才能开 PR）

1. Reviewer 有明确放行信号（"放行"/"LGTM"/"通过"/"可以合入"）
2. 所有 P1/P2 已修复且经 reviewer 确认
3. Review 针对当前分支/当前工作（不是历史 review，必须覆盖当前 HEAD）
4. BACKLOG 涉及条目已在 feature branch 上标记完成
5. 全量门禁（build + test + lint + check）全绿，基于最新 main rebase

### Review Continuity Guard

只要 HEAD 变了，旧 review 默认不自动继承。必须核对：
- reviewer 放行对应的 SHA = 当前 HEAD → 通过
- 不一致 → 停止 merge-gate

### 合入流程

```bash
# 1. Rebase 到最新 main + 全量门禁
# 项目特定命令（如 pnpm gate 或等效）

# 2. Root Artifact Guard
# 检查根目录是否有媒体/设计工件

# 3. Push feature branch
git push origin {branch}

# 4. 开 PR（使用 refs/pr-template.md 模板）
# 项目特定 PR 创建命令

# 5. 触发 review

# 6. 等待 review 通过（事件驱动，不轮询）

# 7. Squash merge
# 项目特定 merge 命令

# 8. 清理 worktree
git worktree remove ../project-{feature-name}
git branch -d feat/{feature-name}
git worktree prune
```

### 合入后清理

分支合入 main 后当场清理，不要留到下次。检查是否有积压未清理的 worktree 和已合入分支。

## Tests

N/A — reference-only module.

## Examples

- receive-review 放行 → 门禁 5 条件全绿 → rebase main → PR → review → squash merge → 清理 worktree → feat-lifecycle (完成)

### Document Sync Rule

After merge:
- Update `docs/features/Fxxx-*.md`:
  - Set `status: complete`
  - Set `merged:` with date and commit reference
  - Verify ALL AC items have final status
  - Update `updated:` timestamp

**Rule**: A merged feature with a stale doc is incomplete. The doc is the historical record — make it accurate before closing.

### Memory Hook: memory-index

After merge, invoke the memory hook from `registry/capabilities.yaml`:
→ `memory_hooks.merge-gate.complete: memory-index`
→ `modules/agent-memory/` → router → `memory-index`
→ Execute `workflows/memory-index.md`
→ Rebuild the searchable memory index so the merged feature's decisions and lessons are discoverable.

## Next Step

→ Complete. The feature is merged. Return to `feat-lifecycle` Completion phase for vision verification and close-out.
