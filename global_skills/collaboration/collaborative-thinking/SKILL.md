---
name: collaborative-thinking
description: >
  单人或multi-agent的创意探索、独立思考、讨论收敛。
  Use when: brainstorm、multi-agent独立思考、讨论结束需要收敛、方向性问题需要多视角。
  Not for: 已有明确 spec 直接写代码、单猫执行已定方案。
  Output: 收敛报告（共识/分歧/行动项）+ 三件套沉淀检查。
triggers:
  - "brainstorm"
  - "讨论"
  - "multi-agent独立思考"
  - "收敛"
  - "讨论结束"
  - "总结一下"
---

# Collaborative Thinking

三种思考模式：单人探索 / multi-agent独立思考 / 讨论收敛沉淀。与 `feat-lifecycle` 讨论阶段的区别：`feat-lifecycle` 专用于 feat 采访和需求澄清；本 skill 是通用思考框架。

## 核心知识

| 模式 | 何时用 | 何时不用 |
|------|--------|----------|
| **A 单人探索** | 1:1 功能设计、想法 → spec | 需要多视角的方向性决策 |
| **A+ 多视角分析** | 架构选型、流程设计、需要多角度思考 | 实现细节、bug 定位（过度分析浪费时间） |
| **C 收敛沉淀** | 任何讨论产出了决策/规则/否决理由 | 纯问答（结论在 thread 里已够）、Human说"不用记" |

## Mode A: 单人探索 (Brainstorm)

**目标**：将模糊想法转化为可执行 spec，通过增量验证降低返工。

1. **理解上下文**：先读项目现状（文件、文档、近期 commits）。每次只问一个问题，优先多选题。
2. **探索方案**：提出 2-3 个备选 + tradeoffs，先说推荐和理由。**YAGNI 无情剪枝**——"以后可能需要"的功能先砍。
3. **呈现设计**：每次 200-300 字，每段后问"这个方向对吗？"。覆盖：架构 / 组件 / 数据流 / 错误处理 / 测试。
4. **产出**：设计文档写到 *(internal reference removed)*，commit 后问"要开始实现了吗？"

## Mode A+: Structured Solo Multi-Perspective

**何时使用**：需要多视角分析但只有单个 Agent 时。替代原 multi-agent 讨论模式。

**流程**：
1. **分视角独立分析**：Agent 依次从 2-3 个不同视角分析同一问题，每个视角独立产出分析，不参考其他视角结论
2. **标注不确定性**：区分确信的结论和猜测
3. **综合**：汇总各视角分析，标记共识区、分歧区、Tradeoffs
4. **呈现给 Human**：综合报告 + 各视角独立分析作为附录

**与 expert-panel 的区别**：expert-panel 用于正式分析报告（含 WHY 链四格）。本模式用于轻量级多视角思考。

## Mode C: 收敛沉淀 (Convergence)

**收敛三件套——每项必须显式回答"有/没有"，不允许跳过**：

**1. 否决理由 → ADR**：这次讨论有否决某个技术方案？有 → 补到对应 ADR 的否决记录段。

**2. 踩坑教训 → public-lessons.md**：这次讨论有暴露新坑？有 → 追加到 `docs/public-lessons.md`（7 槽位格式）。

**3. 操作规则 → 指引文件**：这次讨论有产生新的必须遵守的规则？有 → 更新 CLAUDE.md / AGENTS.md / GEMINI.md（或 `refs/shared-rules.md`）。

**强制回答格式**（附在 commit message 或文档末尾）：
```
## 收敛检查
1. 否决理由 → ADR？[有 → 已补到 ADR-0xx / 没有]
2. 踩坑教训 → lessons-learned？[有 → 已追加 / 没有]
3. 操作规则 → 指引文件？[有 → 已更新 CLAUDE.md §xx / 没有]
```

**追溯链**（每次收敛必须建立）：BACKLOG 条目 link 会议纪要入口；每篇文档头部 link 回上级文档。

**会议纪要模板**（存放：*(internal reference removed)*）：
```markdown
# {主题} 讨论纪要
**Thread ID**: `thread_xxx` | **日期**: YYYY-MM-DD | **参与者**: [列出]

## 背景 / 各方观点 / 共识 / 分歧 / 待决 / 行动项
```

## Quick Reference

| 你要做的事 | 用哪个 Mode |
|-----------|------------|
| 帮Human把想法变成 spec | A |
| 需要多视角分析一个架构方向 | A+ |
| 讨论刚结束，要沉淀 | C |
| Mode A+ 结束后 | **C** |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Mode A 一次问多个问题 | 拆成多条，每条只问一件事 |
| Mode A 没提备选方案就直接设计 | 先 2-3 个方案 + tradeoffs，再推荐 |
| Mode A+ Step 1 让猫看到彼此回答 | 依次从各视角独立分析，不参考其他视角结论 |
| Mode A+ 综合时抹平分歧 | 分歧必须保留 + 标注各方理由 |
| Mode A+ 跳过综合复核 | 综合可能误读观点，原作者必须确认 |
| Mode C 三件套"感觉没有就跳过" | 必须显式回答每一项"有/没有" |
| Mode C 写了纪要但不 link BACKLOG | 追溯链断裂，未来找不到 |

## 下一步

- Mode A 结束 → `worktree` 拉 worktree，`writing-plans` 做实现计划
- Mode A+ 结束 → **必须进入 Mode C** 收敛
- Mode C 完成后 → commit：`docs({scope}): {topic} 讨论收敛 + 追溯链 [{Agent签名}]`
- 产出了新 feat → `feat-lifecycle` skill 立项


## Portability Notes

This skill was migrated from Clowder AI's cat-cafe-skills. The following changes were made:
- Clowder-specific infrastructure references (MCP tools, hooks, pnpm, Redis ports, biome, cat-config) have been stripped or genericized.
- Cross-references to other skills now point to `global_skills/` paths.
- References to `refs/` documents now point to `modules/clowder-dev/refs/`.
- MCP function calls and hook protocols are marked `[INFRA]` — they require equivalent infrastructure to be fully operational.

The core methodology, decision logic, checklists, and communication protocols are intact and universally applicable.
