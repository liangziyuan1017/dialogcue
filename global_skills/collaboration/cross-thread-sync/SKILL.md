---
name: cross-thread-sync
description: >
  cross-session 协同：发现平行 session → 通知（3+2 件套）→ 争用协调 → 确认。
  Use when: 平行 session 之间需要协同、通知改动影响、共享文件争用。
  Not for: cross-check工作交接（用 cross-cat-handoff）。
  Output: cross-post 通知 + 争用协调完成。
triggers:
  - "通知另一个 session"
  - "cross-session"
  - "平行世界"
  - "parallel session sync"
  - "另一只agent"
  - "cross-thread"
---
# Cross-Session Sync — Coordination Pattern

Parallel session coordination: discover → notify → resolve contention → confirm.

**Note**: In single-agent projects, cross-session sync is less critical. This skill serves as a reference pattern for multi-module or multi-agent projects where parallel work may conflict.

## Step 1: Discover — Who is working in parallel?

Check for parallel sessions or processes that might affect shared resources.

**判断是否需要同步**：

| 改动范围 | 是否通知 |
|---------|---------|
| 共享文件（roadmap、feature doc、config） | 必须 |
| 被其他 feature 依赖的接口/类型 | 必须 |
| 共享/核心 package | 必须 |
| 纯内部改动（只影响自己 feature 的文件） | 不需要 |

## Step 2: Notify — 3+2 Escalation

### Default: 3 items

All cross-session notifications must include:

| # | Item | Description |
|---|------|------|
| 1 | **What Changed** | What was changed (file path + one-line summary) |
| 2 | **Impact on You** | How this affects the receiver (interface changed? need rebase?) |
| 3 | **Action Needed** | Sync level + specific action (see table below) |

### Sync Levels

| Level | Meaning | Receiver Action |
|------|---------|----------------|
| `[FYI]` | Informational only | No response needed, no action |
| `[ACTION]` | Action required | Execute specified action (rebase / rebuild / confirm compatibility) |
| `[BLOCKING]` | Blocking dependency | **Must ack**. Timeout without ack → escalate to Human |

### Escalation to 5 items

When touching any of these → add Why + Tradeoff:

- API contract changes (signature, input/output)
- Shared/core package changes
- Structural changes to shared state files
- Irreversible decisions (schema migration, data deletion)

## Step 3: Resolve Contention

If parallel changes conflict: identify overlap → propose resolution → confirm with affected parties.

## Step 4: Confirm

Blocking information must be dual-written to traceable state (feature doc / workflow / task), not only left in notification messages.

## Portability Notes

This skill was migrated from Clowder AI's cat-cafe-skills. The following changes were made:
- Clowder-specific infrastructure references (MCP tools, hooks, pnpm, Redis ports, biome, cat-config) have been stripped or genericized.
- Cross-references to other skills now point to `global_skills/` paths.
- References to `refs/` documents now point to `modules/clowder-dev/refs/`.
- MCP function calls and hook protocols are marked `[INFRA]` — they require equivalent infrastructure to be fully operational.

The core methodology, decision logic, checklists, and communication protocols are intact and universally applicable.
