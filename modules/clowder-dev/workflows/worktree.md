# Worktree — Execution Workflow

Step-by-step process for creating an isolated development worktree.
Invoked by `skills/worktree/SKILL.md`.

## Scripts

N/A — reference-only module. All steps are process descriptions.

## Execution Order

### 创建前：Main 同步检查

开 worktree 前必须确认 main 与 origin/main 完全同步（双向）：

```bash
# Step 1: 检查是否有未提交的文档变更
git status --porcelain docs/ | head -5

# Step 2: 检查 main 与 remote 双向同步
git fetch origin main --quiet
AHEAD=$(git rev-list --count origin/main..main)
BEHIND=$(git rev-list --count main..origin/main)
# ahead > 0 → 先 git push origin main
# behind > 0 → 先 git pull origin main
# 两者都 = 0 → 可以继续
```

### 创建步骤

```bash
# 1. 创建 worktree（目录位置遵循项目 CLAUDE.md/AGENTS.md 指定）
git worktree add ../project-{feature-name} -b feat/{feature-name}
cd ../project-{feature-name}

# 2. 安装依赖
# （项目特定命令）

# 3. 配置环境变量（如有隔离需求）
# （项目特定环境配置）

# 4. 验证基线测试通过
# （项目特定测试命令）
```

### 合入后清理

分支合入 main 后当场清理：

```bash
git worktree remove ../project-{feature-name}
git branch -d feat/{feature-name}
git worktree prune
```

### 安全核查

创建前：
- [ ] Main 双向同步（ahead=0 + behind=0）
- [ ] 目录放在项目外部（不在项目内部）
- [ ] 基线测试通过

清理前：
- [ ] 分支已合入 main
- [ ] 不是生产环境 worktree

## Tests

N/A — reference-only module.

## Examples

- `git worktree add ../cat-cafe-f042 -b feat/f042` → cd → install → verify baseline

### Document Sync Rule

After creating the worktree:
- Update `docs/features/Fxxx-*.md`:
  - Set `status: in-progress`
  - Record the worktree path and branch name

## Next Step

→ `tdd` — in the isolated worktree, start test-driven implementation.
