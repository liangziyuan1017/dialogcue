---
feature_ids: [F000]
related_features: []
topics: [state-extraction, taxonomy, data-analysis]
doc_kind: spec
created: 2026-06-09
---

# F000: State Keyword Discovery

> **Status**: spec | **Owner**: agent | **Priority**: P0

## Why

Before we can extract state keywords from customer turns (F002), we need to know **what keywords to look for**. The original plan prescribed a fixed taxonomy (8 emotions, 10 facts, 5 willingness levels) but these were assumed, not discovered from data. Debt collection conversations in Chinese have domain-specific patterns — the actual frequent facts, emotions, and willingness signals may differ from assumptions. This feature grounds the taxonomy in real data.

## What

### Phase A: Data Exploration

Use DeepSeek LLM to analyze all customer turns across 31 records in `/data/output_manual.py`. For each turn, the LLM identifies:
- **Fact patterns**: objective circumstances the customer describes (e.g. 失业, 工资拖延, 多头欠款)
- **Emotion patterns**: affective states expressed (e.g. 焦虑, 防御, 恳求)
- **Willingness signals**: degree of repayment intent, from resistant to cooperative

Aggregate frequencies across all turns. Output the discovered taxonomy to `/src/state_keywords.json`.

### Phase B: Willingness Level Definition

Define willingness as ordered levels (most resistant → most cooperative). Each level has:
- `level`: name (e.g. `resistant`, `weak`, `conditional`, `strong`)
- `definition`: what this level means in the debt collection context
- `boundary`: what distinguishes it from adjacent levels (why a turn is classified here and not one level up or down)
- `example_turns`: at least 2 verbatim turns from the data that demonstrate this level, with brief explanation of why each fits

## Acceptance Criteria

### Phase A（Data Exploration）
- [ ] AC-A1: `state_keywords.json` contains `facts`, `emotions`, `willingness_levels` arrays
- [ ] AC-A2: Each fact entry has `keyword`, `frequency`, `example_turn` (verbatim from data)
- [ ] AC-A3: Each emotion entry has `keyword`, `frequency`, `example_turn`
- [ ] AC-A4: Facts sorted by frequency descending; emotions sorted by frequency descending
- [ ] AC-A5: Total distinct facts ≥ 5, total distinct emotions ≥ 5
- [ ] AC-A6: Every `example_turn` traces to an actual customer turn in `/data/output_manual.py`

### Phase B（Willingness Level Definition）
- [ ] AC-B1: Willingness levels ordered from most resistant to most cooperative
- [ ] AC-B2: Each level has `level`, `definition`, `boundary`, `example_turns` (≥2 examples)
- [ ] AC-B3: Each `example_turn` includes `text` (verbatim) and `reason` (why it fits this level)
- [ ] AC-B4: Total willingness levels ≥ 4
- [ ] AC-B5: Boundaries are non-overlapping — a turn can only belong to one level

## Dependencies

- **Evolved from**: None
- **Blocked by**: None
- **Related**: F002 (consumes this taxonomy as extraction target set)

## Risk

| 风险 | 缓解 |
|------|------|
| LLM invents keywords not grounded in data | Require every keyword to have a verbatim `example_turn` from actual records |
| Willingness level boundaries ambiguous | Explicit `boundary` field stating what distinguishes each level from neighbors |
| 31 records too few for stable frequency | Accept as prototype scope; flag low-frequency keywords for review at scale |

## Open Questions

| # | 问题 | 状态 |
|---|------|------|
| OQ-1 | Should collector turns also be analyzed for action type taxonomy, or keep the fixed 7-type enum? | ⬜ 未定 |

## Key Decisions

| # | 决策 | 理由 | 日期 |
|---|------|------|------|
| KD-1 | Discover keywords from data rather than prescribe | Domain-specific Chinese debt collection language may not match assumed English tags | 2026-06-09 |

## Timeline

| 日期 | 事件 |
|------|------|
| 2026-06-09 | 立项 |

## Links

| 类型 | 路径 | 说明 |
|------|------|------|
| **Plan** | `plan_feature_base.md` | Feature-wise plan with F000 as first feature |
| **Data** | `data/output_manual.py` | Source data (31 records, 805 turns) |
