---
REMOVED_FIELD_id: F000
name: State Keyword Discovery
status: complete
owner: agent
related_features: []
topics: [state-extraction, taxonomy, data-analysis]
doc_kind: spec
created: 2026-06-09
---

# F000: State Keyword Discovery

> **Priority**: P0

## Why

Before we can extract state keywords from customer turns (F002), we need to know **what keywords to look for**. The original plan prescribed a fixed taxonomy (8 emotions, 10 facts, 5 willingness levels) but these were assumed, not discovered from data. Debt collection conversations in Chinese have domain-specific patterns — the actual frequent facts, emotions, and willingness signals may differ from assumptions. This feature grounds the taxonomy in real data.

## What

### Phase A: Customer State Discovery

Use DeepSeek LLM to analyze all **customer turns** across 31 records in `/data/output_manual.py`. For each turn, the LLM identifies:
- **Fact groups**: objective circumstances the customer describes (e.g. 失业, 工资拖延, 多头欠款). Same-meaning keywords with slightly different phrasing are **grouped** — each group has a canonical name, a list of variant keywords found in data, and frequency.
- **Emotion groups**: affective states expressed (e.g. 焦虑, 防御, 恳求). Grouped the same way — canonical name + variant keywords + frequency.
- **Willingness signals**: degree of repayment intent. Number of levels is **data-driven** — the LLM identifies natural breakpoints rather than fitting a preset count.

The LLM should also **suggest typical debt-collection domain keywords/states** that may not appear in these 31 records but are common in the domain (e.g. 法律威胁, 逃废债, 协商历史), marked as `source: "suggested"` vs `source: "observed"`.

Aggregate frequencies across all turns. Output to `/src/state_keywords.json`.

### Phase B: Collector Action Discovery

Use DeepSeek LLM to analyze all **collector turns** across 31 records. Discover the actual action type taxonomy from data rather than using a fixed 7-type enum. Same grouping approach — canonical action type + variant keywords + frequency + suggested domain-common actions.

Output appended to `/src/state_keywords.json` under `collector_actions`.

### Phase C: Willingness Level Definition

Define willingness as ordered levels (most resistant → most cooperative), where the count and boundaries are determined by natural clustering in the data. Each level has:
- `level`: name
- `definition`: what this level means in the debt collection context
- `boundary`: what distinguishes it from adjacent levels (why a turn is classified here and not one level up or down)
- `example_turns`: at least 2 verbatim turns from the data that demonstrate this level, with brief explanation of why each fits

## Acceptance Criteria

### Phase A（Customer State Discovery）
- [x] AC-A1: `state_keywords.json` contains `facts`, `emotions`, `willingness_levels` arrays
- [x] AC-A2: Each fact/emotion group has `group_name`, `keywords` (list of variants), `frequency`, `example_turn` (verbatim), `source` ("observed" or "suggested")
- [x] AC-A3: Groups sorted by frequency descending; suggested entries after observed
- [x] AC-A4: Total observed fact groups ≥ 5, total observed emotion groups ≥ 5
- [x] AC-A5: Every `example_turn` traces to an actual customer turn in `/data/output_manual.py`
- [x] AC-A6: Suggested domain keywords included with `source: "suggested"` and `frequency: 0`

### Phase B（Collector Action Discovery）
- [x] AC-B1: `state_keywords.json` contains `collector_actions` array
- [x] AC-B2: Each collector action group has `group_name`, `keywords`, `frequency`, `example_turn`, `source`
- [x] AC-B3: Total observed collector action groups ≥ 4
- [x] AC-B4: Every `example_turn` traces to an actual collector turn in `/data/output_manual.py`

### Phase C（Willingness Level Definition）
- [x] AC-C1: Willingness levels ordered from most resistant to most cooperative
- [ ] AC-C2: Each level has `level`, `definition`, `boundary`, `example_turns` (≥2 examples) — ⚠️ prompt updated to require ≥2; current output has 1 per level
- [x] AC-C3: Each `example_turn` includes `text` (verbatim) and `reason` (why it fits this level)
- [x] AC-C4: Boundaries are non-overlapping — a turn can only belong to one level
- [x] AC-C5: Level count is data-driven (no preset number)

## Dependencies

- **Evolved from**: None
- **Blocked by**: None
- **Related**: F002 (consumes this taxonomy as extraction target set)

## Risk

| 风险 | 缓解 |
|------|------|
| LLM invents keywords not grounded in data | Require every observed keyword to have a verbatim `example_turn`; suggested keywords explicitly flagged |
| Willingness level boundaries ambiguous | Explicit `boundary` field stating what distinguishes each level from neighbors |
| 31 records too few for stable frequency | Accept as prototype scope; flag low-frequency keywords for review at scale |
| Grouping too coarse or too fine | LLM groups by semantic similarity; Human reviews output before F002 consumes it |

## Open Questions

| # | 问题 | 状态 |
|---|------|------|
| OQ-1 | Should suggested keywords be included in F002 extraction targets or only for reference? | ⬜ 未定 |

## Key Decisions

| # | 决策 | 理由 | 日期 |
|---|------|------|------|
| KD-1 | Discover keywords from data rather than prescribe | Domain-specific Chinese debt collection language may not match assumed English tags | 2026-06-09 |
| KD-2 | Group similar-meaning keywords into canonical groups | Same circumstance expressed with different phrasing (e.g. "没钱" vs "经济困难") should map to same state | 2026-06-09 |
| KD-3 | Include suggested domain keywords (source: "suggested") | 31 records may not cover all common debt-collection scenarios; domain knowledge fills gaps | 2026-06-09 |
| KD-4 | Discover collector action types from data too | Fixed 7-type enum may not match actual collector behavior patterns in Chinese | 2026-06-09 |
| KD-5 | Willingness level count is data-driven | Let natural clustering in the data determine granularity | 2026-06-09 |

## Timeline

| 日期 | 事件 |
|------|------|
| 2026-06-09 | 立项 |
| 2026-06-09 | Discussion — grouping, suggested keywords, collector discovery, data-driven willingness |
| 2026-06-09 | Worktree created at `../icbc-f000` on branch `feat/f000-state-keyword-discovery` |
| 2026-06-09 | Merged into main, worktree cleaned |

## Links

| 类型 | 路径 | 说明 |
|------|------|------|
| **Plan** | [ROADMAP.md](../ROADMAP.md) | Dependency graph + architecture decisions |
| **Data** | `data/output_manual.py` | Source data (31 records, 805 turns) |

## Implementation Plan

→ [implementation-plan.md](F000-implementation-plan.md)
