---
id: ADR-009
title: "Eliminate F002 LLM State Extraction — use F001 manual annotations only"
doc_kind: decision
feature_ids: [F002]
topics: [architecture, state-extraction, cost-reduction]
status: accepted
created: 2026-06-10
updated: 2026-06-10
schema_version: 1
---

# Eliminate F002 LLM State Extraction

## What

Remove F002 (LLM State Extraction) entirely. The system will rely on the manual annotations already present in F001's `output_aligned.py` (493 of 805 turns labeled). No LLM-based per-turn extraction step.

## Why

- The 493 labeled turns from F001 already provide sufficient state coverage for downstream features (F003 reward labeling, F004 decision tree).
- Running DeepSeek on all 805 turns costs API calls, adds latency, and introduces LLM inconsistency on short/ambiguous turns.
- The labeled turns cover the structurally important turns (state transitions, collector actions). Unlabeled turns are mostly filler ("嗯", "对", "好") that carry no state information worth extracting.
- `action_text` was redundant — it duplicated `turn["text"]`.

## Tradeoff

| Alternative | Pros | Cons |
|---|---|---|
| **Keep F002 (LLM all turns)** | Full 805/805 coverage | Cost, latency, LLM noise on filler turns, redundant data |
| **Keep F002 (LLM unlabeled only)** | Resume-safe, covers gaps | Still costs API calls for marginal gain on filler turns |
| **Remove F002 (chosen)** | Zero cost, no LLM noise, simpler pipeline | 312 turns stay unlabeled; downstream must handle missing state |

Downstream features (F003, F004) must handle turns without `state` gracefully — skip them in path extraction, or infer from context.
