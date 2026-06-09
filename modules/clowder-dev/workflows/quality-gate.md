# Quality Gate — Execution Workflow

Step-by-step self-check before requesting review.
Invoked by `skills/quality-gate/SKILL.md`.

## Scripts

N/A — reference-only module. All steps are process descriptions.

## Execution Order

### Step 0: VISION CHECK（愿景核对）

1. 找原始 Discussion/Interview 文档（Human原话在里面）
2. 读核心痛点："我要..."、"我不想..."
3. 问自己：Human用这个功能，体验是什么样的？
4. AC 是否完整覆盖了Human的原始需求？→ 如有遗漏，先补 AC 再继续

### Step 0.5: DELIVERY COMPLETENESS CHECK

1. 完整 feat 还是部分？→ 部分：有Human明确同意分批交付的记录吗？
2. 后续需要"重写"还是"扩展"？→ 重写：如果是已标注 Spike 且有结论，通过；否则不通过

### Step 1: FIND — 找 spec/plan 文档

### Step 2: CREATE — 建检查清单

列出每一个 AC / 功能点 / 边界条件 + Discussion 里的 UX 描述和场景

### Step 3: VERIFY — 逐项检查

- 代码在哪？有测试覆盖？边界处理了？
- 交付物必须核实 commit/PR 状态
- 新增 MCP 工具 → MCP_TOOLS_SECTION 更新了吗？
- 新增行为规则 → governance digest 更新了吗？

### Step 4: RUNTIME GUARD — 运行态保护

- 若在生产环境：先探活，服务在线时直接复用，禁止执行启动命令
- 验证未合入改动时，不能把生产环境端口当成当前分支的证据
- 报告里同时写明 worktree/cwd + 目标 URL

### Step 5: PEN CHECK — 自动化设计稿对照

1. glob designs/**/*.pen，匹配当前 feat 编号或关键词
2. 匹配到 .pen → 强制进入设计稿对照流程
3. 无匹配但有 UI 改动 → 标注"⚠️ 无设计稿，跳过对照"
4. 此步骤不依赖记忆——必须执行 glob 命令

### Step 6: RUN — 运行验证命令（必须这次真实运行）

- 测试全部通过
- lint: 0 errors
- format check: 0 errors
- build: exit 0

### Step 7: READ — 完整读输出，看 exit code，数失败数

### Step 7.5: ARTIFACT HYGIENE CHECK — 根目录媒体垃圾闸门

检查工作树和已提交差异中是否有根目录媒体/设计工件。命中 → BLOCK，先归档再继续。

### Step 8: REPORT — 输出合规报告 + 证据

### 前端功能额外要求

≤3 张截图 + 1 段 15s 录屏，附"需求 → 截图"映射表。

### 有 .pen 设计稿的功能额外要求

1. 打开 .pen 文件 → 截取设计稿
2. 打开实际页面 → 截取实现截图
3. 逐区域对比：布局、颜色、间距、交互状态
4. 不一致处必须标注并修复
5. 报告附设计稿截图 vs 实现截图对照表

### 合规报告模板

```markdown
## Quality Gate Report

Spec: feature spec or implementation note
原始需求: feature-discussions/YYYY-MM-DD-xxx/README.md
检查时间: YYYY-MM-DD HH:MM

### 愿景覆盖（Step 0）
| # | Human原始需求 | AC 覆盖？ | 实现？ |
|---|---------------|-----------|--------|
| 1 | "我要 XXX"    | AC#3      | ✅     |

### 功能验收
| # | 要求 | 状态 | 代码位置 | 测试覆盖 |
|---|------|------|----------|----------|
| 1 | XXX  | ✅   | file.ts:L10 | test.spec.ts |

### 验证命令输出（必须是这次真实运行）
test → N/N pass ✅
lint → 0 errors ✅
check → 0 errors ✅
build → exit 0 ✅
```

### Red flags — 立刻 STOP

- 用 "should"、"probably"、"seems to"
- 表达满足感时还没运行命令
- 信任 subagent 的 "success" 报告而没独立验证

## Tests

N/A — reference-only module.

## Examples

- tdd 完成 → quality-gate: Vision Check → Spec Compliance → Run tests/lint/build → Report → request-review

### Document Sync Rule

After the quality gate passes:
- Update `docs/features/Fxxx-*.md`:
  - Set `status: review`
  - Verify ALL AC items are marked with accurate status (✅/⚠️/❌)
  - Update Files table with all delivered files
  - Add `## Design Decisions` section documenting key choices made during implementation
  - Update `updated:` timestamp

**Rule**: The feature doc is the review package. Before submitting for review, the doc must be a complete and accurate representation of what was built.

### Memory Hook: governance-review

Before submitting for review, invoke the memory hook from `registry/capabilities.yaml`:
→ `memory_hooks.quality-gate.complete: governance-review`
→ `modules/agent-memory/` → router → `governance-review`
→ Execute `workflows/governance-review.md`
→ Check the work against module principles, boundaries, and governance rules. Report violations or cautions.

## Next Step

→ `request-review` — after the quality gate passes **AND the feature doc is verified current**, submit for Human review.

**Gate**: Before proceeding, re-read `docs/features/Fxxx-*.md` and confirm it reflects ALL changes made in this phase. If the doc is stale, STOP — update it first.
