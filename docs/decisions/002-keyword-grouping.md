---
id: ADR-002
title: "Group same-meaning keywords into canonical groups"
doc_kind: decision
feature_ids: [F000]
topics: [taxonomy, grouping, normalization]
status: accepted
created: 2026-06-09
updated: 2026-06-09
schema_version: 1
---

# ADR-002: Group same-meaning keywords into canonical groups

## What

Keywords with the same meaning but different phrasing (e.g. "没钱", "经济困难", "现在确实困难") are grouped under a single canonical group name (e.g. `financial_hardship`). Each group stores the list of variant keywords and their aggregate frequency.

## Why

In debt collection conversations, customers express the same circumstance in many different ways. Without grouping, each variant becomes a separate state node in the decision tree, fragmenting the sentence pool and making retrieval unreliable. Grouping ensures that all turns about financial hardship map to the same state, concentrating evidence for better recommendations.

## Tradeoff

| Alternative | Pros | Cons |
|-------------|------|------|
| No grouping (each keyword separate) | Simple; no grouping logic needed | Fragmented sentence pools; poor retrieval quality |
| LLM-assisted grouping (chosen) | Concentrates evidence; better retrieval | Grouping quality depends on LLM; may over-merge distinct states |
| Manual curation | Perfect control | Doesn't scale; requires domain expert for every keyword |
