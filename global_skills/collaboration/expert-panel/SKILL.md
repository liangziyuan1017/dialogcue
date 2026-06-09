---
name: expert-panel
description: >
  Structured Multi-Perspective Analysis — single agent analyzes problem from multiple viewpoints and synthesizes findings.
  Use when: 技术趋势判断、竞品分析、行业事件分析、需要多视角决策支持、Human说"帮我分析一下"。
  Not for: 简单问题（直接回答）、代码实现、bug fix、日常聊天。
  Output: Multi-perspective analysis report with WHY-chain (Evidence/Reasoning/So What/Confidence).
triggers:
  - "帮我分析一下"
  - "expert panel"
  - "技术参谋"
  - "竞品分析"
  - "行业分析"
  - "趋势判断"
  - "多视角分析"
  - "showcase"
---

# Expert Panel — Structured Multi-Perspective Analysis

**定位：结构化多视角分析框架。** 单个 Agent 依次从多个视角独立分析同一问题，然后综合汇报给 Human。

**核心原则：结论不值钱，论证过程才值钱。**

## 本 skill 的工作

1. **视角分工**：Agent 依次扮演 Analyst / Assessor / Strategist 角色
2. **WHY 链标准**：每个结论必须有 Evidence → Reasoning → So What → Confidence
3. **综合交付**：多视角分析综合成报告呈现给 Human

## 视角分配

Agent 依次从以下视角独立分析（最少 2 个，推荐 3 个）：

| 角色 | 视角 | 职责 |
|------|------|------|
| **Analyst** | 架构/技术 | 技术深度、架构对比、可借鉴点 |
| **Assessor** | 风险/成本 | 成本结构、合规风险、踩坑预警 |
| **Strategist** | 生态/趋势 | 行业定位、大图景、用户/人才视角 |

## 执行流程

```
Analyze (Analyst) → Analyze (Assessor) → Analyze (Strategist) → Synthesize → Present to Human
```

### Step 1: Independent Analysis per Perspective

Agent 依次从每个角色视角独立分析同一个问题。每个视角的分析不参考其他视角的结论。

**调研分两档**：

| 档位 | 何时用 | 方法 |
|------|--------|------|
| **Light**（默认） | 日常分析、快速判断 | WebSearch + search_evidence + 已有知识 |
| **Full** | 高 stakes / Human说"调研" / 需要多源验证 | 启动 `deep-research` skill 完整流程 |

不确定用哪档 → 用 Light。Light 不够再升级。

**分析输出格式 — WHY 链四格**：

每个核心判断必须有：
```
Evidence:   具体证据（案例/数据/事件 + 来源URL或引用）
Reasoning:  从证据到结论的逻辑链（为什么这个证据支持这个结论）
So what:    对我们意味着什么（行动含义）
Confidence: 确信 / 中等 / 猜测
```

**禁止**：
- 光给结论不给论证（"基于行业经验" 不是证据）
- Evidence 和 Reasoning 混在一起（拆开写）

### Step 2: Synthesis

Agent 汇总所有视角的分析，产出综合报告。

综合必须包含：
- 各视角观点摘要
- 共识区
- **分歧区**（不抹平！各方理由都保留）
- Tradeoffs / 适用边界（结论在什么场景成立、什么场景不适用）
- Open Questions（待Human拍板）
- 行动项

### Step 3: Present to Human

Agent 向 Human 交付综合报告。

## 报告结构

1. **命题与范围**：在讨论什么，不讨论什么
2. **核心判断**（每条四格）：Evidence / Reasoning / So What / Confidence
3. **证据矩阵**：各视角调研发现汇总（来源 + 可靠度）
4. **推理链**：从证据到结论的逻辑链，含分歧点和各方理由
5. **Tradeoffs / 适用边界**：推荐在哪些场景成立、哪些场景不适用
6. **Premortem**：最可能翻车在哪 + 护栏
7. **行动建议**（分层：决策者 / 执行者）
8. **Open Questions**：待Human拍板
9. **独立分析记录**：各视角的独立判断摘要 + 独特洞察

## 什么时候叠加其他 skill？

| 场景 | 用什么 |
|------|--------|
| 日常"帮我分析一下" | expert-panel 单独用（Light 调研档） |
| 高 stakes 决策、Human说"调研" | expert-panel + `deep-research`（Full 调研档） |
| 分析后需要立项 | expert-panel → `feat-lifecycle` |
| 分析后需要沉淀 | expert-panel → `collaborative-thinking` Mode C |


## Portability Notes

This skill was migrated from Clowder AI. Adapted for single-agent use: multi-agent dispatch/synthesis/contributor-check mechanics replaced with sequential solo multi-perspective analysis. The WHY-chain standard (Evidence/Reasoning/So What/Confidence) is universally applicable.
