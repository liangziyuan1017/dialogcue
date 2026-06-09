# Feature Lifecycle — Execution Workflow

Step-by-step process for feature lifecycle management.
Invoked by `skills/feat-lifecycle/SKILL.md`.

## Scripts

N/A — reference-only module. All steps are process descriptions.

## Execution Order

### Kickoff (立项)

**Step 0: 关联检测（内部 + 社区 issue 都必须做）**

分配 F 编号前，先跑关联检测，防止重复立项或把子任务误立为独立 feature：

1. 扫描 BACKLOG + features/
2. 判定：

| 判定结果 | 处置 |
|---------|------|
| 已有 Feature 的子任务/phase | 不立新号，挂到现有 Fxxx 下 |
| 已有 Feature 的相关需求 | 标记 related: Fxxx，由 maintainer 决定合并还是独立 |
| 全新独立需求 | 继续走 Step 1 分配 F 号 |
| 太小 / 纯 enhancement | 不立项，保留 enhancement 标签 |

3. 社区 issue 额外检查：可行性、粒度、回溯（feature doc 必须含 community_issue 字段）

**Step 1: 分配 ID**

取最大 F 编号 + 1，三位数。

**Step 2: 创建聚合文件**

从模板创建 `docs/features/Fxxx-name.md`（kebab-case）。轻量 Feature（≤1 Phase）可省略部分章节，但 Frontmatter + Status + Why + What + AC + Dependencies 必须保留。

**Step 3: 更新 ROADMAP.md**

末尾加行：`| F042 | 名称 | spec | Owner | source | [F042](features/...) |`

**Step 4: 关联文档**

Links 章节列出相关 research/discussion；更新这些文档的 feature_ids。

**Step 5: Commit**

`docs(F042): kickoff {名称}`

### Memory Hook: memory-search

After kickoff, invoke the memory hook from `registry/capabilities.yaml`:
→ `memory_hooks.feat-lifecycle.kickoff: memory-search`
→ `modules/agent-memory/` → router → `memory-search`
→ Execute `workflows/memory-search.md`
→ Search for prior decisions, lessons, or knowledge related to this feature topic. Reference any findings in the feature doc.

### Discussion (讨论)

**两种模式**：

- **采访式（默认）**：Human口述 → 一次一问澄清 → 排优先级 → 记开放问题
- **开放讨论**：多猫协作。结构：背景 + 分析 + 开放问题 + 倾向

**讨论结束必须做**：
1. 落盘讨论文档（含Human原话、决策过程、优先级排序）
2. ROADMAP.md 该 Feature 行 ref 讨论文档链接
3. Commit

### Design Gate (设计确认)

Discussion → writing-plans 之间的必经关卡。UX 没确认，不准开 worktree。

| 类型 | 确认人 | 方式 |
|------|--------|------|
| 前端 UI/UX | Human | wireframe → Human OK |
| 纯后端 | 其他Agent | collaborative-thinking 讨论共识 |
| 架构级 | Agent讨论 → Human拍板 | 先出方案再上报 |
| Trivial | 跳过 | 按 SOP 例外路径 |

**元审美自检**：方案是坐标变换（改变问题结构）还是多项式堆项（叠补丁/层数）？后者 → 先读 meta-aesthetics canon，尝试更简的分解方式。

### Memory Hook: decision-record

After Design Gate, invoke the memory hook from `registry/capabilities.yaml`:
→ `memory_hooks.feat-lifecycle.design_gate: decision-record`
→ `modules/agent-memory/` → router → `decision-record`
→ Execute `workflows/decision-record.md`
→ Record the architecture/design decisions made during Design Gate as durable ADRs.

### Completion (完成)

**Step 0: 愿景对照（不可跳过）**

AC 全打勾 ≠ 完成。先读原始 Discussion/Interview，自问：核心问题？解决了吗？体验如何？

**愿景守护证物对照表（缺表 = BLOCKED）**：

| Human原话（逐字引用） | 当前实际状态 | 匹配？ |
|----------------------|-------------|--------|
| "...原话..." | 截图/代码/命令输出 | ✅/❌ |

**self-verification + human confirmation**：自己先完成三问 + 对照表 → @ 其他猫请求独立愿景守护 → 对齐 → 填签收表。

**交付物核实铁律**：spec checkbox 是记录工具，不是真相源。声称"完成"前必须核实实际 commit/PR 状态。

## Tests

N/A — reference-only module.

## Examples

- 新功能立项：关联检测 → 分配 F 号 → 创建聚合文件 → 更新 ROADMAP → commit
- 讨论收敛：讨论文档落盘 → ROADMAP 关联 → commit
- Feature 完成：愿景对照 → 证物对照表 → cross-check验证 → 签收

### Document Sync Rule

**After EVERY phase in this workflow, update `docs/features/Fxxx-*.md`:**
- Kickoff complete → set `status: kickoff`, fill Why/What/AC
- Discussion complete → add design decisions, update What section
- Design Gate approved → set `status: design-approved`, document architecture
- Completion → set `status: complete`, mark all AC ✅, add Files table

**Never leave the feature doc stale.** If the feature changed during this phase, the doc must reflect it before moving to the next phase.

## Next Step

→ `writing-plans` — after Design Gate confirms the approach, write the implementation plan.
